# Keyboard guide

Owner: Member 4
Source of truth: plan.md §7.6 (explorer) and §7.8 (page). This file turns those sections into a precise spec that Member 5 can build the tree UI against.

`docs/contracts.md` (Member 2) is the authoritative shared contract for the AST and the ExplorerNode. `docs/explorer_contract.md` (Member 4) records how the explorer reads it, the role vocabulary and the parser checklist for A8–A16.

**Status (Phase 3):** the key logic is implemented in `static/explorer_keys.js` and covered by automated tests (section 9). It is not yet wired into the page and **nothing here has been tested with NVDA or Orca**. Section 7 lists what still has to be tested with real screen readers. Statements about screen-reader behaviour in sections 5 and 6 are design intent or expectations, marked as such.

## 1. Mathematical node roles

From plan.md §7.6. A number is a coefficient only when it multiplies `x`. In `3x + 5`, 3 is a coefficient and 5 is a constant term.

| Role | When it applies | Spoken example |
|---|---|---|
| Equation | the whole thing | "The whole equation: 2 times the group x plus 3, equals 10." |
| Left side / Right side | each side of `=` | "Left side: 2 times the group x plus 3." |
| Coefficient | a number multiplying x | "2. This is the coefficient. It tells you x is multiplied by 2." |
| Variable | `x` | "x. This is the variable, the unknown number we want to find." |
| Constant term | a number on its own | "5. This is a constant term. It's added to 3x." |
| Group (brackets) | `( … )` | "Brackets grouping x plus 3. Everything inside is treated as one quantity." |
| Multiplier of a group | `2(…)` | "2 multiplies everything inside the brackets." |
| Operator | `+ − × ÷` | "Plus. It adds 3x and 5." |
| Power | `x^2` | "x squared. x is the base, 2 is the exponent: x times x." |
| Fraction | `a / b` | "A fraction. Numerator x plus 1, denominator 2." |

### Three depths for every part

| Depth | Key | Example for the 3 in `3x + 5 = 14` |
|---|---|---|
| Quick (`spoken_quick`) | Space | "3 is the coefficient of x." |
| Detailed (`spoken_detailed`) | `I` | "3x means 3 multiplied by x. 3 is the coefficient and x is the variable." |
| Context (`spoken_context`) | `C` | "This term is on the left side and is added to 5." |

## 2. Keys

| Key | Action |
|---|---|
| ↑ | Move to the bigger part (parent) |
| ↓ | Move inside (first child) |
| ← / → | Previous / next part at the same level |
| Space | Read the selected part (quick) |
| `I` | More information (detailed) |
| `C` | Context: how this part connects to the rest |
| `R` | Read the whole equation again |
| `Home` | Jump back to the whole equation |
| `?` | List the keys |
| Esc | Leave the explorer |

### Rules that apply to every key

1. Explorer keys act only while focus is inside the tree. They never act while the student is typing in a text box.
2. Plain keys only. If Ctrl, Alt, Meta/Cmd is held, the page does nothing and the browser or screen reader handles the key. Shift is ignored except for `?` (Shift + `/` on a US layout). Match on the character `?`, not on a physical key.
3. For every key the page handles, it calls `preventDefault()` so that Space does not scroll the page and Home does not jump to the top of the page.
4. Unknown keys are ignored silently.
5. Navigation never wraps around. Reaching an edge is announced (section 3).
6. Sibling order (← / →) is the order of the parts as typed, left to right.
7. Moving with the arrow keys moves focus, and the screen reader reads the item's accessible name, which is its quick text. The student should not need to press Space after every move. Space exists to hear the quick text again.

### Where each key goes

Using `3x + 5 = 14` as the example (see assumptions A1–A3 in section 8 for how nodes get their roles):

```
Equation  3x + 5 = 14
├─ Left side  3x + 5          (the Add node)
│  ├─ Multiplication  3x      (the Mul node, Operator role)
│  │  ├─ Coefficient  3
│  │  └─ Variable  x
│  └─ Constant term  5
└─ Right side  14             (the Number node)
```

Keys from the Coefficient `3`: ↑ goes to Multiplication `3x`, → goes to Variable `x`, ← and ↓ stay (boundary messages), Home goes to the Equation.

## 3. Boundary behaviour

Boundary messages are short, are spoken through the live region, and never move focus.

| Situation | Behaviour | Spoken message |
|---|---|---|
| ↑ on the whole equation | Stay | "This is the whole equation. There is nothing bigger." |
| ↓ on a part with no children | Stay | "[Part] has nothing inside it." |
| ← on the first part at a level | Stay | "This is the first part at this level." |
| → on the last part at a level | Stay | "This is the last part at this level." |
| `Home` on the whole equation | Stay | "Already at the whole equation." |
| `Home` anywhere else | Focus moves to the root. The screen reader speaks the root's accessible name because focus moved; the page adds no second announcement (see Phase 3 clarifications below) | (root name, spoken by focus) |
| `R` | Reads the whole equation. Focus does **not** move | (root detailed text, see Phase 3 clarifications) |
| Esc | The keyboard module closes the controller (keys stop working), removes the tree items from the tab order, announces the message and calls `onExit`. The **host page** must, in `onExit`, move focus to the Explore button and hide or collapse the explorer (or call `view.destroy()` to discard its state). The module does not hide or discard the tree itself | "Left the explorer." |
| Explore pressed with an empty box | Explorer does not open, focus stays on the box | The parser's error message |
| Explore pressed with unparseable input | Explorer does not open | The parser's spoken error (plan §7.1) |
| Re-opening the explorer | Focus starts on the whole equation, never on the previous position | Opening announcement (section 5) |
| `?` | Reads the key list, focus does not move. Pressing `?` again repeats it | See section 4 |

On a part that is an only child, ← and → both say "This is the only part at this level."

## 4. `?` help text

Spoken and shown as a list, in this order:

> Up arrow: move to the bigger part. Down arrow: move inside. Left and right arrows: previous and next part at the same level. Space: hear this part. I: more information. C: how this part connects to the rest. R: read the whole equation again. Home: back to the whole equation. Escape: leave the explorer.

The help is also available as visible text (not only speech) so it works with no speech at all.

## 5. Screen-reader behaviour (design intent)

This is what the page should expose. It follows the standard ARIA tree pattern, so screen readers can announce position and level without custom code. None of it has been verified yet.

### Structure

| Element | Attributes |
|---|---|
| Explorer container | `role="tree"`, `aria-label="Equation explorer"` |
| Each part | `role="treeitem"` |
| Parts with children | `aria-expanded="true"` (the whole tree is always expanded in the MVP, so ↓ never needs to open anything) |
| Each part | `aria-level`, `aria-posinset`, `aria-setsize` (so the screen reader can say "level 2, 1 of 2") |
| Accessible name of a part | its `spoken_quick` text |
| Tabbing | Roving `tabindex`: only the current part has `tabindex="0"`, all others `-1`. Tab enters the tree on the current part and the next Tab leaves it |
| Live region | One shared `aria-live="polite"` region, separate from the result region, for Space / `I` / `C` / `R` / `?` / boundary messages |

### Announcements

| Event | What the student should hear |
|---|---|
| Explorer opens | "Equation explorer. [root detailed text] Press question mark for keys." Focus is on the root |
| Arrow key moves | The new part's quick text, plus level and position as given by the screen reader |
| Space | Quick text again (live region) |
| `I` | Detailed text (live region) |
| `C` | Context text (live region) |
| Boundary | The message from section 3 |
| Esc | "Left the explorer." and focus is on the Explore button |

### Phase 3 clarifications (not key changes)

No key assignment differs from plan §7.6. Two message details were corrected because the Phase 1 and 2 explorer text made the original wording wrong:

1. **`R` and the opening announcement use the root's `spoken_detailed`, not `spoken_quick`.** The root's quick text is only "Equation", which does not read the equation. The detailed text is "The whole equation. It says that the left side, 3x plus 5, has the same value as the right side, 14." That is what plan §7.6 means by "Read the whole equation again".
2. **`Home` does not add a live-region announcement.** Focus moving to the root already makes the screen reader speak the item's name. Adding the root's text as well would be the double announcement that T8 and T9 are meant to rule out.

Also decided in Phase 3 (documented, no new keys):

- **Auto-repeat.** A held key (`event.repeat`) keeps moving the selection silently (focus is the announcement). The **first** boundary reached is announced once; further repeats of the same key at that boundary are silent. Pressing the key again (a new press) announces again, and moving away resets this. Held Space / I / C / R / `?` are silent after the first press. The key is always swallowed.
- **Esc is final.** After Esc the controller ignores every key until the explorer is opened again, so a second Esc cannot fire twice.
- **Shift.** Shift and Caps Lock are ignored, so `I` and `i` are the same key.
- **Modifiers and AltGr.** Ctrl, Alt and Meta combinations pass through, with one exception. AltGr (Windows reports it as Ctrl+Alt) is accepted when `getModifierState("AltGraph")` reports true **and** the key is a single printable character (for example `?` on a layout that needs AltGr for it). Ctrl alone, Meta, and non-printable keys (arrows, Home, Esc) are never accepted this way. **Limitation:** on AltGr keyboard layouts, a real Ctrl+Alt combination may also report AltGraph as true, so pass-through of Ctrl+Alt shortcuts is **not guaranteed** on those layouts: a Ctrl+Alt+I/C/R/`?` could be captured by the explorer. If a browser does not provide `getModifierState`, Ctrl+Alt is rejected. This behaviour has **not been verified** in any real browser or keyboard layout.
- **Missing text.** A node without a quick text is named from its role ("Left side", "Constant term"), or "Equation part" if it has no role either. Space reads that name. A missing detailed or context text is announced as "There is no detailed explanation for [name]." / "There is no context for [name]." Silence and a generic "no explanation" message are both avoided.
- **Tree limits.** Trees deeper than 100 levels are rejected (real equations are about 10 deep).
- **Mouse or Tab focus.** If focus lands on a tree item another way, the selection follows it.
- **Help panel.** `?` also shows a visible key list (a `role="group"` panel, hidden again on the next handled key), as section 4 requires.

### Speech and screen reader at the same time

Plan §7.8 says speech uses the browser's `speechSynthesis`. Screen-reader users must not hear two voices at once. Implemented in `createView` as the `mode` option (the page still has to choose the mode, Q1):

- `"screen-reader"` (default): the screen reader speaks movement (focus + accessible name) and the live region carries everything else. `speechSynthesis` is never called.
- `"speech"`: for a student with no screen reader. The page speaks through `speechSynthesis`, cancelling anything in progress first, and the live region is not written.
- Every event produces at most one spoken string in exactly one channel.

Original proposal, kept for reference:

- Arrow movement is spoken by the **screen reader** (via focus and the accessible name). The page does not also call `speechSynthesis` for it.
- Space / `I` / `C` / `R` / `?` text goes to the live region (screen reader speaks it). `speechSynthesis` is used for these only if the student has turned on the page's own speech (Repeat / Stop / speed controls) and is not using a screen reader. How the page knows is open question Q1 in section 8.

## 6. Potential NVDA and Orca shortcut conflicts

**These are expected risks based on general knowledge of how the two screen readers work. They have not been checked against these keys in this project.** Each needs a real test (section 7). Plan §14 already lists this as a risk.

| Our key | Possible conflict | Why it matters | Mitigation to try |
|---|---|---|---|
| Esc | NVDA: Esc may leave focus mode and return to browse mode | One Esc might switch the mode instead of leaving the explorer, or both | Test whether the page sees the Esc at all; if not, add a second way out (the Explore button, Shift+Tab out of the tree) |
| Arrow keys | NVDA and Orca in browse/document mode use arrows to move through page text, not to move focus | Arrows might read lines of the page instead of moving the tree selection | Make sure the tree is entered in focus mode. `role="tree"` normally triggers this; test whether it does with automatic focus-mode switching turned off |
| Space | In browse mode a screen reader may treat Space on a control as activate/click | Could double-trigger or do nothing | Handle Space on keydown with `preventDefault()`; test in both modes |
| `I`, `C`, `R` | Single-letter quick navigation in browse mode. Each reader assigns letters to element types (for example headings, lists, landmarks, form fields) | If the tree is in browse mode, the reader would jump to the next such element instead of reading detail | Only valid in focus mode; confirm the mode before relying on them. Fall back to a configurable key set (plan §14, P1) |
| `?` | Some readers use Shift + `/` or a `?` command for their own help or for finding things | Could open reader help instead of ours | Test; keep the key list also reachable by a visible "Keys" button (needs Member 5) |
| `Home` | Moves to the start of a line or document in browse mode | Might scroll or read a line instead of jumping to the root | Same as arrows; test in focus mode |
| NVDA modifier (Insert / CapsLock) and Orca modifier (Insert / CapsLock) | Held by the reader for its own commands | Our keys must never need these. They are not used. | None needed |
| NVDA+Space (toggle focus/browse) and Orca equivalents | Student can leave focus mode by choice | The tree then stops responding to our keys | Document in the in-page help, and say it in the checklist |
| Browser shortcuts | `?` and `/` can open "quick find" in some browsers (Firefox) when focus is on the page, not in an input | Could intercept | Test in the browsers used with each reader |
| Alt, Ctrl, Cmd combinations | Browser and reader commands | We do not use any, and we pass them through | None |

### Suggested test pairs

The usual pairings to cover (confirm with the team which ones are available):

| Reader | Platform | Browser |
|---|---|---|
| NVDA | Windows | Firefox and Chrome |
| Orca | Linux | Firefox |

VoiceOver and JAWS are named in plan §3 as typical tools but are not in plan §7.6's testing requirement. They are listed as best-effort only.

## 7. Items that need real accessibility testing

Nothing in this list has been done. Marked per item with the plan phase where it is due.

| # | Item to test | Phase |
|---|---|---|
| T1 | The screen reader enters focus mode automatically when focus lands on the tree | Phase 3, round 1 |
| T2 | Each arrow key moves the selection and the new part's quick text is spoken exactly once | Phase 3 |
| T3 | Level and position ("2 of 3") are announced for parts | Phase 3 |
| T4 | Space, `I`, `C`, `R`, `?` are handled by the page and not intercepted | Phase 3 |
| T5 | Esc leaves the explorer in one press, and does not just change reader mode | Phase 3 |
| T6 | Home goes to the root and does not move the page scroll | Phase 3 |
| T7 | Boundary messages are spoken and focus does not move | Phase 3 |
| T8 | Live-region text is spoken once, not twice, and not before the student has stopped moving | Phase 3 |
| T9 | The page's own speech and the screen reader do not talk over each other | Phase 3 |
| T10 | Typing in the equation boxes triggers no explorer key and no speech | Phase 3 |
| T11 | Mathematical wording sounds right in each reader's voice ("x squared", "negative three") | Phase 3 |
| T12 | Whole journeys 6.1, 6.2, 6.3 (plan §6) can be completed keyboard-only | Phase 3 exit |
| T13 | Same, with visually impaired testers if available | Phase 4, round 2 |
| T14 | Key conflicts with the browsers used (section 6) | Phase 3 |

Test notes go in `docs/accessibility_checklist.md` (see its results table) and in the report section.

## 8. Assumptions and open questions

For teammates to confirm. `docs/contracts.md` is the authoritative shared contract and nothing here changes it; where an assumption below goes beyond the contract, it is Member 4's and is marked. If an answer needs a contract change, it is for Member 2 to decide. Full detail: `docs/explorer_contract.md`.

| # | Assumption / question | Who |
|---|---|---|
| A1 | Operators (`+`, `×`, `^`, `÷`) are the Add/Sub/Mul/Div/Pow nodes themselves, not separate child nodes; their children are the operands. A node gets the Operator role unless a more specific role applies (side, power, fraction, group multiplier). The operator's explanation ("Plus. It adds 3x and 5.") is then part of that node's detailed text | M1, M2 |
| A2 | An Equation node's children are the left side and the right side directly, so the "Left side" and "Right side" roles are given to those two children, not to an extra wrapper node. The side role wins over the Operator role for the top node of a side | M1, M2 |
| A3 | Roles not listed in plan §7.6 (Phase 1 uses the Operator role and the name "Multiplication" for the product `3x`; Phase 2 may give it friendlier wording; also roles for Group, Pow and Div wording) need agreed wording; `docs/contracts.md` only lists examples (`coefficient`, `variable`, `operator`, `constant`), so the full vocabulary is Member 4's extension, documented in `docs/explorer_contract.md`. The constant role is named `constant`, as in the contract | M4, M2 |
| A6 | Phase 2 roles. `group` (the brackets as a whole; its one child keeps its own role), `group_multiplier` (a bare number multiplying a Group, `2` in `2(x + 3)`; never `coefficient`, which is only a number multiplying `x`), `power` (a Pow node). A bare number in a power or fraction gets `base`, `exponent`, `numerator` or `denominator`; the exponent is never `constant` or `coefficient`. A Variable, Group or operator in those positions keeps its own role and its position is stated in its detailed and context text. The page should not assume a base, numerator or denominator can be found from `role` alone: use child order (index 0 / 1) | M4, M5 |
| A7 | DECIDED by `docs/contracts.md`: there is no `Fraction` node type (it is rejected as unsupported). `Div` is the one division node and the explorer gives every `Div` the fraction roles (`fraction`, `numerator`, `denominator`), so `x/2` and a stacked `x` over `2` are read the same. Open for Member 1: whether the parser ever needs to tell them apart | M1 |
| A4 | ExplorerNode `id` is unique within one response and stable for the same input. `docs/contracts.md` only requires a stable unique string, and its example ids are illustrative. Convention chosen by the explorer: the path, `n0`, `n0.1`, `n0.1.0` | M4 |
| A5 | All nodes are always expanded in the MVP | M5 |
| Q1 | How does the page decide between the screen reader speaking and `speechSynthesis` speaking (section 5)? | M5 |
| Q2 | Is there a visible "Keys" button as well as `?`? | M5 |
| Q3 | Is Explore a button that opens the tree below the input, or a separate view? This guide assumes the former | M5 |
| A8 | AST representation. `build_explorer_tree` accepts only plain `dict` nodes with `type` (str), `children` (a `list`; a tuple is rejected) and `span` (a list or tuple of two ints, bool excluded, `0 <= start < end`). A `dict` is required: a dataclass or object needs a `to_dict()` or an adapter in `_read_node`. Unknown extra keys are ignored. Whether a child's span lies inside its parent's is **not** checked. The span is validated and then dropped: it is not in the ExplorerNode | M1 |
| A9 | Node type names are exact and case-sensitive: `Equation, Number, Variable, Add, Sub, Mul, Div, Pow, Neg, Group`, which is exactly the contract's list. Any other name (`Fraction`, `Power`, `Negate`, `Paren`, `Frac`, ...) is rejected with its path | M1 |
| A10 | `Number.value` is the source spelling, a **string** (contract): ASCII digits with an optional decimal point (`3`, `2.50`, `.5`, `5.`). Anything else (`-3`, `+3`, `1e3`, `1,000`, spaces, non-ASCII digits, an `int` or `float`) raises `ExplorerError`. The spelling is kept unchanged as `value` and in speech (`2.50` is spoken `2.50`). `5.` is accepted: M1 to confirm whether the tokenizer can produce it. `Variable.value` is any non-empty string, spoken as given (the plan only has `x`) | M1 |
| A11 | Child order is reading order and is never re-sorted: Equation `[left, right]`, binary operators `[left operand, right operand]`, Pow `[base, exponent]`, Div `[numerator, denominator]`. Arity is exact: Group and Neg one child, every other operator two | M1 |
| A12 | Brackets: a student's brackets are `Group` nodes (the parser keeps them). Group span includes the brackets, its child's span does not. A Div whose parts were typed in brackets has no Group node: its own span includes them | M1 |
| A13 | Implicit multiplication: `3x` is `Mul(Number, Variable)`, `2(x+3)` is `Mul(Number, Group)`, `3x^2` is `Mul(3, Pow(x, 2))`. DECIDED (Phase 3 refinement): a number multiplying a `Pow` whose base is a `Variable` is its **coefficient** (`3x^2`, `x^2*3`); the exponent keeps the role `exponent`. A number multiplying a Group stays `group_multiplier`. A number multiplying any other power (`3(x+1)^2` with a Group base, `3*2^2`, `3(-x)^2`) or a product (`2 * 3x^2`) stays a plain `number` | M1 |
| A14 | Negative numbers: a Number is never negative (a signed spelling such as `"-3"` is rejected), so a minus is a `Neg` node: `Neg(Number 3)` and `Neg(Mul(3, x))` are accepted. `Mul(Neg(Number 3), x)` is **not** a coefficient (the 3 gets role `number`). Unary minus is assumed to bind looser than `^` (`-x^2` is `Neg(Pow)`) and `-3x` should be `Neg(Mul(3, x))`, where the 3 stays a coefficient; M1 to confirm | M1 |
| A15 | Division: `Div` is the only division node (contract) and gets the fraction roles; the 2 in `x/2` is a `denominator`. See A7 | M1 |
| A16 | Depth: at most 100 levels including the Equation (`MAX_DEPTH` in `engine/explore.py`, kept equal to the keyboard module's by a test). A deeper or cyclic tree raises `ExplorerError` | M1, M5 |

### Known limitations of the explorer wording

- **Group boundaries (fixed).** Whole-expression readings (the Equation's text, so the opening announcement and `R`, and the "It reads ..." sentence of a side) now close every group aloud with "end group": `2(3(x+1)+4)` reads "2 times the group 3 times the group x plus 1 end group plus 4 end group" and `2(3(x+1))+4` reads "... x plus 1 end group end group plus 4". Single-part texts (Space, `I`, `C`) keep the short wording. An exhaustive test (every tree up to 7 nodes) checks that expressions differing only in where groups sit are read differently.
- **Still ambiguous in speech:** a minus sign directly before a division (`x / -x * x`: negation of a product or of the divisor, which depends on how Member 1 builds the tree), a bare `Div` node used as a power base (the parser normally wraps it in a Group), and `the quantity ...` wording for operands that have no Group node (only synthetic trees). None of these arises from bracketed student input.
- **Plain number beside a product.** In `2 * 3x^2` the 2 is a "plain number" and is told it does not multiply x, although it multiplies the term 3x^2. Only a number directly beside `x`, `x^n` or a group gets a special role.
- **Variable names start a sentence in lower case** ("x is the variable.", "x squared means ..."), as is usual for a variable.
- **Long bases.** After "The base is B and the exponent is E", a base longer than six words is called "the base" in the squared/cubed sentence and in the exponent's detailed text. Texts read alone (context) still spell it out.

## 9. Implementation (Phase 3)

File: `static/explorer_keys.js` (Member 4). `static/app.js`, `index.html` and `style.css` are unchanged and remain Member 5's. The module has no dependencies and works as `window.ExplorerKeys` or `require()`.

### Integration interface for Member 5

```js
// tree = the ExplorerNode tree from POST /api/parse-expression
let explorer = null;

function openExplorer(tree) {
  try {
    explorer = ExplorerKeys.createView(treeContainerEl, tree, {
      onExit() { exploreButton.focus(); },   // REQUIRED. Esc calls this. You choose the target.
      liveRegion: exploreLiveEl,             // optional, persistent, separate from the result region
      mode: "screen-reader",                 // or "speech" (then pass speak / cancelSpeech)
      // speak: (t) => speechSynthesis.speak(new SpeechSynthesisUtterance(t)),
      // cancelSpeech: () => speechSynthesis.cancel(),
    });
  } catch (e) {
    // e.code: "tree-invalid" | "tree-too-deep" | "options-invalid" | "container-invalid"
    showSpokenError("The explorer could not be opened.");
    return;
  }
  treeContainerEl.hidden = false;            // container must be visible BEFORE open()
  const r = explorer.open();                 // focus to root + opening announcement
  if (!r.focused) { /* browser did not take focus: container hidden or detached */ }
}
```

### View lifecycle

- `createView` owns what it creates: the tree list inside the container, one `keydown` and one `focusin` listener on the container, and (unless you pass them) a live region and a help panel added to the container's parent. Children the container already had are never removed.
- **Calling `createView` again on the same container destroys the previous view first**, so a second Explore press cannot produce two trees, duplicate ids, two listeners or two controllers. The old view's controller is closed and its `open()` throws (`code: "destroyed"`). If the new tree is invalid, `createView` throws **before** touching anything and the old view keeps working.
- `view.destroy()` removes the listeners and the tree, removes the live region and help panel it created, restores the container's previous `role` and `aria-label`, and is safe to call twice. A live region or help panel that **you** supplied is kept: its text is cleared and its help list removed. After `destroy()`, no key reaches the controller.
- `destroy()` does **not** cancel page speech. Cancelling the page's own speech on open and on exit is the page's job.
- Esc does not destroy the view. It closes the controller, takes every tree item out of the tab order (`tabindex="-1"`) and calls `onExit`. Call `view.open()` to use the same view again (focus starts on the whole equation), or `view.destroy()` to discard it. If focus lands in a closed tree by Tab or click, keys do nothing until `open()`.
- Until `open()` is called, no tree item is a Tab stop.

### Exit callback (M1)

`onExit` is required. If it is missing or not a function, `createView` throws `options-invalid` ("createView requires an onExit callback that moves focus to the Explore button.") and builds nothing. The module does not guess a focus target: the page must move focus to the Explore button inside `onExit`, otherwise the student would be left in a tree that no longer responds.

### Announcement modes (M3)

- `"screen-reader"` (default): live region only. `speak` is never called.
- `"speech"`: `speak(text)` only, after `cancelSpeech()` if given. A throwing `cancelSpeech` is ignored. If `speak` throws, that announcement goes to the live region instead (nothing was spoken, so there is no double speech).
- `"speech"` without a `speak` function does not go silent: the view uses `"screen-reader"` and reports it in `view.mode` and `view.modeFallback`.
- An unknown `mode`, or a non-function `speak` / `cancelSpeech` / `schedule`, throws `options-invalid`.
- The module cannot tell whether a screen reader is running. Using `"speech"` while NVDA or Orca is on would double-speak focus changes; the page must choose the mode (open question Q1).

### Other integration requirements

- The container must be attached to the page, and (unless you pass both `liveRegion` and `helpPanel`) must have a parent element, or `createView` throws `container-invalid`.
- Pass the tree container only. Never pass `body` or a wrapper that also holds the text boxes: the key listener lives on the container, which is what keeps typing safe.
- CSS needed from Member 5: a visible non-colour-only marker for `[data-selected="true"]`, a visible focus outline on `[role="treeitem"]`, and nothing that overrides the `hidden` attribute on the help panel.
- Focus uses `focus({preventScroll: true})` followed by `scrollIntoView({block: "nearest"})`, so the page only scrolls when the item is off screen.
- Parse errors are handled by the page before `createView` is called.
- `ExplorerKeys.createController(tree)` can be used without the DOM adapter. `handleKey(event)` returns `{handled, preventDefault, action, moved, exit, announce, focusText, focusId, selection}`. `setFocus(id)` returns `{ok: false, handled: false, error: "unknown-node" | "closed"}` on failure.

### Key to action map

| Key | Action id | Result |
|---|---|---|
| ArrowUp | `parent` | focus parent, or boundary message |
| ArrowDown | `firstChild` | focus first child, or boundary message |
| ArrowLeft / ArrowRight | `previousSibling` / `nextSibling` | focus sibling, or boundary message |
| Space | `quick` | announce `spoken_quick` |
| I | `detailed` | announce `spoken_detailed` |
| C | `context` | announce `spoken_context` |
| R | `readAll` | announce root `spoken_detailed`, no focus move |
| Home | `root` | focus root, or "Already at the whole equation." |
| ? | `help` | announce key list, show help panel |
| Escape | `exit` | "Left the explorer.", `onExit()` |

Anything else is unhandled and not prevented. Missing text fields are announced from the role as described under Phase 3 clarifications, never as silence.
