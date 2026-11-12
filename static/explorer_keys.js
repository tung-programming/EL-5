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
 * `tree` is the ExplorerNode tree from engine/explore.py (plan.md §10):
 *   {id, type, role, value, spoken_quick, spoken_detailed, spoken_context, children[]}
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
 *   announced twice.
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

  var MSG = {
    NO_PARENT: "This is the whole equation. There is nothing bigger.",
    FIRST: "This is the first part at this level.",
    LAST: "This is the last part at this level.",
    ONLY: "This is the only part at this level.",
    AT_ROOT: "Already at the whole equation.",
    LEFT: "Left the explorer.",
    NO_TEXT: "No explanation is available for this part.",
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
      throw new Error("Explorer tree must be an object.");
    }
    var byId = new Map();
    (function visit(node, parent, index, level, siblingCount) {
      if (!node || typeof node !== "object") {
        throw new Error("Explorer node is not an object.");
      }
      if (typeof node.id !== "string" || node.id === "") {
        throw new Error("Explorer node has no id.");
      }
      if (byId.has(node.id)) {
        throw new Error("Duplicate explorer node id: " + node.id);
      }
      var kids = node.children === undefined ? [] : node.children;
      if (!Array.isArray(kids)) {
        throw new Error("Explorer node " + node.id + " has invalid children.");
      }
      byId.set(node.id, {
        node: node,
        parent: parent,
        index: index,
        level: level,
        siblingCount: siblingCount,
        children: kids,
      });
      kids.forEach(function (child, i) {
        visit(child, node, i, level + 1, kids.length);
      });
    })(tree, null, 0, 1, 1);
    return byId;
  }

  function text(node, field) {
    var value = node && node[field];
    return typeof value === "string" && value.trim() !== "" ? value : MSG.NO_TEXT;
  }

  function shortName(node) {
    if (typeof node.spoken_quick === "string" && node.spoken_quick.trim() !== "") {
      return node.spoken_quick;
    }
    if (typeof node.role === "string" && node.role !== "") {
      return node.role.replace(/_/g, " ");
    }
    return "This part";
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
        name: shortName(e.node),
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
        focusText: text(target.node, "spoken_quick"),
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
            ? stay(action, shortName(e.node) + " has nothing inside it.")
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
          return stay(action, text(e.node, "spoken_quick"));
        case "detailed":
          return stay(action, text(e.node, "spoken_detailed"));
        case "context":
          return stay(action, text(e.node, "spoken_context"));
        case "readAll":
          // Reads the root's detailed text: its quick text is only "Equation".
          return stay(action, text(rootNode, "spoken_detailed"));
        case "help":
          return stay(action, HELP_TEXT);
        case "exit":
          open = false;
          return result({ action: action, exit: true, announce: MSG.LEFT });
        default:
          return unhandled();
      }
    }

    return {
      /** Handle a keydown-like event {key, ctrlKey, altKey, metaKey, repeat, isComposing}. */
      handleKey: function (ev) {
        if (!open || !ev || typeof ev !== "object") return unhandled();
        if (ev.ctrlKey || ev.altKey || ev.metaKey || ev.isComposing) return unhandled();
        var key = normaliseKey(ev.key);
        var action = key !== null && Object.prototype.hasOwnProperty.call(KEY_ACTIONS, key)
          ? KEY_ACTIONS[key]
          : null;
        if (action === null) return unhandled();
        var res = perform(action);
        // Holding a key must not queue the same message over and over.
        // Movement still repeats; the key is still swallowed (preventDefault).
        if (ev.repeat && !res.moved) res.announce = null;
        return res;
      },
      /** Move focus to a node by id (e.g. user clicked or tabbed into an item). */
      setFocus: function (id) {
        if (!open) return unhandled();
        var target = typeof id === "string" ? index.get(id) : undefined;
        if (!target) {
          var res = result({ action: "setFocus", ok: false });
          return res; // focus unchanged
        }
        return moveTo(target, "setFocus");
      },
      /** What to announce when the explorer opens (guide §5). */
      openAnnouncement: function () {
        return "Equation explorer. " + text(rootNode, "spoken_detailed") +
          " Press question mark for keys.";
      },
      /** Re-open: always starts on the whole equation (guide §3). */
      reset: function () {
        focusId = rootNode.id;
        open = true;
        return result({ action: "reset", focusText: text(rootNode, "spoken_quick") });
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

  /**
   * options:
   *   document     defaults to global document
   *   mode         "screen-reader" (default) | "speech"
   *   speak(text)  required in "speech" mode; cancelSpeech() optional
   *   liveRegion   an existing aria-live element; created if omitted
   *   onExit()     called after Esc; Member 5 moves focus to the Explore button
   *   schedule(fn) defaults to setTimeout(fn, 50); lets tests run synchronously
   */
  function createView(container, tree, options) {
    options = options || {};
    var doc = options.document || document;
    var mode = options.mode === "speech" ? "speech" : "screen-reader";
    var schedule = options.schedule || function (fn) { setTimeout(fn, 50); };
    var controller = createController(tree);
    var items = new Map(); // node id -> treeitem element

    function build(node, level, pos, size) {
      var li = doc.createElement("li");
      li.setAttribute("role", "treeitem");
      li.setAttribute("id", "explorer-" + node.id);
      li.setAttribute("data-node-id", node.id);
      li.setAttribute("aria-label", text(node, "spoken_quick"));
      li.setAttribute("aria-level", String(level));
      li.setAttribute("aria-posinset", String(pos));
      li.setAttribute("aria-setsize", String(size));
      li.setAttribute("aria-selected", "false");
      li.setAttribute("tabindex", "-1");
      var label = doc.createElement("span");
      label.textContent = text(node, "spoken_quick");
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
    if (!live) {
      live = doc.createElement("div");
      live.setAttribute("aria-live", "polite");
      live.setAttribute("aria-atomic", "true");
      live.setAttribute("style", SR_ONLY);
      if (container.parentNode) container.parentNode.appendChild(live);
    }

    var help = doc.createElement("div");
    help.setAttribute("aria-label", "Explorer keys");
    help.setAttribute("role", "group");
    help.hidden = true;
    var list = doc.createElement("ul");
    HELP_ITEMS.forEach(function (pair) {
      var item = doc.createElement("li");
      item.textContent = pair[0] + ": " + pair[1] + ".";
      list.appendChild(item);
    });
    help.appendChild(list);
    if (container.parentNode) container.parentNode.appendChild(help);

    function say(textToSay) {
      if (!textToSay) return;
      if (mode === "speech") {
        if (options.cancelSpeech) options.cancelSpeech();
        if (options.speak) options.speak(textToSay);
        return;
      }
      // Clear first so identical text (Space twice) is announced again.
      live.textContent = "";
      schedule(function () {
        live.textContent = textToSay;
      });
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

    function apply(res) {
      if (res.action !== "help" && res.handled) help.hidden = true;
      if (res.action === "help") help.hidden = false;
      if (res.moved || res.action === "setFocus") {
        syncSelection();
        var el = items.get(res.focusId);
        if (el && res.moved && doc.activeElement !== el) el.focus();
        // In screen-reader mode the focus event is what gets spoken.
        if (mode === "speech" && res.moved) say(res.focusText);
      }
      if (res.announce) say(res.announce);
      if (res.exit) {
        help.hidden = true;
        if (options.onExit) options.onExit();
      }
    }

    container.addEventListener("keydown", function (ev) {
      var res = controller.handleKey(ev);
      if (res.preventDefault) ev.preventDefault();
      if (res.handled) apply(res);
    });

    // Keep state consistent if focus arrives another way (Tab, click).
    container.addEventListener("focusin", function (ev) {
      var target = ev.target;
      var id = target && target.getAttribute && target.getAttribute("data-node-id");
      if (id && id !== controller.getFocusId() && controller.isOpen()) {
        controller.setFocus(id);
        syncSelection();
      }
    });

    syncSelection();

    return {
      controller: controller,
      /** Open: focus goes to the whole equation, then announce (guide §3, §5). */
      open: function () {
        var res = controller.reset();
        help.hidden = true;
        syncSelection();
        var el = items.get(res.focusId);
        if (el) el.focus();
        say(controller.openAnnouncement());
        return res;
      },
      liveRegion: live,
      helpPanel: help,
    };
  }

  return {
    createController: createController,
    createView: createView,
    HELP_ITEMS: HELP_ITEMS,
    HELP_TEXT: HELP_TEXT,
    KEY_ACTIONS: KEY_ACTIONS,
    MESSAGES: MSG,
  };
});
