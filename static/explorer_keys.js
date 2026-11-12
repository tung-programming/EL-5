/*
 * Expression explorer: keyboard interaction. Owner: Member 4.
 * Shared integration point with Member 5 (static/app.js). See plan.md §7.6, §7.8
 * and docs/keyboard_guide.md (the source of truth for keys and messages).
 *
 * Two layers, no dependencies, works in a browser (window.ExplorerKeys) and in
 * Node (module.exports) so the logic can be unit-tested without a browser.
 *
 *  1. createController(tree)  PURE LOGIC. Tracks the focused node, turns a key
 *     event into a result object. Knows nothing about the DOM or speech.
 *  2. createView(container, tree, options)  THIN DOM ADAPTER. Builds the ARIA
 *     tree, roving tabindex, live region and help panel, and applies the
 *     controller's results. NOT yet verified in a real browser or with NVDA/Orca.
 *
 * `tree` is the ExplorerNode tree from engine/explore.py, the ExplorerNode of
 * docs/contracts.md (the authoritative shared contract):
 *   {id, type, role, value, spoken_quick, spoken_detailed, spoken_context, children[]}
 * There is no span. This module needs only `id` (unique string) and `children`;
 * `role` and the three spoken_* strings are used when present, and any other
 * field is ignored.
 *
 * Announcement strategy (one voice at a time):
 *   Every event produces AT MOST ONE spoken string, delivered through exactly ONE
 *   channel chosen by options.mode:
 *     "screen-reader" (default): arrow/Home movement is spoken by the screen
 *        reader from the focused item's accessible name; Space/I/C/R/?/boundary
 *        text goes to the aria-live region. speechSynthesis is never called.
 *     "speech": no screen reader; the page speaks through speechSynthesis
 *        (cancelling anything already speaking) and the live region is not used.
 *   Movement therefore never also writes to the live region, so it cannot be
 *   announced twice. If "speech" is requested but no speak() function is given,
 *   the view falls back to "screen-reader" (view.mode / view.modeFallback say so).
 *
 * Lifecycle: createView() returns a view with destroy(). Calling createView()
 * again on the same container destroys the previous view first, so there are
 * never two trees, two key listeners or two controllers on one container.
 *
 * Errors thrown on bad input are Error objects with a `code`:
 *   "tree-invalid", "tree-too-deep" (more than MAX_DEPTH levels),
 *   "options-invalid", "container-invalid", "destroyed".
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.ExplorerKeys = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---- Messages (docs/keyboard_guide.md §3, §4) ----------------------------

  var MAX_DEPTH = 100; // real algebra trees are about 10 deep

  function fail(code, message) {
    var err = new Error(message);
    err.code = code;
    return err;
  }

  var MSG = {
    NO_PARENT: "This is the whole equation. There is nothing bigger.",
    FIRST: "This is the first part at this level.",
    LAST: "This is the last part at this level.",
    ONLY: "This is the only part at this level.",
    AT_ROOT: "Already at the whole equation.",
    LEFT: "Left the explorer.",
    FALLBACK_NAME: "Equation part",
  };

  var NAV_ACTIONS = {
    parent: true,
    firstChild: true,
    previousSibling: true,
    nextSibling: true,
    root: true,
  };

  // [key label, what it does]. Order is the spoken order (guide §4).
  var HELP_ITEMS = [
    ["Up arrow", "move to the bigger part"],
    ["Down arrow", "move inside"],
    ["Left and right arrows", "previous and next part at the same level"],
    ["Space", "hear this part"],
    ["I", "more information"],
    ["C", "how this part connects to the rest"],
    ["R", "read the whole equation again"],
    ["Home", "back to the whole equation"],
    ["Escape", "leave the explorer"],
  ];
  var HELP_TEXT =
    HELP_ITEMS.map(function (p) {
      return p[0] + ": " + p[1] + ".";
    }).join(" ");

  // Normalised key name -> action id. This is the complete key map.
  var KEY_ACTIONS = {
    ArrowUp: "parent",
    ArrowDown: "firstChild",
    ArrowLeft: "previousSibling",
    ArrowRight: "nextSibling",
    Space: "quick",
    i: "detailed",
    c: "context",
    r: "readAll",
    Home: "root",
    "?": "help",
    Escape: "exit",
  };

  function normaliseKey(key) {
    if (typeof key !== "string" || key === "") return null;
    if (key === " " || key === "Spacebar") return "Space";
    if (key === "Esc") return "Escape";
    if (key.length === 1) return key.toLowerCase(); // "I" (Shift/CapsLock) == "i"
    return key;
  }

  // ---- Tree index ----------------------------------------------------------

  function indexTree(tree) {
    if (!tree || typeof tree !== "object" || Array.isArray(tree)) {
      throw fail("tree-invalid", "Explorer tree must be an object.");
    }
    var byId = new Map();
    // Iterative, so a hostile or broken tree cannot overflow the call stack.
    var stack = [{ node: tree, parent: null, index: 0, level: 1, siblingCount: 1 }];
    while (stack.length) {
      var f = stack.pop();
      var node = f.node;
      if (!node || typeof node !== "object" || Array.isArray(node)) {
        throw fail("tree-invalid", "Explorer node is not an object.");
      }
      if (f.level > MAX_DEPTH) {
        throw fail("tree-too-deep", "Explorer tree is too deep (more than " + MAX_DEPTH + " levels).");
      }
      if (typeof node.id !== "string" || node.id === "") {
        throw fail("tree-invalid", "Explorer node has no id.");
      }
      if (byId.has(node.id)) {
        throw fail("tree-invalid", "Duplicate explorer node id: " + node.id);
      }
      var kids = node.children === undefined ? [] : node.children;
      if (!Array.isArray(kids)) {
        throw fail("tree-invalid", "Explorer node " + node.id + " has invalid children.");
      }
      byId.set(node.id, {
        node: node,
        parent: f.parent,
        index: f.index,
        level: f.level,
        siblingCount: f.siblingCount,
        children: kids,
      });
      for (var i = kids.length - 1; i >= 0; i--) {
        stack.push({ node: kids[i], parent: node, index: i, level: f.level + 1, siblingCount: kids.length });
      }
    }
    return byId;
  }

  // The field's text, or null when it is missing or blank.
  function text(node, field) {
    var value = node && node[field];
    return typeof value === "string" && value.trim() !== "" ? value : null;
  }

  // A meaningful name for a node: its quick text, else a role-based fallback.
  function nameOf(node) {
    var quick = text(node, "spoken_quick");
    if (quick !== null) return quick;
    if (node && typeof node.role === "string" && node.role.trim() !== "") {
      var r = node.role.trim().replace(/_/g, " ");
      return r.charAt(0).toUpperCase() + r.slice(1);
    }
    return MSG.FALLBACK_NAME;
  }

  function missing(kind, node) {
    return "There is no " + kind + " for " + nameOf(node) + ".";
  }

  function isAltGraph(ev) {
    try {
      return typeof ev.getModifierState === "function" && ev.getModifierState("AltGraph") === true;
    } catch (e) {
      return false;
    }
  }

  // Plain keys only (guide rule 2). Exception: AltGr, which Windows reports as
  // Ctrl+Alt, is accepted ONLY when the browser says AltGraph is down and the
  // key is a single printable character. Real Ctrl+x / Alt+x / Meta+x still pass through.
  function modifiersAllowKey(ev) {
    if (ev.metaKey) return false;
    if (!ev.ctrlKey && !ev.altKey) return true;
    var printable = typeof ev.key === "string" && ev.key.length === 1;
    return isAltGraph(ev) && printable && (ev.ctrlKey ? ev.altKey === true : true);
  }

  // ---- Layer 1: controller (pure) -----------------------------------------

  function createController(tree) {
    var index = indexTree(tree); // throws on a malformed tree
    var rootNode = tree;
    var focusId = rootNode.id;
    var open = true;

    function entry() {
      var e = index.get(focusId);
      if (!e) {
        // Should be unreachable; never leave the user without a selection.
        focusId = rootNode.id;
        e = index.get(focusId);
      }
      return e;
    }

    function selection() {
      var e = entry();
      return {
        id: e.node.id,
        name: nameOf(e.node),
        role: e.node.role,
        level: e.level,
        position: e.index + 1,
        setSize: e.siblingCount,
        hasChildren: e.children.length > 0,
      };
    }

    function result(fields) {
      var out = {
        handled: true,
        preventDefault: true,
        action: null,
        ok: true,
        moved: false,
        exit: false,
        announce: null, // text for the live region / page speech
        focusText: null, // text of the newly focused node (spoken by focus, see header)
        focusId: focusId,
        selection: null,
      };
      for (var k in fields) out[k] = fields[k];
      out.focusId = focusId;
      out.selection = selection();
      return out;
    }

    function failure(error) {
      return {
        handled: false,
        preventDefault: false,
        action: "setFocus",
        ok: false,
        error: error,
        moved: false,
        exit: false,
        announce: null,
        focusText: null,
        focusId: focusId,
        selection: selection(),
      };
    }

    function unhandled() {
      return {
        handled: false,
        preventDefault: false,
        action: null,
        ok: true,
        moved: false,
        exit: false,
        announce: null,
        focusText: null,
        focusId: focusId,
        selection: selection(),
      };
    }

    function moveTo(target, action) {
      var changed = target.node.id !== focusId;
      focusId = target.node.id;
      return result({
        action: action,
        moved: changed,
        focusText: nameOf(target.node),
      });
    }

    function stay(action, message) {
      return result({ action: action, announce: message });
    }

    function sibling(action, offset) {
      var e = entry();
      if (e.parent === null || e.siblingCount === 1) return stay(action, MSG.ONLY);
      var siblings = index.get(e.parent.id).children;
      var target = siblings[e.index + offset];
      if (!target) return stay(action, offset < 0 ? MSG.FIRST : MSG.LAST);
      return moveTo(index.get(target.id), action);
    }

    function perform(action) {
      var e = entry();
      switch (action) {
        case "parent":
          return e.parent === null
            ? stay(action, MSG.NO_PARENT)
            : moveTo(index.get(e.parent.id), action);
        case "firstChild":
          return e.children.length === 0
            ? stay(action, nameOf(e.node) + " has nothing inside it.")
            : moveTo(index.get(e.children[0].id), action);
        case "previousSibling":
          return sibling(action, -1);
        case "nextSibling":
          return sibling(action, 1);
        case "root":
          return focusId === rootNode.id
            ? stay(action, MSG.AT_ROOT)
            : moveTo(index.get(rootNode.id), action);
        case "quick":
          return stay(action, nameOf(e.node));
        case "detailed":
          return stay(action, text(e.node, "spoken_detailed") || missing("detailed explanation", e.node));
        case "context":
          return stay(action, text(e.node, "spoken_context") || missing("context", e.node));
        case "readAll":
          // Reads the root's detailed text: its quick text is only "Equation".
          return stay(action, text(rootNode, "spoken_detailed") || missing("detailed explanation", rootNode));
        case "help":
          return stay(action, HELP_TEXT);
        case "exit":
          open = false;
          return result({ action: action, exit: true, announce: MSG.LEFT });
        default:
          return unhandled();
      }
    }

    // Held-key state: the navigation key whose boundary message was already given.
    var lastBoundary = null;

    return {
      /** Handle a keydown-like event {key, ctrlKey, altKey, metaKey, repeat, isComposing}. */
      handleKey: function (ev) {
        if (!open || !ev || typeof ev !== "object") return unhandled();
        if (ev.isComposing || !modifiersAllowKey(ev)) return unhandled();
        var key = normaliseKey(ev.key);
        var action = key !== null && Object.prototype.hasOwnProperty.call(KEY_ACTIONS, key)
          ? KEY_ACTIONS[key]
          : null;
        if (action === null) return unhandled();
        if (!ev.repeat) lastBoundary = null;
        var res = perform(action);
        if (NAV_ACTIONS[action]) {
          if (res.moved) {
            lastBoundary = null; // successful movement repeats silently (focus is the announcement)
          } else {
            // First boundary of a held sequence is announced, repeats are not.
            if (ev.repeat && lastBoundary === action) res.announce = null;
            lastBoundary = action;
          }
        } else if (ev.repeat) {
          res.announce = null; // holding Space / I / C / R / ? must not flood the reader
        }
        return res;
      },
      /** Move focus to a node by id (e.g. user clicked or tabbed into an item). */
      setFocus: function (id) {
        if (!open) return failure("closed");
        var target = typeof id === "string" ? index.get(id) : undefined;
        if (!target) return failure("unknown-node"); // focus unchanged, not "handled"
        lastBoundary = null;
        return moveTo(target, "setFocus");
      },
      /** What to announce when the explorer opens (guide §5). */
      openAnnouncement: function () {
        return "Equation explorer. " +
          (text(rootNode, "spoken_detailed") || nameOf(rootNode) + ".") +
          " Press question mark for keys.";
      },
      /** Re-open: always starts on the whole equation (guide §3). */
      reset: function () {
        var moved = focusId !== rootNode.id;
        focusId = rootNode.id;
        open = true;
        lastBoundary = null;
        return result({ action: "reset", moved: moved, focusText: nameOf(rootNode) });
      },
      /** Stop responding to keys (used by the view on destroy). */
      close: function () {
        open = false;
      },
      isOpen: function () {
        return open;
      },
      getFocusId: function () {
        return focusId;
      },
      getSelection: selection,
      has: function (id) {
        return index.has(id);
      },
    };
  }

  // ---- Layer 2: DOM adapter (thin, needs a real browser to verify) ---------

  var SR_ONLY =
    "position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;" +
    "clip:rect(0 0 0 0);white-space:nowrap;border:0;";

  var views = new WeakMap(); // container -> its live view (at most one)

  function isFn(v) {
    return typeof v === "function";
  }

  function restoreAttr(el, name, previous) {
    if (previous === null || previous === undefined) {
      if (isFn(el.removeAttribute)) el.removeAttribute(name);
    } else {
      el.setAttribute(name, previous);
    }
  }

  /**
   * options:
   *   onExit()      REQUIRED. Called after Esc. The page must move focus to the
   *                 Explore button here (no fallback target is invented).
   *   document      defaults to global document
   *   mode          "screen-reader" (default) | "speech"
   *   speak(text)   needed for "speech" mode. Without it the view falls back to
   *                 "screen-reader" and reports view.modeFallback.
   *   cancelSpeech() optional; errors from it are ignored
   *   liveRegion    an existing aria-live element (not removed on destroy)
   *   helpPanel     an existing element to hold the visible key list (not removed on destroy)
   *   schedule(fn)  defaults to setTimeout(fn, 50); lets tests run synchronously
   *
   * The container must be attached to the DOM and visible when open() is called,
   * and (unless both liveRegion and helpPanel are supplied) must have a parentNode,
   * which receives the live region and help panel. Existing children of the
   * container are left alone and survive destroy().
   */
  function createView(container, tree, options) {
    options = options || {};
    if (!container || !isFn(container.setAttribute) || !isFn(container.appendChild) ||
        !isFn(container.addEventListener) || !isFn(container.removeEventListener)) {
      throw fail("container-invalid", "createView needs a DOM element as the tree container.");
    }
    if (!isFn(options.onExit)) {
      throw fail("options-invalid",
        "createView requires an onExit callback that moves focus to the Explore button.");
    }
    if (options.mode !== undefined && options.mode !== "screen-reader" && options.mode !== "speech") {
      throw fail("options-invalid", 'mode must be "screen-reader" or "speech".');
    }
    ["speak", "cancelSpeech", "schedule"].forEach(function (name) {
      if (options[name] !== undefined && !isFn(options[name])) {
        throw fail("options-invalid", name + " must be a function.");
      }
    });
    var doc = options.document || (typeof document !== "undefined" ? document : null);
    if (!doc) throw fail("options-invalid", "No document available.");
    var host = container.parentNode;
    if ((!options.liveRegion || !options.helpPanel) && !host) {
      throw fail("container-invalid",
        "The tree container must be attached to the page (it needs a parent for the live region and help panel).");
    }

    var controller = createController(tree); // validates the tree; nothing touched yet

    var mode = options.mode === "speech" ? "speech" : "screen-reader";
    var modeFallback = null;
    if (mode === "speech" && !isFn(options.speak)) {
      mode = "screen-reader";
      modeFallback = "speech mode needs a speak() function; using the live region instead.";
    }
    var schedule = options.schedule || function (fn) { setTimeout(fn, 50); };

    // Replace any previous view on this container (after validation, so a bad
    // tree leaves the old view working).
    var previous = views.get(container);
    if (previous) previous.destroy();

    var destroyed = false;
    var items = new Map(); // node id -> treeitem element
    var prevRole = container.getAttribute ? container.getAttribute("role") : null;
    var prevLabel = container.getAttribute ? container.getAttribute("aria-label") : null;

    function build(node, level, pos, size) {
      var name = nameOf(node);
      var li = doc.createElement("li");
      li.setAttribute("role", "treeitem");
      li.setAttribute("id", "explorer-" + node.id);
      li.setAttribute("data-node-id", node.id);
      li.setAttribute("aria-label", name);
      li.setAttribute("aria-level", String(level));
      li.setAttribute("aria-posinset", String(pos));
      li.setAttribute("aria-setsize", String(size));
      li.setAttribute("aria-selected", "false");
      li.setAttribute("tabindex", "-1");
      var label = doc.createElement("span");
      label.textContent = name;
      li.appendChild(label);
      var kids = node.children || [];
      if (kids.length) {
        li.setAttribute("aria-expanded", "true");
        var group = doc.createElement("ul");
        group.setAttribute("role", "group");
        kids.forEach(function (child, i) {
          group.appendChild(build(child, level + 1, i + 1, kids.length));
        });
        li.appendChild(group);
      }
      items.set(node.id, li);
      return li;
    }

    container.setAttribute("role", "tree");
    container.setAttribute("aria-label", "Equation explorer");
    var rootList = doc.createElement("ul");
    rootList.setAttribute("role", "none");
    rootList.appendChild(build(tree, 1, 1, 1));
    container.appendChild(rootList);

    var live = options.liveRegion;
    var ownsLive = !live;
    if (ownsLive) {
      live = doc.createElement("div");
      live.setAttribute("aria-live", "polite");
      live.setAttribute("aria-atomic", "true");
      live.setAttribute("style", SR_ONLY);
      host.appendChild(live);
    }

    var help = options.helpPanel;
    var ownsHelp = !help;
    var prevHelpHidden = help ? help.hidden : true;
    if (ownsHelp) {
      help = doc.createElement("div");
      help.setAttribute("aria-label", "Explorer keys");
      help.setAttribute("role", "group");
      host.appendChild(help);
    }
    help.hidden = true;
    var helpList = doc.createElement("ul");
    HELP_ITEMS.forEach(function (pair) {
      var item = doc.createElement("li");
      item.textContent = pair[0] + ": " + pair[1] + ".";
      helpList.appendChild(item);
    });
    help.appendChild(helpList);

    function writeLive(t) {
      // Clear first so identical text (Space twice) is announced again.
      live.textContent = "";
      schedule(function () {
        if (!destroyed) live.textContent = t;
      });
    }

    // Exactly one channel per announcement.
    function say(t) {
      if (!t || destroyed) return;
      if (mode === "speech") {
        try {
          if (options.cancelSpeech) options.cancelSpeech();
        } catch (e) { /* a failing cancel must not block speaking */ }
        try {
          options.speak(t);
          return;
        } catch (e) { /* speak failed, nothing was spoken: use the live region instead */ }
      }
      writeLive(t);
    }

    function focusItem(el) {
      el.focus({ preventScroll: true });
      if (isFn(el.scrollIntoView)) {
        try { el.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch (e) { /* optional */ }
      }
    }

    function syncSelection() {
      var current = controller.getFocusId();
      items.forEach(function (el, id) {
        var on = id === current;
        el.setAttribute("tabindex", on ? "0" : "-1");
        el.setAttribute("aria-selected", on ? "true" : "false");
        // Style hook so Member 5 can draw a non-colour-only indicator.
        el.setAttribute("data-selected", on ? "true" : "false");
      });
    }

    function leaveTabOrder() {
      items.forEach(function (el) { el.setAttribute("tabindex", "-1"); });
    }

    function apply(res) {
      help.hidden = res.action !== "help";
      if (res.moved) {
        syncSelection();
        var el = items.get(res.focusId);
        if (el && doc.activeElement !== el) focusItem(el);
        // In screen-reader mode the focus event is what gets spoken.
        if (mode === "speech") say(res.focusText);
      }
      if (res.announce) say(res.announce);
      if (res.exit) {
        leaveTabOrder(); // a closed tree must not be a Tab stop
        options.onExit();
      }
    }

    function onKeydown(ev) {
      if (destroyed) return;
      var res = controller.handleKey(ev);
      if (res.preventDefault) ev.preventDefault();
      if (res.handled) apply(res);
    }

    // Keep state consistent if focus arrives another way (Tab, click).
    function onFocusin(ev) {
      if (destroyed) return;
      var target = ev.target;
      var id = target && target.getAttribute && target.getAttribute("data-node-id");
      if (id && id !== controller.getFocusId() && controller.isOpen()) {
        if (controller.setFocus(id).ok) syncSelection();
      }
    }

    container.addEventListener("keydown", onKeydown);
    container.addEventListener("focusin", onFocusin);
    leaveTabOrder(); // not a Tab stop until open() is called

    var view = {
      controller: controller,
      mode: mode,
      modeFallback: modeFallback,
      liveRegion: live,
      helpPanel: help,
      /**
       * Open: focus goes to the whole equation, then the opening text is announced
       * (guide §3, §5). Returns the controller result plus `focused`, which is false
       * when the browser did not move focus (for example the container is hidden).
       */
      open: function () {
        if (destroyed) throw fail("destroyed", "This explorer view was destroyed.");
        var res = controller.reset();
        help.hidden = true;
        syncSelection();
        var el = items.get(res.focusId);
        if (el) focusItem(el);
        res.focused = !!el && doc.activeElement === el;
        say(controller.openAnnouncement());
        return res;
      },
      isDestroyed: function () {
        return destroyed;
      },
      /** Remove everything this view added. Safe to call more than once. */
      destroy: function () {
        if (destroyed) return;
        destroyed = true;
        controller.close();
        container.removeEventListener("keydown", onKeydown);
        container.removeEventListener("focusin", onFocusin);
        if (isFn(container.removeChild) && rootList.parentNode === container) {
          container.removeChild(rootList);
        }
        restoreAttr(container, "role", prevRole);
        restoreAttr(container, "aria-label", prevLabel);
        if (ownsLive) {
          if (live.parentNode && isFn(live.parentNode.removeChild)) live.parentNode.removeChild(live);
        } else {
          live.textContent = "";
        }
        if (ownsHelp) {
          if (help.parentNode && isFn(help.parentNode.removeChild)) help.parentNode.removeChild(help);
        } else {
          if (helpList.parentNode === help && isFn(help.removeChild)) help.removeChild(helpList);
          help.hidden = prevHelpHidden;
        }
        items.clear();
        if (views.get(container) === view) views.delete(container);
      },
    };
    views.set(container, view);
    return view;
  }

  return {
    createController: createController,
    createView: createView,
    HELP_ITEMS: HELP_ITEMS,
    HELP_TEXT: HELP_TEXT,
    KEY_ACTIONS: KEY_ACTIONS,
    MESSAGES: MSG,
    MAX_DEPTH: MAX_DEPTH,
  };
});
