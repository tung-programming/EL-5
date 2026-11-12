// Tests for static/explorer_keys.js. Owner: Member 4.
// Run: node --test tests/js/        (Node 18+, no dependencies)
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const EK = require("../../static/explorer_keys.js");
const TREES = require("./explorer_trees.json");

const key = (k, extra) => Object.assign({ key: k }, extra || {});
const T = TREES["3x+5=14"];
// n0 Equation
//  n0.0 Left side  -> n0.0.0 Multiplication (n0.0.0.0 coefficient 3, n0.0.0.1 variable x), n0.0.1 constant 5
//  n0.1 Right side (leaf)
function at(id, tree) {
  const c = EK.createController(tree || T);
  if (id !== "n0") assert.equal(c.setFocus(id).ok, true);
  return c;
}
function find(node, id) {
  if (node.id === id) return node;
  for (const k of node.children) { const r = find(k, id); if (r) return r; }
  return null;
}

// ---- every planned key ----------------------------------------------------

test("key map covers exactly the planned keys", () => {
  assert.deepEqual(Object.keys(EK.KEY_ACTIONS).sort(),
    ["?", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowUp", "Escape", "Home", "Space", "c", "i", "r"].sort());
});

test("ArrowDown moves to first child", () => {
  const c = at("n0");
  const r = c.handleKey(key("ArrowDown"));
  assert.equal(r.focusId, "n0.0"); assert.equal(r.moved, true);
  assert.equal(c.getFocusId(), "n0.0");
  assert.equal(c.handleKey(key("ArrowDown")).focusId, "n0.0.0");
});

test("ArrowUp moves to parent", () => {
  const c = at("n0.0.0.1");
  assert.equal(c.handleKey(key("ArrowUp")).focusId, "n0.0.0");
  assert.equal(c.handleKey(key("ArrowUp")).focusId, "n0.0");
});

test("ArrowRight / ArrowLeft move between siblings in order", () => {
  const c = at("n0.0.0.0");
  assert.equal(c.handleKey(key("ArrowRight")).focusId, "n0.0.0.1");
  assert.equal(c.handleKey(key("ArrowLeft")).focusId, "n0.0.0.0");
  const d = at("n0.0");
  assert.equal(d.handleKey(key("ArrowRight")).focusId, "n0.1");
});

test("Home returns to root from anywhere", () => {
  const c = at("n0.0.0.1");
  const r = c.handleKey(key("Home"));
  assert.equal(r.focusId, "n0"); assert.equal(r.moved, true);
});

test("Space / I / C read quick, detailed, context of the focused node", () => {
  const c = at("n0.0.1");
  const n = find(T, "n0.0.1");
  assert.equal(c.handleKey(key(" ")).announce, n.spoken_quick);
  assert.equal(c.handleKey(key("i")).announce, n.spoken_detailed);
  assert.equal(c.handleKey(key("c")).announce, n.spoken_context);
});

test("R reads the whole equation and does not move focus", () => {
  const c = at("n0.0.1");
  const r = c.handleKey(key("r"));
  assert.equal(r.announce, T.spoken_detailed);
  assert.match(r.announce, /3x plus 5/);
  assert.equal(r.moved, false); assert.equal(c.getFocusId(), "n0.0.1");
});

test("? announces the key list and does not move focus", () => {
  const c = at("n0.0.1");
  const r = c.handleKey(key("?", { shiftKey: true }));
  assert.equal(r.announce, EK.HELP_TEXT);
  assert.equal(c.getFocusId(), "n0.0.1");
  for (const w of ["Up arrow", "Down arrow", "Left and right", "Space", "I:", "C:", "R:", "Home", "Escape"]) {
    assert.ok(EK.HELP_TEXT.includes(w), w);
  }
  assert.equal(c.handleKey(key("?")).announce, EK.HELP_TEXT); // repeat is fine
});

test("Escape exits once, then the controller ignores keys until reset", () => {
  const c = at("n0.0.1");
  const r = c.handleKey(key("Escape"));
  assert.equal(r.exit, true); assert.equal(r.announce, "Left the explorer.");
  assert.equal(c.isOpen(), false);
  assert.equal(c.handleKey(key("Escape")).handled, false);
  assert.equal(c.handleKey(key("ArrowDown")).handled, false);
  const re = c.reset();
  assert.equal(re.focusId, "n0"); assert.equal(c.isOpen(), true);
  assert.equal(c.handleKey(key("ArrowDown")).focusId, "n0.0");
});

// ---- boundaries -----------------------------------------------------------

test("boundaries: stay put and say so", () => {
  let c = at("n0");
  let r = c.handleKey(key("ArrowUp"));
  assert.equal(r.announce, "This is the whole equation. There is nothing bigger.");
  assert.equal(r.moved, false); assert.equal(r.focusId, "n0");

  assert.equal(c.handleKey(key("Home")).announce, "Already at the whole equation.");

  c = at("n0.1"); // Right side, leaf
  r = c.handleKey(key("ArrowDown"));
  assert.equal(r.announce, "Right side has nothing inside it.");
  assert.equal(r.focusId, "n0.1");
  assert.equal(c.handleKey(key("ArrowRight")).announce, "This is the last part at this level.");

  c = at("n0.0");
  assert.equal(c.handleKey(key("ArrowLeft")).announce, "This is the first part at this level.");
  assert.equal(c.getFocusId(), "n0.0");
});

test("root has no siblings: left/right say it is the only part", () => {
  const c = at("n0");
  assert.equal(c.handleKey(key("ArrowLeft")).announce, "This is the only part at this level.");
  assert.equal(c.handleKey(key("ArrowRight")).announce, "This is the only part at this level.");
});

test("only child: left and right both say only part", () => {
  const g = TREES["2(x+3)=12"]; // Group has one child
  const c = EK.createController(g);
  c.setFocus("n0.0.1.0");
  assert.equal(c.handleKey(key("ArrowLeft")).announce, "This is the only part at this level.");
  assert.equal(c.handleKey(key("ArrowRight")).announce, "This is the only part at this level.");
  assert.equal(c.getFocusId(), "n0.0.1.0");
});

test("no wrap-around at either end", () => {
  const c = at("n0.0.0.1");
  c.handleKey(key("ArrowRight"));
  assert.equal(c.getFocusId(), "n0.0.0.1");
  const d = at("n0.0.0.0");
  d.handleKey(key("ArrowLeft"));
  assert.equal(d.getFocusId(), "n0.0.0.0");
});

// ---- movement is spoken once ---------------------------------------------

test("movement produces focusText but no announce (no double speech)", () => {
  const c = at("n0");
  const r = c.handleKey(key("ArrowDown"));
  assert.equal(r.announce, null);
  assert.equal(r.focusText, find(T, "n0.0").spoken_quick);
});

test("selection describes level, position and name", () => {
  const c = at("n0.0.0.1");
  const s = c.getSelection();
  assert.equal(s.level, 4); assert.equal(s.position, 2); assert.equal(s.setSize, 2);
  assert.equal(s.name, find(T, "n0.0.0.1").spoken_quick);
  assert.equal(c.handleKey(key("ArrowUp")).selection.level, 3);
});

// ---- unsupported / modifier / invalid ------------------------------------

test("unsupported keys are ignored silently and not swallowed", () => {
  const c = at("n0.0");
  for (const k of ["a", "Tab", "Enter", "x", "F1", "Shift", "PageDown", "End", "1", "/", "Backspace"]) {
    const r = c.handleKey(key(k));
    assert.equal(r.handled, false, k); assert.equal(r.preventDefault, false, k);
    assert.equal(r.announce, null, k); assert.equal(r.moved, false, k);
  }
  assert.equal(c.getFocusId(), "n0.0");
});

test("Ctrl/Alt/Meta combinations are passed through", () => {
  const c = at("n0.0");
  for (const m of ["ctrlKey", "altKey", "metaKey"]) {
    for (const k of ["ArrowDown", " ", "i", "c", "r", "Home", "?", "Escape"]) {
      const r = c.handleKey(key(k, { [m]: true }));
      assert.equal(r.handled, false, m + k);
      assert.equal(r.preventDefault, false, m + k);
    }
  }
  assert.equal(c.getFocusId(), "n0.0");
});

test("Shift is ignored except for ?; capital letters work", () => {
  const c = at("n0.0");
  assert.equal(c.handleKey(key("ArrowDown", { shiftKey: true })).moved, true);
  assert.equal(c.handleKey(key("I", { shiftKey: true })).announce, find(T, "n0.0.0").spoken_detailed);
  assert.equal(c.handleKey(key("C")).announce, find(T, "n0.0.0").spoken_context);
});

test("legacy key names Spacebar and Esc work", () => {
  const c = at("n0.0");
  assert.equal(c.handleKey(key("Spacebar")).action, "quick");
  assert.equal(c.handleKey(key("Esc")).exit, true);
});

test("IME composition is ignored", () => {
  assert.equal(at("n0").handleKey(key("i", { isComposing: true })).handled, false);
});

test("malformed events never throw and are unhandled", () => {
  const c = at("n0");
  for (const ev of [null, undefined, {}, { key: null }, { key: "" }, { key: 5 }, "ArrowDown", []]) {
    const r = c.handleKey(ev);
    assert.equal(r.handled, false);
  }
  assert.equal(c.getFocusId(), "n0");
  // inherited property names must not count as keys
  assert.equal(c.handleKey(key("constructor")).handled, false);
  assert.equal(c.handleKey(key("toString")).handled, false);
});

// ---- invalid / missing node, focus preservation --------------------------

test("setFocus with unknown, missing or non-string id leaves focus unchanged", () => {
  const c = at("n0.0.1");
  for (const id of ["nope", "", undefined, null, 5, {}]) {
    const r = c.setFocus(id);
    assert.equal(r.ok, false);
    assert.equal(r.focusId, "n0.0.1");
    assert.equal(r.moved, false);
  }
  assert.equal(c.getFocusId(), "n0.0.1");
});

test("missing spoken text falls back to the role, never a generic message", () => {
  const tree = { id: "a", role: "equation", children: [{ id: "b", role: "left_side", spoken_quick: "", children: [] }] };
  const c = EK.createController(tree);
  assert.equal(c.handleKey(key(" ")).announce, "Equation");
  const down = c.handleKey(key("ArrowDown"));
  assert.equal(down.focusText, "Left side");
  assert.equal(c.getSelection().name, "Left side");
  assert.equal(c.handleKey(key(" ")).announce, "Left side"); // quick falls back to the role name
  assert.equal(c.handleKey(key("i")).announce, "There is no detailed explanation for Left side.");
  assert.equal(c.handleKey(key("c")).announce, "There is no context for Left side.");
  assert.equal(c.handleKey(key("ArrowDown")).announce, "Left side has nothing inside it.");
  c.setFocus("a");
  assert.equal(c.handleKey(key("r")).announce, "There is no detailed explanation for Equation.");
  assert.match(c.openAnnouncement(), /^Equation explorer\. Equation\. Press question mark/);
});

test("a node with no role and no text still gets a non-empty name", () => {
  const c = EK.createController({ id: "a", spoken_quick: 5, role: 7 });
  assert.equal(c.handleKey(key(" ")).announce, EK.MESSAGES.FALLBACK_NAME);
  assert.equal(c.getSelection().name, EK.MESSAGES.FALLBACK_NAME);
});

test("a node with no children field is a leaf", () => {
  const c = EK.createController({ id: "a", spoken_quick: "Equation" });
  assert.equal(c.handleKey(key("ArrowDown")).announce, "Equation has nothing inside it.");
});

test("malformed trees are rejected up front", () => {
  for (const bad of [null, undefined, 5, "x", [], {}, { id: "" },
    { id: "a", children: "no" }, { id: "a", children: [null] },
    { id: "a", children: [{ id: "a", children: [] }] }]) {
    assert.throws(() => EK.createController(bad), /Explorer|Duplicate/);
  }
});

test("focus is preserved across every handled non-movement key", () => {
  const c = at("n0.0.0.1");
  for (const k of [" ", "i", "c", "r", "?", "ArrowDown", "ArrowRight"]) {
    c.handleKey(key(k));
    assert.equal(c.getFocusId(), "n0.0.0.1", k);
  }
});

// ---- repeated key presses -------------------------------------------------

test("repeated presses: reading keys re-announce, held keys do not queue", () => {
  const c = at("n0.0.1");
  assert.equal(c.handleKey(key(" ")).announce, c.handleKey(key(" ")).announce);
  const held = c.handleKey(key("?", { repeat: true }));
  assert.equal(held.announce, null); assert.equal(held.preventDefault, true);
  assert.equal(c.getFocusId(), "n0.0.1");
});

test("holding an arrow keeps moving and stops at the boundary", () => {
  const c = at("n0");
  let last;
  for (let i = 0; i < 10; i++) last = c.handleKey(key("ArrowDown", { repeat: i > 0 }));
  assert.equal(c.getFocusId(), "n0.0.0.0");
  assert.equal(last.moved, false);
});

test("Home twice, Up from root many times: stable", () => {
  const c = at("n0.0.0.0");
  c.handleKey(key("Home")); c.handleKey(key("Home"));
  for (let i = 0; i < 5; i++) c.handleKey(key("ArrowUp"));
  assert.equal(c.getFocusId(), "n0");
});

test("open announcement, root detailed text, and reset to root", () => {
  const c = at("n0.0.1");
  assert.match(c.openAnnouncement(), /^Equation explorer\. The whole equation/);
  assert.match(c.openAnnouncement(), /Press question mark for keys\.$/);
  assert.equal(c.reset().focusId, "n0");
});

// ---- every real tree: full traversal reaches each node exactly once ------

test("depth-first traversal with arrows visits every node of every fixture", () => {
  for (const [name, tree] of Object.entries(TREES)) {
    const all = []; (function w(n) { all.push(n.id); n.children.forEach(w); })(tree);
    const c = EK.createController(tree);
    const seen = [c.getFocusId()];
    // pre-order walk using only Down / Right / Up
    for (let guard = 0; guard < 1000; guard++) {
      if (c.handleKey(key("ArrowDown")).moved) { seen.push(c.getFocusId()); continue; }
      let advanced = false;
      while (true) {
        if (c.handleKey(key("ArrowRight")).moved) { seen.push(c.getFocusId()); advanced = true; break; }
        if (!c.handleKey(key("ArrowUp")).moved) break;
      }
      if (!advanced) break;
    }
    assert.deepEqual(seen, all, name);
    for (const id of all) { // every node has all three depths from the real explorer
      c.setFocus(id);
      for (const k of [" ", "i", "c"]) {
        const a = c.handleKey(key(k)).announce;
        assert.ok(a && a !== EK.MESSAGES.NO_TEXT, name + id + k);
      }
    }
  }
});

// ---- Layer 2: DOM adapter against a minimal fake DOM ---------------------

class El {
  constructor(tag, doc) {
    this.tag = tag; this.doc = doc; this.attrs = {}; this.children = []; this.parentNode = null;
    this.listeners = {}; this._text = ""; this.hidden = false;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  removeAttribute(k) { delete this.attrs[k]; }
  removeChild(c) { this.children = this.children.filter((x) => x !== c); c.parentNode = null; return c; }
  removeEventListener(t, fn) { this.listeners[t] = (this.listeners[t] || []).filter((f) => f !== fn); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  set textContent(v) { this._text = v; }
  get textContent() { return this._text; }
  focus(opts) {
    if (this.doc.activeElement === this) return; // like a browser: no focusin if already focused
    this.doc.focusOpts.push(opts);
    this.doc.activeElement = this;
    this.doc.focusLog.push(this.attrs["data-node-id"]);
    this.dispatch("focusin", { target: this });
  }
  dispatch(type, ev) {
    ev = Object.assign({ defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, ev);
    // like the DOM, events bubble from the target up to its ancestors
    for (let el = this; el; el = el.parentNode) {
      for (const fn of el.listeners[type] || []) fn(ev);
    }
    return ev;
  }
}
function fakeDoc() {
  const doc = { activeElement: null, focusLog: [], focusOpts: [], createElement: (t) => new El(t, doc) };
  return doc;
}
function mount(tree, opts) {
  const doc = fakeDoc();
  const page = new El("div", doc);
  const tc = page.appendChild(new El("div", doc));
  const view = EK.createView(tc, tree, Object.assign({ document: doc, schedule: (f) => f(), onExit() {} }, opts));
  const items = [];
  (function walk(el) { if (el.attrs.role === "treeitem") items.push(el); el.children.forEach(walk); })(tc);
  const byId = Object.fromEntries(items.map((e) => [e.attrs["data-node-id"], e]));
  const press = (k, extra) => tc.dispatch("keydown", Object.assign({ key: k }, extra || {}));
  return { doc, page, tc, view, byId, press };
}

test("view: ARIA tree structure, names, levels, expanded, roving tabindex", () => {
  const m = mount(T);
  assert.equal(m.tc.attrs.role, "tree");
  assert.equal(m.tc.attrs["aria-label"], "Equation explorer");
  const left = m.byId["n0.0"];
  assert.equal(left.attrs["aria-label"], find(T, "n0.0").spoken_quick);
  assert.equal(left.attrs["aria-level"], "2");
  assert.equal(left.attrs["aria-posinset"], "1");
  assert.equal(left.attrs["aria-setsize"], "2");
  assert.equal(left.attrs["aria-expanded"], "true");
  assert.equal(m.byId["n0.1"].attrs["aria-expanded"], undefined); // leaf
  const zero0 = Object.values(m.byId).filter((e) => e.attrs.tabindex === "0");
  assert.equal(zero0.length, 0); // not a Tab stop until open()
  m.view.open();
  const zero = Object.values(m.byId).filter((e) => e.attrs.tabindex === "0");
  assert.equal(zero.length, 1); assert.equal(zero[0].attrs["data-node-id"], "n0");
  assert.ok(m.view.liveRegion.attrs["aria-live"] === "polite");
});

test("view: open focuses root and announces once through the live region", () => {
  const m = mount(T);
  m.view.open();
  assert.equal(m.doc.activeElement, m.byId["n0"]);
  assert.match(m.view.liveRegion.textContent, /^Equation explorer\./);
});

test("view: arrows move DOM focus + roving tabindex, live region NOT written", () => {
  const m = mount(T); m.view.open();
  const before = m.view.liveRegion.textContent;
  const ev = m.press("ArrowDown");
  assert.equal(ev.defaultPrevented, true);
  assert.equal(m.doc.activeElement, m.byId["n0.0"]);
  assert.equal(m.byId["n0.0"].attrs.tabindex, "0");
  assert.equal(m.byId["n0"].attrs.tabindex, "-1");
  assert.equal(m.byId["n0.0"].attrs["aria-selected"], "true");
  assert.equal(m.byId["n0.0"].attrs["data-selected"], "true");
  assert.equal(m.view.liveRegion.textContent, before); // focus is the announcement
});

test("view: Space/I/C go to live region; boundary keeps focus", () => {
  const m = mount(T); m.view.open();
  m.press("ArrowDown"); m.press("ArrowDown"); m.press("ArrowDown"); // coefficient 3
  assert.equal(m.doc.activeElement, m.byId["n0.0.0.0"]);
  m.press("i");
  assert.equal(m.view.liveRegion.textContent, find(T, "n0.0.0.0").spoken_detailed);
  m.press("c");
  assert.equal(m.view.liveRegion.textContent, find(T, "n0.0.0.0").spoken_context);
  m.press("ArrowLeft");
  assert.equal(m.view.liveRegion.textContent, "This is the first part at this level.");
  assert.equal(m.doc.activeElement, m.byId["n0.0.0.0"]);
});

test("view: ? shows visible help, next handled key hides it", () => {
  const m = mount(T); m.view.open();
  assert.equal(m.view.helpPanel.hidden, true);
  m.press("?", { shiftKey: true });
  assert.equal(m.view.helpPanel.hidden, false);
  assert.equal(m.view.liveRegion.textContent, EK.HELP_TEXT);
  m.press("ArrowDown");
  assert.equal(m.view.helpPanel.hidden, true);
});

test("view: Esc calls onExit; unhandled keys and modified keys are not prevented", () => {
  let exited = 0;
  const m = mount(T, { onExit: () => exited++ }); m.view.open();
  assert.equal(m.press("Tab").defaultPrevented, false);
  assert.equal(m.press("ArrowDown", { ctrlKey: true }).defaultPrevented, false);
  assert.equal(m.press("Escape").defaultPrevented, true);
  assert.equal(exited, 1);
  m.press("Escape"); assert.equal(exited, 1); // repeated Esc does nothing more
});

test("view: focus arriving by Tab/click syncs selection", () => {
  const m = mount(T); m.view.open();
  m.byId["n0.0.1"].focus();
  assert.equal(m.view.controller.getFocusId(), "n0.0.1");
  assert.equal(m.byId["n0.0.1"].attrs.tabindex, "0");
  assert.equal(m.byId["n0"].attrs.tabindex, "-1");
});

test("view: repeated Space clears the live region so it is announced again", () => {
  const log = [];
  const m = mount(T, { schedule: (f) => { log.push(m.view.liveRegion.textContent); f(); } });
  m.view.open(); m.press(" "); m.press(" ");
  assert.equal(log[log.length - 1], ""); // cleared before re-setting
});

test("view: speech mode uses speechSynthesis hooks only, never the live region", () => {
  const spoken = []; let cancels = 0;
  const m = mount(T, { mode: "speech", speak: (t) => spoken.push(t), cancelSpeech: () => cancels++ });
  m.view.open();
  m.press("ArrowDown"); m.press("i");
  assert.equal(m.view.liveRegion.textContent, "");
  assert.equal(spoken.length, 3); // open, move, detailed: one utterance each
  assert.equal(spoken[1], find(T, "n0.0").spoken_quick);
  assert.equal(spoken[2], find(T, "n0.0").spoken_detailed);
  assert.equal(cancels, 3);
});

test("view: screen-reader mode never calls speak", () => {
  let called = 0;
  const m = mount(T, { speak: () => called++, cancelSpeech: () => called++ });
  m.view.open(); m.press("ArrowDown"); m.press("i");
  assert.equal(called, 0);
});

// =========================================================================
// Regression tests for the code-review fixes (C1, M1, M3-M7, M9)
// =========================================================================

function countTreeitems(el) {
  let n = 0; (function w(e) { if (e.attrs.role === "treeitem") n++; e.children.forEach(w); })(el); return n;
}
function chain(depth) { // root -> n1 -> n2 ... with `depth` levels in total
  const root = { id: "n0", role: "equation", spoken_quick: "Equation", children: [] };
  let cur = root;
  for (let i = 1; i < depth; i++) { const n = { id: "n" + i, role: "operator", spoken_quick: "Level " + (i + 1), children: [] }; cur.children.push(n); cur = n; }
  return root;
}

// ---- C1: view lifecycle ---------------------------------------------------

test("C1: createView twice on one container leaves exactly one tree, one listener set", () => {
  const m = mount(T); m.view.open();
  const second = EK.createView(m.tc, TREES["2x+3=9"], { document: m.doc, schedule: (f) => f(), onExit() {} });
  second.open();
  assert.equal(m.view.isDestroyed(), true);
  assert.equal(second.isDestroyed(), false);
  const ids = []; (function w(e) { if (e.attrs.role === "treeitem") ids.push(e.attrs.id); e.children.forEach(w); })(m.tc);
  assert.equal(ids.length, 7); assert.equal(new Set(ids).size, ids.length);
  assert.equal(m.tc.listeners.keydown.length, 1);
  assert.equal(m.tc.listeners.focusin.length, 1);
  assert.equal(m.page.children.length, 3); // container + ONE live region + ONE help panel
  assert.equal(m.tc.children.length, 1);
});

test("C1: one key press moves exactly once after rebuild; stale controller is closed", () => {
  const m = mount(T); m.view.open();
  const oldController = m.view.controller;
  const second = EK.createView(m.tc, TREES["2x+3=9"], { document: m.doc, schedule: (f) => f(), onExit() {} });
  second.open();
  m.doc.focusLog.length = 0;
  m.press("ArrowDown");
  assert.equal(second.controller.getFocusId(), "n0.0");
  assert.equal(m.doc.focusLog.length, 1);
  assert.equal(oldController.isOpen(), false);
  assert.equal(oldController.handleKey(key("ArrowDown")).handled, false);
  assert.throws(() => m.view.open(), (e) => e.code === "destroyed");
});

test("C1: a stale key handler captured before destroy does nothing", () => {
  const m = mount(T); m.view.open();
  const stale = m.tc.listeners.keydown[0];
  m.view.destroy();
  const ev = { key: "ArrowDown", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
  stale(ev);
  assert.equal(ev.defaultPrevented, false);
});

test("C1: destroy removes listeners, tree, live region, help panel; idempotent", () => {
  const m = mount(T); m.view.open();
  m.view.destroy(); m.view.destroy();
  assert.equal(m.tc.listeners.keydown.length, 0);
  assert.equal(m.tc.listeners.focusin.length, 0);
  assert.equal(countTreeitems(m.tc), 0);
  assert.equal(m.page.children.length, 1); // only the container remains
  assert.equal(m.press("ArrowDown").defaultPrevented, false);
  assert.equal(m.view.controller.isOpen(), false);
});

test("C1: destroy preserves pre-existing children and restores role / aria-label", () => {
  const doc = fakeDoc(); const page = new El("div", doc); const tc = page.appendChild(new El("div", doc));
  const mine = tc.appendChild(new El("p", doc));
  tc.setAttribute("aria-label", "Original label");
  const v = EK.createView(tc, T, { document: doc, schedule: (f) => f(), onExit() {} });
  assert.equal(tc.attrs["aria-label"], "Equation explorer");
  assert.equal(tc.attrs.role, "tree");
  v.destroy();
  assert.deepEqual(tc.children, [mine]);
  assert.equal(tc.attrs["aria-label"], "Original label");
  assert.equal("role" in tc.attrs, false);
});

test("C1: pending live-region write after destroy is dropped", () => {
  const pending = []; const m = mount(T, { schedule: (f) => pending.push(f) });
  m.view.open();
  const live = m.view.liveRegion;
  m.view.destroy();
  pending.forEach((f) => f());
  assert.equal(live.textContent, "");
});

test("C1: caller-supplied live region and help panel are kept, cleaned and reusable", () => {
  const doc = fakeDoc(); const page = new El("div", doc); const tc = page.appendChild(new El("div", doc));
  const live = page.appendChild(new El("div", doc)); const help = page.appendChild(new El("div", doc));
  help.hidden = true;
  const o = { document: doc, schedule: (f) => f(), onExit() {}, liveRegion: live, helpPanel: help };
  const v = EK.createView(tc, T, o); v.open();
  assert.equal(live.textContent.startsWith("Equation explorer."), true);
  assert.equal(help.children.length, 1);
  v.destroy();
  assert.equal(live.parentNode, page); assert.equal(help.parentNode, page);
  assert.equal(live.textContent, ""); assert.equal(help.children.length, 0); assert.equal(help.hidden, true);
  const v2 = EK.createView(tc, T, o); v2.open(); v2.destroy();
  assert.equal(page.children.length, 3);
});

test("C1: a bad new tree throws and leaves the previous view working", () => {
  const m = mount(T); m.view.open();
  assert.throws(() => EK.createView(m.tc, { id: "" }, { document: m.doc, onExit() {} }), (e) => e.code === "tree-invalid");
  assert.equal(m.view.isDestroyed(), false);
  m.press("ArrowDown");
  assert.equal(m.doc.activeElement, m.byId["n0.0"]);
});

test("C1: 50 create/destroy cycles do not leak elements or listeners", () => {
  const m = mount(T);
  for (let i = 0; i < 50; i++) { const v = EK.createView(m.tc, T, { document: m.doc, schedule: (f) => f(), onExit() {} }); v.open(); }
  assert.equal(countTreeitems(m.tc), 7);
  assert.equal(m.tc.listeners.keydown.length, 1);
  assert.equal(m.page.children.length, 3);
});

// ---- M1: onExit required ---------------------------------------------------

test("M1: createView without a usable onExit throws a clear error", () => {
  const doc = fakeDoc(); const page = new El("div", doc); const tc = page.appendChild(new El("div", doc));
  for (const bad of [undefined, null, "x", 5, {}]) {
    assert.throws(() => EK.createView(tc, T, { document: doc, onExit: bad }),
      (e) => e.code === "options-invalid" && /onExit/.test(e.message) && /Explore button/.test(e.message));
  }
  assert.throws(() => EK.createView(tc, T, { document: doc }), (e) => e.code === "options-invalid");
  assert.throws(() => EK.createView(tc, T), (e) => e.code === "options-invalid");
  assert.equal(tc.children.length, 0); assert.equal(page.children.length, 1); // nothing was built
});

test("M1: Esc calls onExit once, takes the tree out of the tab order, open() restores it", () => {
  let exits = 0; const m = mount(T, { onExit: () => exits++ }); m.view.open();
  m.press("ArrowDown");
  m.press("Escape"); m.press("Escape");
  assert.equal(exits, 1);
  assert.equal(Object.values(m.byId).filter((e) => e.attrs.tabindex === "0").length, 0);
  m.byId["n0.0"].focus(); // Tab / click back in while closed: keys stay dead, state not corrupted
  assert.equal(m.press("ArrowDown").defaultPrevented, false);
  m.view.open();
  assert.equal(m.view.controller.getFocusId(), "n0");
  assert.equal(m.byId["n0"].attrs.tabindex, "0");
  assert.equal(m.press("ArrowDown").defaultPrevented, true);
});

// ---- M3: speech mode -------------------------------------------------------

test("M3: speech mode without speak falls back to the live region and says so", () => {
  const m = mount(T, { mode: "speech" });
  assert.equal(m.view.mode, "screen-reader");
  assert.match(m.view.modeFallback, /speak/);
  m.view.open(); m.press("i");
  assert.equal(m.view.liveRegion.textContent, find(T, "n0").spoken_detailed);
});

test("M3: normal modes report no fallback", () => {
  assert.equal(mount(T).view.modeFallback, null);
  const s = mount(T, { mode: "speech", speak() {} });
  assert.equal(s.view.mode, "speech"); assert.equal(s.view.modeFallback, null);
});

test("M3: invalid mode / non-function callbacks are rejected", () => {
  const doc = fakeDoc(); const page = new El("div", doc); const tc = page.appendChild(new El("div", doc));
  const base = { document: doc, onExit() {} };
  assert.throws(() => EK.createView(tc, T, Object.assign({}, base, { mode: "loud" })), (e) => e.code === "options-invalid");
  for (const name of ["speak", "cancelSpeech", "schedule"]) {
    assert.throws(() => EK.createView(tc, T, Object.assign({}, base, { [name]: "no" })), (e) => e.code === "options-invalid", name);
  }
});

test("M3: speak failing falls back to the live region for that announcement only", () => {
  let calls = 0;
  const m = mount(T, { mode: "speech", speak: () => { calls++; throw new Error("tts down"); } });
  m.view.open();
  assert.equal(calls, 1);
  assert.match(m.view.liveRegion.textContent, /^Equation explorer\./);
});

test("M3: a throwing cancelSpeech does not stop speech; cancel is optional", () => {
  const spoken = [];
  const m = mount(T, { mode: "speech", speak: (t) => spoken.push(t), cancelSpeech: () => { throw new Error("x"); } });
  m.view.open(); assert.equal(spoken.length, 1);
  const n = mount(T, { mode: "speech", speak: (t) => spoken.push(t) });
  n.view.open(); assert.equal(spoken.length, 2);
});

test("M3: each action uses exactly one channel", () => {
  for (const mode of ["screen-reader", "speech"]) {
    const spoken = []; let liveWrites = 0;
    const m = mount(T, { mode, speak: (t) => spoken.push(t) });
    const live = m.view.liveRegion;
    let value = ""; Object.defineProperty(live, "textContent", { get: () => value, set: (v) => { if (v !== "") liveWrites++; value = v; } });
    m.view.open();
    for (const k of ["ArrowDown", " ", "i", "c", "r", "?", "ArrowUp", "Home"]) {
      const s0 = spoken.length, l0 = liveWrites;
      m.press(k);
      const used = (spoken.length - s0) + (liveWrites - l0);
      assert.ok(used <= 1, mode + " " + k + " used " + used + " channels/utterances");
    }
    if (mode === "screen-reader") assert.equal(spoken.length, 0); else assert.equal(liveWrites, 0);
  }
});

// ---- M4: role-based names ---------------------------------------------------

test("M4: view labels fall back to the role, not a generic sentence", () => {
  const tree = { id: "a", role: "equation", children: [{ id: "b", role: "group_multiplier", children: [] }, { id: "c", children: [] }] };
  const m = mount(tree);
  assert.equal(m.byId.a.attrs["aria-label"], "Equation");
  assert.equal(m.byId.b.attrs["aria-label"], "Group multiplier");
  assert.equal(m.byId.c.attrs["aria-label"], EK.MESSAGES.FALLBACK_NAME);
  assert.equal(m.byId.b.children[0].textContent, "Group multiplier");
  for (const el of Object.values(m.byId)) assert.doesNotMatch(el.attrs["aria-label"], /No explanation/i);
});

// ---- M5: held-key boundaries -------------------------------------------------

test("M5: holding a key announces the first boundary once, not every repeat", () => {
  const c = at("n0");
  const out = [];
  for (let i = 0; i < 12; i++) out.push(c.handleKey(key("ArrowDown", { repeat: i > 0 })));
  const moved = out.filter((r) => r.moved).length;
  const said = out.filter((r) => r.announce);
  assert.equal(moved, 3); // n0 -> n0.0 -> n0.0.0 -> n0.0.0.0
  assert.equal(said.length, 1);
  assert.match(said[0].announce, /has nothing inside it\.$/);
  assert.equal(out.slice(0, 3).every((r) => r.announce === null), true); // movement is silent
});

test("M5: a fresh press at the boundary announces again; moving away resets", () => {
  const c = at("n0.0.0.1");
  assert.ok(c.handleKey(key("ArrowRight")).announce);                     // press 1
  assert.equal(c.handleKey(key("ArrowRight", { repeat: true })).announce, null);
  assert.equal(c.handleKey(key("ArrowRight", { repeat: true })).announce, null);
  assert.ok(c.handleKey(key("ArrowRight")).announce);                     // new press
  c.handleKey(key("ArrowLeft"));                                          // moved: resets
  assert.ok(c.handleKey(key("ArrowRight", { repeat: true })).moved);
  assert.ok(c.handleKey(key("ArrowRight", { repeat: true })).announce);   // boundary again after moving
});

test("M5: first boundary during a hold is announced even if the hold began elsewhere", () => {
  const c = at("n0.0.0.0");
  assert.equal(c.handleKey(key("ArrowRight")).moved, true);               // press moves
  const r = c.handleKey(key("ArrowRight", { repeat: true }));             // hits the end
  assert.equal(r.moved, false); assert.equal(r.announce, "This is the last part at this level.");
  assert.equal(c.handleKey(key("ArrowRight", { repeat: true })).announce, null);
});

test("M5: switching to a different boundary key mid-hold announces it once", () => {
  const c = at("n0");
  assert.ok(c.handleKey(key("ArrowUp")).announce);
  assert.equal(c.handleKey(key("ArrowUp", { repeat: true })).announce, null);
  assert.ok(c.handleKey(key("Home", { repeat: true })).announce);         // different action
  assert.equal(c.handleKey(key("Home", { repeat: true })).announce, null);
});

test("M5: reading keys stay silent on auto-repeat, still prevented", () => {
  const c = at("n0.0");
  for (const k of [" ", "i", "c", "r", "?"]) {
    const r = c.handleKey(key(k, { repeat: true }));
    assert.equal(r.announce, null, k); assert.equal(r.preventDefault, true, k);
  }
});

// ---- M7: depth / malformed ---------------------------------------------------

test("M7: MAX_DEPTH levels are accepted, one more is a tree-too-deep error", () => {
  assert.equal(EK.MAX_DEPTH, 100);
  assert.doesNotThrow(() => EK.createController(chain(EK.MAX_DEPTH)));
  assert.throws(() => EK.createController(chain(EK.MAX_DEPTH + 1)),
    (e) => e.code === "tree-too-deep" && /too deep/.test(e.message));
});

test("M7: a 50000-level tree fails predictably, not with RangeError", () => {
  assert.throws(() => EK.createController(chain(50000)), (e) => e.code === "tree-too-deep" && !(e instanceof RangeError));
});

test("M7: too-deep or invalid trees do not touch the container", () => {
  const doc = fakeDoc(); const page = new El("div", doc); const tc = page.appendChild(new El("div", doc));
  for (const bad of [chain(500), { id: "a", children: null }, null]) {
    assert.throws(() => EK.createView(tc, bad, { document: doc, onExit() {} }), (e) => /tree/.test(e.code));
  }
  assert.equal(tc.children.length, 0); assert.deepEqual(tc.attrs, {}); assert.equal(page.children.length, 1);
});

test("M7: all tree errors carry a code", () => {
  for (const bad of [null, { id: "" }, { id: "a", children: "x" }, { id: "a", children: [{ id: "a" }] }, { id: "a", children: [[]] }]) {
    assert.throws(() => EK.createController(bad), (e) => e.code === "tree-invalid");
  }
});

test("M7: a 100-level tree can be navigated down and back up", () => {
  const c = EK.createController(chain(EK.MAX_DEPTH));
  for (let i = 0; i < EK.MAX_DEPTH - 1; i++) assert.equal(c.handleKey(key("ArrowDown")).moved, true);
  assert.equal(c.getSelection().level, 100);
  assert.equal(c.handleKey(key("ArrowDown")).moved, false);
  c.handleKey(key("Home")); assert.equal(c.getFocusId(), "n0");
});

// ---- M6: AltGr ----------------------------------------------------------------

const altGr = (k, extra) => key(k, Object.assign({ ctrlKey: true, altKey: true, getModifierState: (n) => n === "AltGraph" }, extra || {}));

test("M6: AltGr (reported as Ctrl+Alt) with a printable character is accepted", () => {
  const c = at("n0.0");
  assert.equal(c.handleKey(altGr("?")).action, "help");
  assert.equal(c.handleKey(altGr("r")).action, "readAll");
  assert.equal(c.handleKey(altGr("c", { ctrlKey: false })).action, "context"); // Linux style: alt only
  assert.equal(c.handleKey(altGr("c", { ctrlKey: false, altKey: false })).action, "context");
});

test("M6: real Ctrl / Alt / Meta combinations still pass through", () => {
  const c = at("n0.0");
  const noAltGr = { getModifierState: () => false };
  for (const mods of [{ ctrlKey: true }, { altKey: true }, { ctrlKey: true, altKey: true }, { metaKey: true }]) {
    for (const k of ["r", "i", "c", "?", "ArrowDown", "Home", " ", "Escape"]) {
      assert.equal(c.handleKey(key(k, Object.assign({}, mods, noAltGr))).handled, false, JSON.stringify(mods) + k);
    }
  }
  // no getModifierState at all: cannot tell AltGr from Ctrl+Alt, so it is rejected
  assert.equal(c.handleKey(key("?", { ctrlKey: true, altKey: true })).handled, false);
});

test("M6: AltGr never lets through Ctrl alone, Meta, or non-printable keys", () => {
  const c = at("n0.0");
  const gm = { getModifierState: () => true };
  assert.equal(c.handleKey(key("r", Object.assign({ ctrlKey: true }, gm))).handled, false);   // Ctrl without Alt
  assert.equal(c.handleKey(key("r", Object.assign({ metaKey: true, altKey: true }, gm))).handled, false);
  assert.equal(c.handleKey(altGr("ArrowDown")).handled, false);
  assert.equal(c.handleKey(altGr("Home")).handled, false);
  assert.equal(c.handleKey(altGr("Escape")).handled, false);
});

test("M6: a throwing getModifierState is treated as not-AltGr", () => {
  const c = at("n0.0");
  assert.equal(c.handleKey(key("?", { ctrlKey: true, altKey: true, getModifierState() { throw new Error("x"); } })).handled, false);
});

// ---- M9: smaller items ------------------------------------------------------------

test("M9: setFocus with an invalid id is not 'handled'", () => {
  const c = at("n0.0");
  for (const id of ["nope", "", undefined, null, 5]) {
    const r = c.setFocus(id);
    assert.equal(r.ok, false); assert.equal(r.handled, false); assert.equal(r.preventDefault, false);
    assert.equal(r.error, "unknown-node"); assert.equal(r.moved, false); assert.equal(r.focusId, "n0.0");
  }
  assert.equal(c.setFocus("n0.1").handled, true);
});

test("M9: setFocus on a closed controller fails with 'closed'", () => {
  const c = at("n0.0"); c.handleKey(key("Escape"));
  const r = c.setFocus("n0.1");
  assert.equal(r.ok, false); assert.equal(r.error, "closed"); assert.equal(c.getFocusId(), "n0.0");
});

test("M9: reset() reports movement accurately", () => {
  const c = at("n0.0.1");
  assert.equal(c.reset().moved, true);
  assert.equal(c.reset().moved, false);
  assert.equal(c.getFocusId(), "n0");
});

test("M9: container without a parent is rejected unless live region and help panel are supplied", () => {
  const doc = fakeDoc(); const orphan = new El("div", doc);
  assert.throws(() => EK.createView(orphan, T, { document: doc, onExit() {} }), (e) => e.code === "container-invalid");
  const live = new El("div", doc); const help = new El("div", doc);
  const v = EK.createView(orphan, T, { document: doc, onExit() {}, liveRegion: live, helpPanel: help, schedule: (f) => f() });
  v.open(); assert.match(live.textContent, /^Equation explorer\./);
  for (const bad of [null, undefined, {}, "div", 5]) {
    assert.throws(() => EK.createView(bad, T, { document: doc, onExit() {} }), (e) => e.code === "container-invalid");
  }
});

test("M9: focus avoids needless scrolling", () => {
  const m = mount(T); const scrolls = [];
  for (const el of Object.values(m.byId)) el.scrollIntoView = (o) => scrolls.push(o);
  m.view.open(); m.press("ArrowDown");
  assert.ok(m.doc.focusOpts.length >= 2);
  assert.ok(m.doc.focusOpts.every((o) => o && o.preventScroll === true));
  assert.ok(scrolls.length >= 2 && scrolls.every((o) => o.block === "nearest"));
});

test("M9: open() reports focused=false when the browser did not take focus", () => {
  const m = mount(T);
  m.byId["n0"].focus = () => {}; // e.g. container is display:none
  assert.equal(m.view.open().focused, false);
  const ok = mount(T);
  assert.equal(ok.view.open().focused, true);
});

// ---- ARIA consistency across every real tree ------------------------------------------

test("ARIA: levels, positions, sizes, expanded, ids and tab stop are consistent for every fixture", () => {
  for (const [name, tree] of Object.entries(TREES)) {
    const m = mount(tree); m.view.open();
    const seenIds = new Set();
    (function walk(node, level, pos, size) {
      const el = m.byId[node.id];
      assert.ok(el, name + node.id);
      assert.equal(el.attrs["aria-level"], String(level), name + node.id);
      assert.equal(el.attrs["aria-posinset"], String(pos), name + node.id);
      assert.equal(el.attrs["aria-setsize"], String(size), name + node.id);
      assert.equal(el.attrs["aria-expanded"], node.children.length ? "true" : undefined, name + node.id);
      assert.equal(el.attrs["aria-label"], node.spoken_quick, name + node.id);
      assert.equal(seenIds.has(el.attrs.id), false); seenIds.add(el.attrs.id);
      const group = el.children.find((c) => c.attrs.role === "group");
      assert.equal(!!group, node.children.length > 0);
      if (group) assert.equal(group.children.length, node.children.length);
      node.children.forEach((k, i) => walk(k, level + 1, i + 1, node.children.length));
    })(tree, 1, 1, 1);
    assert.equal(Object.values(m.byId).filter((e) => e.attrs.tabindex === "0").length, 1, name);
    assert.equal(Object.values(m.byId).filter((e) => e.attrs["aria-selected"] === "true").length, 1, name);
  }
});

test("ARIA: selection and tab stop stay synchronised through a long key sequence", () => {
  const m = mount(TREES["2(x+3)=12"]); m.view.open();
  const keys = ["ArrowDown", "ArrowDown", "ArrowRight", "ArrowDown", "ArrowDown", "ArrowRight", "ArrowUp", "i", "Home", "ArrowRight", "ArrowLeft", "?", "ArrowDown"];
  for (const k of keys) {
    m.press(k);
    const id = m.view.controller.getFocusId();
    assert.equal(m.byId[id].attrs.tabindex, "0", k);
    assert.equal(m.byId[id].attrs["aria-selected"], "true", k);
    assert.equal(m.doc.activeElement, m.byId[id], k);
    assert.equal(Object.values(m.byId).filter((e) => e.attrs.tabindex === "0").length, 1, k);
  }
});

// ---- docs/contracts.md ExplorerNode: only the shared fields are used -------------

const CONTRACT_FIELDS = ["children", "id", "role", "spoken_context", "spoken_detailed", "spoken_quick", "type", "value"];

function allNodes(node, out) {
  out = out || [];
  out.push(node);
  node.children.forEach((k) => allNodes(k, out));
  return out;
}

test("CONTRACT: the stored engine trees have exactly the shared ExplorerNode fields and no span", () => {
  for (const [name, tree] of Object.entries(TREES)) {
    for (const n of allNodes(tree)) {
      assert.deepEqual(Object.keys(n).sort(), CONTRACT_FIELDS, name + " " + n.id);
      assert.equal(n.span, undefined, name + " " + n.id);
      assert.ok(n.value === null || typeof n.value === "string", name + " " + n.id + " value is a string or null");
    }
  }
});

test("CONTRACT: every node of every stored tree is reachable with the arrow keys alone", () => {
  for (const [name, tree] of Object.entries(TREES)) {
    const c = EK.createController(tree);
    const seen = [tree.id];
    // depth-first walk using only Down / Right / Up
    const visit = (node) => {
      node.children.forEach((k, i) => {
        const r = c.handleKey(key(i === 0 ? "ArrowDown" : "ArrowRight"));
        assert.equal(r.focusId, k.id, name);
        seen.push(k.id);
        visit(k);
        // return focus to this child before moving to its next sibling
        while (c.getFocusId() !== k.id) assert.equal(c.handleKey(key("ArrowUp")).moved, true, name);
      });
    };
    visit(tree);
    assert.deepEqual(seen.sort(), allNodes(tree).map((n) => n.id).sort(), name);
  }
});

test("CONTRACT: the keyboard module ignores any span and value an upstream tree might still carry", () => {
  const withExtras = JSON.parse(JSON.stringify(T));
  allNodes(withExtras).forEach((n) => { n.span = [0, 1]; n.extra = "x"; });
  const plain = EK.createController(T);
  const extra = EK.createController(withExtras);
  for (const k of ["ArrowDown", "ArrowDown", "ArrowRight", "i", "c", "r", "Home", "ArrowUp", "?"]) {
    const a = plain.handleKey(key(k)), b = extra.handleKey(key(k));
    assert.deepEqual([b.focusId, b.announce, b.moved], [a.focusId, a.announce, a.moved], k);
  }
});

test("CONTRACT: a tree with only id and children is enough (the other fields are optional for the keys)", () => {
  const minimal = { id: "a", children: [{ id: "b", children: [] }, { id: "c", children: [] }] };
  const c = EK.createController(minimal);
  assert.equal(c.handleKey(key("ArrowDown")).focusId, "b");
  assert.equal(c.handleKey(key("ArrowRight")).focusId, "c");
});
