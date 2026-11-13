# Accessibility test checklist

Owner: Member 4
Related: `docs/keyboard_guide.md` (what the keys should do), plan.md §6 (journeys), §7.8 (page), §13 (acceptance criteria).

**Status: manual screen-reader checklist not yet run.** Every box is unchecked. No NVDA or Orca testing has been performed. Browser-level integration checks were run on 13 November 2026; see the results below. Fill in the results table at the bottom only from real screen-reader sessions.

## Phase 3 status (read this first)

**NVDA and Orca testing: NOT YET PERFORMED.** The page (`static/index.html`, `app.js`, `style.css`) is now integrated with the parser API and Member 4's explorer. Browser automation verified tree updates, keyboard handling, focus return, live-region state and step-check responses, but it does not substitute for a screen reader. No OS/browser/screen-reader test session has been recorded; every manual box below stays unchecked. The results table remains reserved for real sessions.

### Implemented (Phase 3, `static/explorer_keys.js`)

- Full key map from `docs/keyboard_guide.md`: arrows, Space, I, C, R, Home, ?, Esc, with the boundary messages.
- Focus tracking over the real explorer tree, safe handling of unknown ids, malformed trees and malformed events.
- Three explanation depths on Space / I / C using `spoken_quick`, `spoken_detailed`, `spoken_context`.
- DOM adapter: `role="tree"` / `treeitem` / `group`, `aria-label` (quick text), `aria-level`, `aria-posinset`, `aria-setsize`, `aria-expanded`, `aria-selected`, roving `tabindex`, an `aria-live="polite"` region, a visible key-help panel, and a `data-selected` hook for a non-colour selection style.
- One-channel announcement strategy (screen-reader mode vs speech mode) so the screen reader and `speechSynthesis` never both speak the same event.
- View lifecycle: `destroy()` plus automatic replacement, so rebuilding the explorer on the same container never duplicates the tree, ids, listeners, live region or help panel.
- Required `onExit` callback (validated), tab order removed on Esc, `open()` reports whether the browser took focus.
- Speech-mode safeguards: fallback to the live region when `speak` is missing or throws.
- Role-based names when a node has no quick text, boundary message on the first boundary of a held key, depth limit of 100 levels with a coded error, AltGr printable characters accepted when `getModifierState("AltGraph")` reports it.

### Automated test results

| Suite | Command | Result |
|---|---|---|
| API, parser, explorer and backend regression suite | `python -m pytest -q` | 1880 passed, 0 failed on 13 November 2026 |
| Keyboard logic and DOM adapter (fake DOM) | `node --test tests/js/explorer_keys.test.js` | 87 passed, 0 failed on 13 November 2026 |
| Browser integration (Chromium, local FastAPI server) | Playwright interaction checks | Parser-generated tree, node-specific Space/I/C/R, full `?` help and Repeat, Stop/cancel, Home/Escape/re-entry, parse error, valid/invalid step responses, and 390px viewport checked. Real SpeechSynthesis emitted start/end for the short node announcement; the long help utterance started but was cancelled before completion. Physical audio was not captured. This is not a screen-reader test. |

The JS tests run against a hand-written fake DOM, not a browser. The fake fires events the way the DOM does (bubbling, no `focusin` when already focused), but it cannot show real focus, scrolling, live-region or `speechSynthesis` behaviour. They prove the logic and the attributes set. They do not prove how a browser or screen reader behaves.

### Still needs manual verification (screen reader required)

Everything in sections 1 to 8 below, in particular keyboard_guide T1 to T14. The riskiest ones: focus-mode switching (T1), Esc handling (T5), Space and letter keys in browse mode (T4), single announcement of live-region text (T8), screen reader versus page speech (T9).

### NVDA and Orca procedure (reproducible)

1. Record: OS and version, browser and version, screen reader and version, speech rate.
2. Start the app: `uvicorn app:app`, open the page.
3. NVDA (Windows 10/11, Firefox and Chrome) or Orca (Linux, Firefox). Leave NVDA's "automatically set system focus to focusable elements" and automatic focus-mode switching at defaults first, then repeat once with automatic focus-mode switching **off**.
4. Keyboard only. For each equation `3x + 5 = 14`, `2x + 3 = 9`, `2(x + 3) = 10`, `x^2 = 4`, `(x + 1) / 2 = 3`: type it, press Explore, then press: Down, Down, Right, Up, Left, Home, Space, I, C, R, ?, Esc. After each key write down what was heard (copy NVDA's speech viewer or Orca's debug output if possible).
5. At each boundary (Up on the root, Down on a leaf, Left on the first sibling, Right on the last) check the message is heard once and focus did not move.
6. Check nothing is spoken twice, and with the page's own speech switched on in "speech" mode with the screen reader running, that you hear one voice at a time.
7. Hold an arrow key down: selection should move and stop at the edge without a pile of repeated messages.
8. Record failures and key conflicts in the tables at the bottom. Then work through sections 1 to 8.
9. Do not tick any box that was not observed.

### Known limitations

- Not tested with NVDA or Orca; automated Chromium checks do not verify actual assistive-technology speech (see above).
- `createView` assumes the tree is fully expanded (guide A5).
- The page provides an explicit screen-reader / browser-speech mode selector; the page cannot detect whether a screen reader is running, so the student must choose the appropriate mode.
- Selection styling and focus outline are CSS work for Member 5; the module only sets `data-selected`.
- The keyboard module's JS fixtures (`tests/js/explorer_trees.json`) come from hand-written ASTs that match the real parser's output (checked by `tests/test_parser_integration_explorer.py`). The browser integration check also explored trees returned by the real parse API.
- AltGr handling relies on `getModifierState("AltGraph")`. Real Ctrl+Alt combinations on AltGr layouts may also report AltGraph, so shortcut pass-through is not guaranteed there. Not verified across real browsers and keyboard layouts. Letter keys I, C, R match the typed character, so they do not work on layouts that do not produce those letters.
- Chrome is reported to sometimes drop an utterance spoken straight after `speechSynthesis.cancel()` (speech mode only). Unverified here.
- In screen-reader mode, opening and leaving the explorer both move focus and write the live region, so a screen reader may speak the focus change and the live text one after the other (or cut one off). Needs checking with NVDA and Orca.
- A screen reader user who toggles to browse mode (NVDA+Space) will stop receiving the page's keys; this must be stated in the in-page help.

## How to use

- Run the checklist once per screen reader + browser pair (record the pair in the results table).
- Use only the keyboard. Do not touch the mouse or trackpad. If you have to, record it as a failure.
- Mark each item Pass / Fail / N/A and add a note for every Fail (what you pressed, what you heard, what you expected).
- Run once in Phase 3 (round 1) and again in Phase 4 (round 2, ideally with visually impaired testers).
- Items tagged **[P0]** map to the plan §13 acceptance criteria. The rest are quality checks.

## Setup

- [ ] Server started with `uvicorn app:app`, page opens
- [ ] Screen reader, version and browser recorded
- [ ] Speech rate set to the tester's normal rate
- [ ] Browser zoom at 100% to begin with

## 1. Keyboard-only operation

- [ ] **[P0]** Every control (both text boxes, Check, Explore, Repeat, Stop, More detail, speed control) can be reached with Tab and Shift+Tab
- [ ] **[P0]** Every control can be activated with Enter or Space as appropriate
- [ ] Tab order follows reading order: Previous step, Current step, Check, Explore, then result controls
- [ ] No keyboard trap anywhere. The student can always Tab or Esc out
- [ ] Journey 6.1 (check a step) completed with keyboard only
- [ ] Journey 6.2 (understand a mistake) completed with keyboard only
- [ ] Journey 6.3 (explore an equation) completed with keyboard only
- [ ] Pressing Enter inside a text box does something predictable (check or nothing), not both
- [ ] No time limits anywhere

## 2. Screen-reader announcements

- [ ] **[P0]** On page load: title and first field are announced, e.g. "Algebra Step Checker. Previous step, text box."
- [ ] Both text boxes have a spoken label
- [ ] **[P0]** After Check, the result is announced once, without moving focus (aria-live)
- [ ] The result is not announced twice (live region + speech)
- [ ] Buttons announce their name and role
- [ ] Error messages are announced when they appear
- [ ] Nothing is announced while the student is typing
- [ ] Headings and landmarks let the student jump to the result and the explorer

## 3. Focus visibility and management

- [ ] Focus outline is visible on every control, including the tree items
- [ ] Focus outline is visible against both the page and the control background
- [ ] After Check, focus stays where the student was (or goes somewhere announced)
- [ ] **[P0]** Opening the explorer puts focus on the whole equation
- [ ] Esc returns focus to the Explore button
- [ ] Focus is never lost to the top of the page
- [ ] Re-opening the explorer starts at the whole equation again

## 4. Explorer navigation (see `docs/keyboard_guide.md` §2–§3)

- [ ] **[P0]** ↓ moves to the first child
- [ ] **[P0]** ↑ moves to the parent
- [ ] **[P0]** ← and → move between siblings in left-to-right order
- [ ] **[P0]** Each part's role is announced correctly (coefficient only for a number multiplying x)
- [ ] Level and position are announced (for example "level 2, 1 of 2")
- [ ] Space reads the quick text
- [ ] `I` reads the detailed text
- [ ] `C` reads the context text
- [ ] `R` reads the whole equation and does not move focus
- [ ] `Home` jumps to the whole equation and does not scroll the page
- [ ] `?` lists the keys
- [ ] Esc leaves the explorer in a single press
- [ ] Boundary messages are spoken at each edge and focus does not move:
  - [ ] ↑ on the root
  - [ ] ↓ on a part with no children
  - [ ] ← on the first sibling
  - [ ] → on the last sibling
  - [ ] Home on the root
- [ ] Typing in a text box never triggers explorer keys
- [ ] Explorer keys with Ctrl, Alt or Cmd held are not captured
- [ ] No key conflicts found with the screen reader. Record each conflict in the results table
- [ ] Works with the equations: `3x + 5 = 14`, `2x + 3 = 9`, `2(x + 3) = 10`, `x^2 = 4`, `(x + 1) / 2 = 3`

## 5. Explanation clarity

Read aloud by the screen reader or speech, not on screen.

- [ ] **[P0]** Quick text is one short sentence and names the role
- [ ] Detailed text explains the part in terms of its neighbours
- [ ] Context text says where the part sits ("on the left side", "added to 3x")
- [ ] Numbers and symbols are spoken as words ("x squared", "negative three", "three x")
- [ ] No wording depends on layout or sight ("above", "to the left of the line")
- [ ] Wording does not sound confusing in the screen reader's voice
- [ ] Tester can state in their own words what the part is after hearing it
- [ ] Tester rates clarity 1–5 per equation (record in results)

## 6. Speech interaction

- [ ] **[P0]** Results can be repeated (Repeat)
- [ ] **[P0]** Speech can be stopped at once (Stop)
- [ ] Speed control works and the setting is announced
- [ ] The page's speech does not talk over the screen reader
- [ ] Speech never starts while typing
- [ ] Speech stops when the student starts a new check or leaves the explorer
- [ ] If speech is unavailable in the browser, the text is still available and a message says so

## 7. Error handling

- [ ] **[P0]** Malformed input gives a clear spoken error (for example "Unexpected symbol y at position 4. Only the variable x is supported.")
- [ ] The error says what is wrong and where, in plain words
- [ ] Focus goes to the box with the problem, or the error is announced and the box is named
- [ ] Empty fields give a spoken error
- [ ] Explore with invalid input gives the error and does not open the explorer
- [ ] "Unable to determine" results are announced clearly and say what to try next
- [ ] Server unavailable gives a spoken message, not silence
- [ ] The student can fix the input and try again without reloading

## 8. High contrast and text resizing

- [ ] Text is readable at 200% browser zoom without horizontal scrolling or overlapping
- [ ] Text is readable with browser text size increased only
- [ ] No content disappears at 400% zoom (single column)
- [ ] OS high contrast mode (Windows Contrast themes) keeps all controls and focus outlines visible
- [ ] Dark or inverted colours are readable
- [ ] No information is conveyed by colour alone (valid / invalid has text, not just green / red)
- [ ] Text-to-background contrast checked (normal text at least 4.5:1)
- [ ] Focus outline and control borders at least 3:1 against what is next to them
- [ ] Click and touch targets are large enough for imprecise pointing

## Results table

Fill in only from sessions that were actually run.

| Date | Tester | Screen reader + version | Browser | OS | Round | Items passed / failed | Notes and conflicts found |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

### Failures log

| # | Item | What was pressed | What was heard | What was expected | Severity | Fixed? |
|---|---|---|---|---|---|---|
| | | | | | | |

### Key-conflict log

| Key | Screen reader | Mode (browse / focus) | What happened | Workaround |
|---|---|---|---|---|
| | | | | |
