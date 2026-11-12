# Final report: Audio-First Algebra Step Checker

Owner: everyone. Outline drafted by Member 1 (Phase 0). Each member writes their own
section as their module is finished; Members 3 and 5 merge everything in Phase 4.

> Write for a reader who hasn't seen the code. Every claim about accuracy should point
> to a test or a measurement in `docs/test_report.md`.

## 1. Introduction (everyone; Member 5 edits)
- The problem: algebra layout is lost in screen-reader speech
- Who it is for: blind and low-vision students, classes 1–5, linear equations
- What we built: step checker + expression explorer

## 2. Requirements and scope (Member 2)
- Goals and non-goals (from plan.md §1–5)
- What counts as valid, invalid and unable to determine
- Changes from the original PRD (plan.md §16)

## 3. System architecture (Member 5)
- Pipeline diagram: parser → verifier / inference / mistakes → explanation → speech
- API and data contracts (docs/contracts.md)
- Technology choices and why (FastAPI, SymPy, plain HTML/JS)

## 4. Parsing and speech (Member 1)
- Why we wrote our own parser instead of `sympy.parse_expr` (safety, keeping the student's structure, positions, clear errors)
- Grammar and how it builds precedence into the tree
- Signs, powers and the ambiguous cases (`1/2x`, `2^3x`)
- Input limits for classes 1–5, rounding to 4 decimal places, division by zero as undefined
- Spoken error messages
- Maths-to-speech rules (minus vs negative, brackets, "end power")
- Testing: unit tests, contract test, random testing (crashes, hangs)

## 5. Verification and testing (Member 3)
- Solution-set comparison, random-value fallback, zero divisors
- Solution-based mistake checks
- Explanation templates
- Test catalogue (`tests/cases.csv`) and results

## 6. Inference and mistake detection (Member 2)
- The five inference checks and how they replace rules R01–R10
- Operation-based mistake checks, with examples

## 7. Expression explorer and accessibility (Member 4)
- Node roles and the three explanation depths
- Keyboard map and screen-reader behaviour (NVDA, Orca)
- Accessibility testing and findings

## 8. User interface and integration (Member 5)
- The page, the live region and speech controls
- End-to-end workflow and focus management

## 9. Evaluation (Members 3 and 4)
- Mathematical metrics: false-valid (must be 0), false-invalid, share of "unable to determine", mistake-label accuracy
- Accessibility metrics: task completion, time, key presses, clarity ratings

## 10. Limitations and future work (everyone; Member 3 edits)
- Known limitations (docs/limitations.md)
- Future features (plan.md §15)

## 11. Team contributions (everyone)
- One paragraph per member

## Appendix
- Supported syntax (docs/syntax.md)
- Keyboard guide (docs/keyboard_guide.md)
- API reference (docs/api.md)
