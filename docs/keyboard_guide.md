# Keyboard guide

Owner: Member 4
Source of truth: plan.md §7.6 (explorer) and §7.8 (page). This file turns those sections into a precise spec that Member 5 can build the tree UI against.

**Status:** specification only. Nothing here has been tested with NVDA or Orca yet. Section 7 lists what still has to be tested with real screen readers. Statements about screen-reader behaviour in sections 5 and 6 are design intent or expectations, marked as such.

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
| `Home` anywhere else | Focus moves to the root, then the root's quick text is read | (root quick text) |
| `R` | Reads the root's quick text. Focus does **not** move | (root quick text) |
| Esc | Tree is hidden or collapsed, focus returns to the Explore button, tree state is discarded | "Left the explorer." |
| Explore pressed with an empty box | Explorer does not open, focus stays on the box | The parser's error message |
| Explore pressed with unparseable input | Explorer does not open | The parser's spoken error (plan §7.1) |
| Re-opening the explorer | Focus starts on the whole equation, never on the previous position | (root quick text) |
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
| Explorer opens | "Equation explorer. [root quick text]. Press question mark for keys." Focus is on the root |
| Arrow key moves | The new part's quick text, plus level and position as given by the screen reader |
| Space | Quick text again (live region) |
| `I` | Detailed text (live region) |
| `C` | Context text (live region) |
| Boundary | The message from section 3 |
| Esc | "Left the explorer." and focus is on the Explore button |

### Speech and screen reader at the same time

Plan §7.8 says speech uses the browser's `speechSynthesis`. Screen-reader users must not hear two voices at once. Proposal for Member 5 to confirm:

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

For teammates to confirm. Nothing here changes `docs/contracts.md`; if any answer needs a contract change, it is for Member 2 to decide.

| # | Assumption / question | Who |
|---|---|---|
| A1 | Operators (`+`, `×`, `^`, `÷`) are the Add/Sub/Mul/Div/Pow nodes themselves, not separate child nodes; their children are the operands. A node gets the Operator role unless a more specific role applies (side, power, fraction, group multiplier). The operator's explanation ("Plus. It adds 3x and 5.") is then part of that node's detailed text | M1, M2 |
| A2 | An Equation node's children are the left side and the right side directly, so the "Left side" and "Right side" roles are given to those two children, not to an extra wrapper node. The side role wins over the Operator role for the top node of a side | M1, M2 |
| A3 | Roles not listed in plan §7.6 (Phase 1 uses the Operator role and the name "Multiplication" for the product `3x`; Phase 2 may give it friendlier wording; also roles for Group, Pow and Div wording) need agreed wording; the explorer will define them and they will be added here | M4 |
| A4 | ExplorerNode `id` is unique within one response and stable for the same input. The exact format is not set in plan §10 | M2 |
| A5 | All nodes are always expanded in the MVP | M5 |
| Q1 | How does the page decide between the screen reader speaking and `speechSynthesis` speaking (section 5)? | M5 |
| Q2 | Is there a visible "Keys" button as well as `?`? | M5 |
| Q3 | Is Explore a button that opens the tree below the input, or a separate view? This guide assumes the former | M5 |
