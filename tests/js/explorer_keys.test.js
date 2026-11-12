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

test("a node with missing spoken text gets a safe fallback", () => {
  const tree = { id: "a", role: "equation", children: [{ id: "b", role: "left_side", spoken_quick: "", children: [] }] };
  const c = EK.createController(tree);
  assert.equal(c.handleKey(key(" ")).announce, EK.MESSAGES.NO_TEXT);
  c.handleKey(key("ArrowDown"));
  assert.equal(c.handleKey(key("i")).announce, EK.MESSAGES.NO_TEXT);
  assert.equal(c.handleKey(key("ArrowDown")).announce, "left side has nothing inside it.");
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
  const bound = c.handleKey(key("ArrowDown", { repeat: true }));
  assert.equal(bound.announce, null); assert.equal(c.getFocusId(), "n0.0.1");
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
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  set textContent(v) { this._text = v; }
  get textContent() { return this._text; }
  focus() {
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
  const doc = { activeElement: null, focusLog: [], createElement: (t) => new El(t, doc) };
  return doc;
}
function mount(tree, opts) {
  const doc = fakeDoc();
  const page = new El("div", doc);
  const tc = page.appendChild(new El("div", doc));
  const view = EK.createView(tc, tree, Object.assign({ document: doc, schedule: (f) => f() }, opts));
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
