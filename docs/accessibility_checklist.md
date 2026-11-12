# Accessibility test checklist

Owner: Member 4
Related: `docs/keyboard_guide.md` (what the keys should do), plan.md §6 (journeys), §7.8 (page), §13 (acceptance criteria).

**Status: not yet run.** Every box is unchecked. No NVDA or Orca testing has been performed. Fill in the results table at the bottom only from real sessions.

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
