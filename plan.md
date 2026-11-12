# Audio-First Algebra Step Checker — Project Plan & PRD (v4)

## 1. Overview

An accessible, keyboard-and-audio tool that helps blind and visually impaired students learn algebra. It does two things:

1. **Step checker:** the student types two consecutive steps. The tool says whether the step is correct, what was done, and, if it's wrong, exactly where it went wrong.
2. **Expression explorer:** the student walks through a single equation with the arrow keys and hears what every part is. For example: "this is a constant", "this is the variable being multiplied by the coefficient 3", "these brackets group x and 2 together".

The goal is to make algebra's **structure and reasoning** understandable, not just audible.

**Key design decisions** (changes from the original PRD):

- The tree-diff + 10-rule engine is replaced by _algebraic inference_ with SymPy. It's simpler, more accurate, and doesn't care about term order.
- **No ML or AI in the core.** Every verdict, operation and mistake label comes from exact, testable maths. A trained mistake model and LLM rephrasing are future features (§15).
- Simple stack: one FastAPI app and one accessible HTML/JS page.

The full list of changes from the original PRD, and the reason for each, is in §16.

## 2. Problem

Algebra uses layout to carry meaning: brackets group terms, superscripts are powers, and fractions stack. A screen reader flattens all of this into one line of speech. A blind student can hear "3 x plus 5 equals 14" and still not know:

- which number is a coefficient and which is a constant,
- what is grouped inside brackets,
- what changed between two lines,
- whether the same operation was done to both sides,
- where exactly a wrong step went wrong.

## 3. Users

- **Primary:** blind and low-vision students learning algebra, usually with a screen reader (NVDA, JAWS, Orca, VoiceOver).
- **Secondary:** teachers, tutors, parents, accessibility support staff.

## 4. Scope

**In scope (MVP):**

- one variable `x` and one `=`
- `+ − * /`, powers (`^` or `**`), brackets
- implicit multiplication (`3x`, `2(x+1)`)
- linear and simple quadratic equations

**Out of scope (MVP):** multiple variables, inequalities, roots, logs, handwriting, spoken input, deciding correctness with AI.

## 5. Core principles

- **SymPy decides correct vs incorrect.** False-valid stays at 0 by design.
- A mistake type is named only when a fixed check proves it. Otherwise: "incorrect, here's the correct result."
- Explanations are generated only from verified, structured data.
- "Unable to determine" is preferred over guessing.
- Everything works with the keyboard alone; nothing depends on colour or sight.

**Definitions:**

- **Valid:** both equations have the same real solution set, and nothing was divided or multiplied by an expression that can be zero.
- **Invalid:** the solution sets differ.
- **Unable to determine:** the input is outside the supported scope, or SymPy can't decide and random-value testing is inconclusive.

## 6. User journeys

### 6.1 Check a step

1. Student opens the page; the screen reader announces "Algebra Step Checker. Previous step, text box."
2. Types `3x + 5 = 14`, presses Tab, types `3x = 9`, presses Tab to **Check**, presses Enter.
3. Hears: _"Correct! You subtracted 5 from both sides. 14 minus 5 is 9."_
4. Can press **Repeat**, **Stop**, or **More detail**.

### 6.2 Understand a mistake

1. Student enters `3x + 5 = 14 → 3x = 10`.
2. Hears: _"Not quite. You subtracted 5 on the left, so the right side should be 14 minus 5, which is 9, not 10."_
3. Fixes the line and checks again.

### 6.3 Explore an equation

1. Student types `2(x + 3) = 10` and presses **Explore**.
2. Moves around with the arrow keys and hears each part's meaning (§7.6).
3. Presses Esc to return.

## 7. Features and requirements

### 7.1 Input & parser — `engine/parser.py` (P0)

- Two labelled text fields, Previous and Current, both announced by screen readers.
- Tokenizer with a whitelist: digits, decimals, `x`, `+ - * / ^ ** ( ) =`, spaces.
- Clear, spoken error messages, e.g. "Unexpected symbol y at position 4. Only the variable x is supported."
- Own recursive-descent parser. It supports implicit multiplication, unary minus, powers, nested brackets and exactly one `=`.
- Output: an **OwnAST** (Number, Variable, Add, Sub, Mul, Div, Pow, Neg, Group, Equation) with source positions. It keeps the student's brackets exactly as typed.
- `to_sympy()` converts the tree with `evaluate=False`.
- Never uses `eval` or `parse_expr`.

### 7.2 Verifier — `engine/verifier.py` (P0)

- Solve both equations with `solveset(L − R, x, S.Reals)` and compare the results.
- Fallback: if SymPy can't solve, test about 20 random values of x and check the equations agree on each.
- Domain check: dividing by an expression containing x raises a "possible zero divisor" warning.

### 7.3 Inference: what did the student do? — `engine/infer.py` (P0)

For previous `L = R` and current `L' = R'`:
| Check | Meaning | Replaces PRD rule |
|---|---|---|
| `L−L' == R−R'`, a constant c | add/subtract c on both sides | R01, R02 |
| `L/L' == R/R'`, a constant k | multiply/divide both sides by k (flag if k contains x) | R03, R04, R10 |
| `L'≡R` and `R'≡L` | sides swapped | R09 |
| `L'≡L` and `R'≡R` | rewrite: expand / factor / collect like terms / simplify | R05–R08 |
| `(L'−R') = k·(L−R)` | same operation on both sides (generic) | — |

Output: `InferenceResult {operation, operand, applied_to, expected, got, warnings}`.

### 7.4 Mistake checks — `engine/mistakes.py` (P0, runs only when invalid)

Each check either proves its mistake or stays silent. The first match wins; if none match, the label is `null`.

| Label                              | How it's detected                                                                | Example                     |
| ---------------------------------- | -------------------------------------------------------------------------------- | --------------------------- |
| `one_side_only`                    | One side changed by an operation, the other unchanged                            | `2x = 8 → x = 8`            |
| `sign_error`                       | `L−L' = −(R−R')`                                                                 | `x + 5 = 9 → x = 14`        |
| `wrong_inverse_op`                 | Left changed by a ratio k, right by a difference k                               | `2x = 8 → x = 6`            |
| `arithmetic_error`                 | Operation clear from one side; applying it to the other gives a different number | `3x + 5 = 14 → 3x = 10`     |
| `partial_distribution`             | Replacing `a(b + c)` with `ab + c` reproduces the student's line                 | `2(x+3) = 10 → 2x + 3 = 10` |
| `coefficient_error`                | Like terms combined, but the new coefficient ≠ sum of the old ones               | `2x + 3x = 10 → 6x = 10`    |
| `exponent_error`                   | Replacing `(a + b)^2` with `a^2 + b^2` reproduces the student's line             | `(x+1)^2 = 9 → x^2 + 1 = 9` |
| `divide_by_variable`               | Inferred ratio contains x                                                        | `x^2 = x → x = 1`           |
| `lost_solution` / `extra_solution` | Solution set got strictly smaller / larger                                       | `x^2 = 4 → x = 2`           |

Output: `MistakeResult {label, expected, got, location} | null`.

### 7.5 Explanations & speech text — `engine/explain.py`, `engine/speak.py` (P0)

- Templates for each operation and each mistake label, at two levels (concise / detailed). Every number comes from the verified JSON.
  - **Valid:** "Correct. You subtracted 5 from both sides. 14 minus 5 is 9."
  - **Invalid, mistake named:** "Not quite. You subtracted 5 on the left, so the right side should be 14 minus 5, which is 9, not 10."
  - **Invalid, no mistake named:** "This step is incorrect. The first equation gives x = 3, but yours gives x = 10 over 3."
  - **Unable to determine:** "I can see the equation changed, but I can't work out how. Try a smaller step."
- `speak.py` turns math into words:
  - `x^2` → "x squared"
  - `-3` → "negative three"
  - `3x` → "three x"
  - `(x+2)` → "the group x plus 2"

### 7.6 Expression explorer (side feature) — `engine/explore.py` + frontend (P0 basic, P1 advanced)

Helps a student who is stuck understand an equation part by part.

**What each part is called:**
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

A number is labelled a coefficient only when it multiplies x. In `3x + 5`, 3 is a coefficient and 5 is a constant.

**Keyboard controls:**
| Key | Action |
|---|---|
| ↑ | Move to the bigger part (parent) |
| ↓ | Move inside (first child) |
| ← / → | Previous / next part at the same level |
| Space | Read the selected part (quick) |
| `I` | More information (detailed) |
| `C` | Context: how this part connects to the rest ("This 5 is added to 3x on the left side") |
| `R` | Read the whole equation again |
| `Home` | Jump back to the whole equation |
| `?` | List the keys |
| Esc | Leave the explorer |

**Three depths for every part:**

- **Quick:** "3 is the coefficient of x."
- **Detailed:** "3x means 3 multiplied by x. 3 is the coefficient and x is the variable."
- **Context:** "This term is on the left side and is added to 5."

The explorer uses the ARIA `tree` pattern (`role="tree"` / `treeitem`), so screen readers understand it natively. Keys must be tested with NVDA and Orca for conflicts.

### 7.7 API — `app.py` (FastAPI) (P0)

| Method | Path                    | Purpose                                     |
| ------ | ----------------------- | ------------------------------------------- |
| POST   | `/api/check-step`       | verdict + inference + mistake + explanation |
| POST   | `/api/parse-expression` | explorer tree with spoken labels            |
| GET    | `/api/rules`            | supported operations and mistake labels     |
| GET    | `/api/health`           | backend check                               |

### 7.8 Accessible page — `static/` (P0)

- A result region with `aria-live="polite"`, so results are announced without moving focus.
- Speech uses the browser's `speechSynthesis`, with Repeat / Stop / speed controls. It never speaks while the student is typing.
- Visible focus, high contrast, resizable text, no information shown by colour alone, no time limits.

## 8. Architecture

```
Text input ─► Parser (own tree) ─► to_sympy ─┬─► Verifier ─► correct / incorrect / unknown
                                             ├─► Inference ─► what was done
                                             └─► Mistake checks (only if incorrect)
               all results ─► Explanation templates ─► text ─► speech + screen reader
Own tree ─► Explorer (roles + spoken labels) ─► keyboard tree on the page
```

## 9. Repo layout

```
algebra_checker/
  engine/  parser.py verifier.py infer.py mistakes.py explain.py speak.py explore.py
  app.py   cli.py
  static/  index.html app.js style.css
  tests/   test_parser.py test_verifier.py test_infer.py test_mistakes.py
           test_explain.py test_explore.py test_api.py cases.csv
  docs/    contracts.md syntax.md keyboard_guide.md limitations.md test_report.md
  report/  final_report.md  slides/
```

## 10. Shared contracts (frozen in Phase 0, in `docs/contracts.md`)

- **OwnAST node:** `{type, value?, children[], span:[start,end]}`
- **InferenceResult:** `{operation, operand, applied_to, expected, got, warnings[]}`
- **MistakeResult:** `{label, expected, got, location} | null`
- **CheckStepResponse:** `{status: valid|invalid|unknown, inference, mistake, explanation:{concise, detailed}}`
- **ExplorerNode:** `{id, type, role, value, spoken_quick, spoken_detailed, spoken_context, children[]}`

Each member writes against mock versions of these until the real modules land.

## 11. Team split (5 members)

Every member owns real code **and** their share of the docs, report and presentation. No one is a docs-only member.

| Member       | Area                                                                    | Code responsibilities                                                                                                                                                                                                                      | Docs & presentation                                                                                                                        |
| ------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Member 1** | **Parser & AST**                                                        | Input grammar, tokenizer, parsing, original tree with positions, `to_sympy()` (normalized form), input error messages, `speak.py` (math → words), parser tests                                                                             | `docs/syntax.md` (what students can type); report section on parsing; presents the parser and the "math to words" demo                     |
| **Member 2** | **Inference & mistake rules** (replaces "AST comparison & rule engine") | `infer.py` (all 5 inference checks), operation-based mistake checks (one side only, sign, wrong inverse, arithmetic, partial distribution, coefficient, exponent), `cli.py`                                                                | `docs/contracts.md` (owns the shared formats); report section on how operations and mistakes are detected; presents the step-checker logic |
| **Member 3** | **Symbolic verification & testing**                                     | `verifier.py` (solution sets, random-value fallback, zero-divisor warnings), solution-based mistake checks (divide by variable, lost/extra solution), `explain.py` templates, owns `tests/cases.csv` (150+ step pairs) and the CI test run | `docs/test_report.md`, `docs/limitations.md`; report sections on correctness and evaluation metrics; presents the test results             |
| **Member 4** | **Expression exploration & accessibility**                              | `explore.py` (roles, three explanation depths, context text), keyboard behaviour spec, screen-reader behaviour, NVDA/Orca testing of the whole app, accessibility test checklist                                                           | `docs/keyboard_guide.md`; report section on accessibility and user testing; presents the live explorer demo                                |
| **Member 5** | **Frontend, speech & integration**                                      | `app.py` (API), `static/` page, speech controls (Repeat/Stop/speed), explorer tree UI, end-to-end workflow, `test_api.py`                                                                                                                  | API section of the docs and a README with setup instructions; report sections on architecture and UI; presents the end-to-end demo         |

**Shared by everyone:**

- Each member adds at least 30 rows to `tests/cases.csv`, covering their own area.
- Each member writes their own section of `report/final_report.md` and 2–3 slides for their part.
- Report editing and slide-deck assembly **rotate**: Member 1 drafts the outline in Phase 0, and Members 3 and 5 merge everything in Phase 4. Everyone rehearses together.
- Every pull request is reviewed by one other member before merging.

**Pairing points:**

- **M1↔M4:** the tree shape drives the explorer.
- **M1↔M3:** `to_sympy()` output feeds the verifier.
- **M2↔M3:** mistake checks and explanation templates share the result formats.
- **M4↔M5:** explorer JSON drives the keyboard tree on the page.
- **M3↔M5:** explanation JSON drives what is shown and spoken.

## 12. Phases

Phase timing is flexible. Phase 1 is the ~10-hour partial demo.

### Phase 0 — Setup & agreement

**Goal:** agree on scope and formats, and set up the repo.

| Member | Tasks                                                                                 |
| ------ | ------------------------------------------------------------------------------------- |
| M1     | Write the grammar; list supported syntax; draft the report outline                    |
| M2     | Write `docs/contracts.md` with example JSON for every format                          |
| M3     | Create `tests/cases.csv` with the PRD §11.1 table plus 20 cases; set up pytest        |
| M4     | Write the explorer role table and keyboard map; check for screen-reader key conflicts |
| M5     | Repo, folder structure, FastAPI skeleton serving a blank accessible page              |

**Exit:** contracts frozen, repo runs, everyone can run `pytest`.

### Phase 1 — First working demo (~10 h)

**Goal:** the smallest version that works end to end.

| Member | Tasks                                                                                     |
| ------ | ----------------------------------------------------------------------------------------- |
| M1     | Parser for linear equations with implicit multiplication; `to_sympy()`                    |
| M2     | Add/subtract and multiply/divide inference; `arithmetic_error` and `one_side_only` checks |
| M3     | Solution-set verifier; valid / invalid explanation templates                              |
| M4     | Basic explorer roles (coefficient, variable, constant, operator)                          |
| M5     | `/api/check-step` wired up; page with two inputs, Check button, live region and speech    |

**Exit:** `3x+5=14 → 3x=9` is reported and spoken as correct; `→ 3x=10` is reported and spoken as an arithmetic error.

### Phase 2 — Full engine

**Goal:** everything in §7.1–7.5 works.

| Member | Tasks                                                                                           |
| ------ | ----------------------------------------------------------------------------------------------- |
| M1     | Powers, nested brackets, fractions, unary minus, all error messages; `speak.py`                 |
| M2     | Swap, rewrite and generic inference; remaining operation-based mistake checks                   |
| M3     | Random-value fallback, zero-divisor warnings, solution-based mistake checks, detailed templates |
| M4     | Explorer roles for groups, powers and fractions; context text                                   |
| M5     | `/api/parse-expression`, `/api/rules`; error and "unable to determine" states on the page       |

**Exit:** every row in `tests/cases.csv` passes (150+).

### Phase 3 — Explorer & full UI

**Goal:** both features are fully usable with the keyboard alone.

| Member | Tasks                                                                        |
| ------ | ---------------------------------------------------------------------------- |
| M1     | Spoken read-back of the parsed equation ("I read this as …") before checking |
| M2     | "More detail" explanations for each operation                                |
| M3     | End-to-end tests for both user journeys                                      |
| M4     | Full keyboard map, three depths, `?` help; NVDA and Orca testing round 1     |
| M5     | Explorer tree UI, Repeat/Stop/speed, focus management, high contrast         |

**Exit:** all three user journeys (§6) work keyboard-only in NVDA and Orca.

### Phase 4 — Testing, docs & presentation

**Goal:** a reliable, documented, demo-ready project.

| Member | Tasks                                                                                            |
| ------ | ------------------------------------------------------------------------------------------------ |
| M1     | `docs/syntax.md`; parser section of the report; slides                                           |
| M2     | Contracts final version; inference/mistakes report section; slides                               |
| M3     | Test report with metrics, limitations doc; correctness report section; merges the report         |
| M4     | Accessibility testing round 2 (ideally with visually impaired users); keyboard guide; slides     |
| M5     | README, API docs; architecture/UI report section; merges the slide deck; runs the demo rehearsal |

**Exit:** P0 acceptance tests pass, docs complete, final demo rehearsed by all five.

## 13. Testing & metrics

- **Unit tests:** one file per module. Every mistake check has a positive example, a near-miss that must _not_ trigger, and an edge case.
- **Shared catalogue:** `tests/cases.csv`, run by one parametrized pytest. It includes the PRD §11.1 table plus:
  - `x^2 = x → x = 1` → invalid + divide_by_variable
  - `2(x+3)=10 → 2x+3=10` → invalid + partial_distribution
  - `x+5=9 → x=14` → invalid + sign_error
  - `x+2=5 → 5=x+2` → valid (swap)
  - malformed input → clear error
- **Metrics:**
  - false-valid rate (must be 0)
  - false-invalid rate
  - share of "unable to determine" results
  - share of incorrect steps that get a mistake name, and the accuracy of those names
  - keyboard-task completion rate, time and number of key presses
  - clarity ratings from testers
- **Commands:**
  - `pytest`
  - `python cli.py "3x+5=14" "3x=10"`
  - `uvicorn app:app`, then run the user journeys using only the keyboard

**Acceptance criteria (P0):**

1. Both equations can be entered and checked using only the keyboard.
2. Malformed input gives a clear spoken error.
3. Supported steps return correct / incorrect / unknown as expected.
4. Explanations match the verified results.
5. Results are spoken and can be repeated or stopped.
6. The explorer can be navigated, and each part's role is announced correctly.

## 14. Risks

| Risk                                     | Mitigation                                                                                           |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| A mistake check fires wrongly            | Each check must reproduce the student's line exactly; near-miss tests for every check                |
| Many incorrect steps get no mistake name | Acceptable: the generic message still helps. Log these cases to guide new checks or the future model |
| SymPy can't solve an equation            | Random-value fallback, otherwise "unable to determine"                                               |
| App keys clash with screen-reader keys   | Standard ARIA tree pattern; test early; configurable keys (P1)                                       |
| Members' modules don't fit together      | Contracts frozen in Phase 0, mocks, integration at the end of every phase                            |
| Report and slides rushed at the end      | Each member writes their section as their module finishes, not in Phase 4 only                       |

## 15. Future features to explore

1. **Trained mistake model (AI).** A classifier that names mistakes the fixed checks miss.
   - Trained on 50–100k synthetic, auto-labelled step pairs; equations can be seeded from DeepMind `mathematics_dataset`.
   - Tested on ~100 real student mistakes (e.g. from Eedi or MathDial; check licenses).
   - Models: scikit-learn gradient boosting first, then fine-tuned DistilBERT or `t5-small`.
   - It never decides correctness, and is shown only at confidence ≥ 0.7.
2. **LLM rephrasing** of explanations into more natural speech, accepted only if every number matches the verified result.
3. **Graduated hints when stuck:**
   - "Look at the number added to 3x."
   - "What would remove it?"
   - "Do the same to both sides."
4. **Practice mode:** generated problems solved one step at a time, with feedback after each step.
5. **Spoken input:** say "three x plus five equals fourteen" (Whisper); the app reads it back to confirm.
6. **Handwriting / photo input** with read-back confirmation.
7. **Advanced explorer:** nested fractions, roots, absolute value, deeper bracket nesting.
8. **Braille display output** (Nemeth / UEB math).
9. **More algebra:** multiple variables, inequalities, simultaneous equations.
10. **Teacher mode:** create problem sets, see common mistake types.
11. **Progress history** (with consent): which mistakes a student makes most often.
12. **Multilingual explanations.**
13. **Personal style settings:** short vs detailed, speaking speed, formal vs friendly wording.

## 16. Changes from the original PRD

The original is `audio_first_algebra_checker_PRD.md`. Section numbers marked "orig." point to it.

### 16.1 Changed

| Area                         | Original PRD                                                                                                                             | This plan                                                                                                                             | Why                                                                                                                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **How a step is understood** | Compare the two equations' trees (orig. §4.3), then match the changes against a 10-rule catalogue R01–R10 (orig. §4.4)                   | 5 algebraic checks with SymPy (§7.3): same difference on both sides, same ratio, sides swapped, rewrite, generic multiple             | Tree comparison breaks on term order (`3x+5` vs `5+3x`) and on notation (`2x` vs `2*x`). Algebra doesn't care about either. About 80–150 lines instead of a comparator plus 10 rules |
| **Rule mapping**             | R01–R10                                                                                                                                  | R01/R02 → difference check; R03/R04/R10 → ratio check; R09 → swap; R05–R08 → rewrite sub-types                                        | Same coverage, fewer moving parts                                                                                                                                                    |
| **Error categories**         | Listed (orig. §4.6), with no method for detecting them                                                                                   | 9 fixed checks, each with an exact rule for detecting it (§7.4)                                                                       | "Only assign a category when there is evidence" now has a concrete test: a check fires only if redoing that mistake reproduces the student's line exactly                            |
| **Definition of "valid"**    | Not defined                                                                                                                              | Same real solution set, and no dividing or multiplying by something that can be zero (§5)                                             | Without a definition, members would implement different meanings                                                                                                                     |
| **When SymPy can't solve**   | "Return uncertainty"                                                                                                                     | Test about 20 random values of x first; return "unable to determine" only if that is inconclusive                                     | Fewer "unable to determine" results, with no loss of safety                                                                                                                          |
| **Parser**                   | "SymPy or equivalent"; separate modules `input_handler`, `parser`, `ast_builder`, `normalizer` (orig. §5.1)                              | One own recursive-descent parser that builds the original tree and converts it to SymPy (§7.1)                                        | SymPy's `parse_expr` runs `eval` on the input, which is a security risk (orig. §7.5 already says the parser is not a sandbox). One parser gives both representations from orig. §5.3 |
| **Frontend**                 | React + Tailwind (orig. §5.2)                                                                                                            | One plain HTML/JS page served by FastAPI                                                                                              | Less setup and fewer moving parts. The accessibility features come from ARIA and the browser, not React                                                                              |
| **API**                      | 5 endpoints including `/api/explain-node` (orig. §10.5)                                                                                  | 4 endpoints; `/api/explain-node` removed (§7.7)                                                                                       | The explorer tree already carries the quick, detailed and context text for every node, so the page doesn't need extra calls                                                          |
| **Check-step response**      | `rule_id`, `operation`, `operand`, `explanation`, `conditions` (orig. §10.2)                                                             | `status`, `inference`, `mistake`, `explanation {concise, detailed}` (§10)                                                             | Adds the mistake result and both explanation levels                                                                                                                                  |
| **Explorer node**            | `spoken_label` only (orig. §10.4)                                                                                                        | `role`, `spoken_quick`, `spoken_detailed`, `spoken_context` (§10)                                                                     | Supports the three explanation depths from orig. §4.8 directly                                                                                                                       |
| **Explorer keys**            | `B` = explain the parent relationship (orig. §4.8)                                                                                       | `C` = context, plus new `Home` and `?` keys (§7.6)                                                                                    | "Context" says what the key does more clearly. `Home` and `?` help a lost user                                                                                                       |
| **Phases**                   | Phases 0–6: engine, explanations, explorer, frontend, testing, extensions (orig. §8)                                                     | Phases 0–4, each with a task table per member (§12)                                                                                   | Every phase now builds a working slice of the whole app, rather than leaving integration to the end. Extensions moved to §15                                                         |
| **First-week plan**          | Day-by-day table (orig. §16)                                                                                                             | Phase 0 + Phase 1 (~10 h first demo)                                                                                                  | Same goal, tied to members instead of days                                                                                                                                           |
| **Team split**               | M1 Parser & AST, M2 AST comparison & rules, M3 Verification & testing, M4 Explorer & accessibility, M5 Frontend & integration (orig. §9) | Same five areas, adapted (§11). M2 now owns inference and mistake checks; M1 also owns `speak.py`; M3 also owns explanation templates | Follows the new engine. Every member also writes their own docs, report section and slides, so no one is docs-only                                                                   |

### 16.2 Removed

| Item                                      | Why                                                                             |
| ----------------------------------------- | ------------------------------------------------------------------------------- |
| Tree comparison module (`ast_comparator`) | Replaced by algebraic inference                                                 |
| Rule IDs R01–R10 as separate code units   | Merged into 5 checks (mapping above)                                            |
| Test case `x = 0 → x/x = 1` (orig. §11.1) | It isn't a real step. Replaced by `x^2 = x → x = 1` (dividing by x loses x = 0) |
| React / Tailwind                          | Simpler stack, as above                                                         |

### 16.3 Added

- Precise definitions of valid, invalid and unable to determine (§5).
- Random-value fallback in the verifier (§7.2).
- 9 named mistake checks with exact detection rules (§7.4).
- Explanation templates for every outcome (§7.5).
- An explorer role table with spoken examples, the "multiplier of a group" role, and `Home` / `?` keys (§7.6).
- Shared data formats frozen on Day 1, with mocks (§10).
- Per-member tasks in every phase, pairing points, and docs/presentation shared by everyone (§11–12).
- A shared test catalogue, `tests/cases.csv`, with near-miss tests for every mistake check (§13).
- Future features: a trained AI mistake model and LLM rephrasing (§15.1–15.2).

### 16.4 Unchanged (still applies from the original)

- **Goals, users and non-goals** (orig. §2–3): no LLM decides correctness, and the tool is not a universal solver.
- **Two representations:** the original tree plus the SymPy form (orig. §5.3).
- **Three outcomes:** valid, invalid, unable to determine (orig. §4.6).
- **Audio requirements:**
  - natural maths language
  - repeat and stop
  - no speech while typing
  - speech kept separate from the maths engine (orig. §4.7)
- **Accessible interface requirements** (orig. §4.9).
- **Functional requirements FR-01 to FR-15** (orig. §6). FR-04 "Compare ASTs" now means "infer the operation".
- **Non-functional requirements** (orig. §7):
  - parsing under 1 s, verification under 2 s
  - no personal data stored by default
  - input validated before parsing
- **Risks and mitigations** (orig. §12) and **success criteria** (orig. §15).
- **Future features** (orig. §14): all kept in §15.
- **Core principle** (orig. §17): _Don't just make algebra audible; make its structure and reasoning understandable._
