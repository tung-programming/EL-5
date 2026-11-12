# Member 1 files: what each one does

Owner: Member 1 (Parser & AST). Status: **Phases 0, 1 and 2 done.** Phase 3 (spoken read-back) and Phase 4 (report section, slides) are still to do.

Run from the project root (`EL-5/`) with the environment active (`source my_env/bin/activate`):
```bash
python -m pytest tests/test_parser.py tests/test_speak.py   # 387 tests
python -m engine.parser "3x + 5 = 14"                       # try any equation
python -m engine.examples                                   # rebuild docs/example_trees.json
```

## Files at a glance
| File | Phase | What it does |
|---|---|---|
| `engine/parser.py` | 1–2 | Reads the student's typed equation, checks it, and builds the equation tree. Converts the tree to SymPy |
| `engine/speak.py` | 2 | Turns any equation, or any part of one, into spoken words |
| `engine/examples.py` | 0 | Writes `docs/example_trees.json` from the real parser |
| `tests/test_parser.py` | 1–2 | 331 parser tests |
| `tests/test_speak.py` | 2 | 56 speech tests |
| `tests/test_parser_integration.py` | 2 | 14 tests: parser output → Member 2's `infer_operation` / `detect_mistake` → `cli.check` |
| `docs/syntax.md` | 0–2 | What students can type: grammar, limits, signs and powers, error kinds, how things are spoken |
| `docs/example_trees.json` | 0 | 7 real example trees (JSON + bracketed + spoken + SymPy) for Members 3 and 4 |
| `report/final_report.md` | 0 | Report outline, with an owner for every section |
| `docs/member1_files.md` | – | This file |

---

## `engine/parser.py`
**Job:** text in, checked equation tree out. It is the only place student input is read. It never uses `eval` or `sympy.parse_expr`.

### How it works
1. **`tokenize(text)`** splits the text into pieces: numbers, `x`, operators, brackets, `=`.
   - Converts Unicode symbols: `−` `×` `÷` `²` `⁻¹` …
   - Rejects anything else with a clear message.
2. **The parser** follows the grammar in `docs/syntax.md`, one function per level: `equation → expr → term → unary → power → primary`. Because each level calls the next tighter one, precedence comes out right automatically:
   - `-x^2` = `-(x^2)`
   - `2^3^2` = `2^9`
   - `8-3-2` = `3`
3. While parsing, it **checks the limits for classes 1–5**:
   - numbers up to 1,000,000
   - more than 4 decimal places → rounded to 4 (5 rounds up)
   - powers are whole numbers from −10 to 10, with no x in them
   - powers can't blow up (`10^7`, `(x^2)^6` are rejected)
4. Any problem raises **`ParseError`**, with a sentence that can be read aloud.

### What other members use
| Function | Returns | Used by |
|---|---|---|
| `parse(text)` | `Node` of type `Equation`, or raises `ParseError` | everyone |
| `to_sympy(tree, evaluate=True)` | `(left, right)` as normal SymPy. **Use this for solving.** Dividing by zero gives `sympy.nan` (undefined) | Members 2, 3 |
| `to_sympy(tree)` | `(left, right)` unevaluated: `2 + 3` stays `2 + 3` | when you need the student's form |
| `tree.to_sympy()` | the same as `to_sympy(tree, evaluate=True)`. **Evaluated by default**, because `cli.py`, infer and mistakes call it to get SymPy ready for solving | `cli.py`, Member 2 |
| `X` | the shared SymPy symbol `x`. **Always use this one**, not your own `Symbol("x")` | Members 2, 3 |
| `node.to_dict()` | the tree as JSON, exactly as in `docs/contracts.md` | Member 5 (API) |
| `walk(tree)` | every node, parent first | Member 4 |
| `source_text(node, text)` | the piece of the original input a node came from, e.g. `"(x + 3)"` | Members 4, 5 |
| `notes(tree, text)` | sentences to tell the student even though input was accepted: rounding, division by zero | Member 5 |
| `undefined_parts(tree)` | the parts that divide by zero | Members 3, 5 |
| `ParseError` | `.kind`, `.position`, `.message`, `.to_dict()` | Member 5 |
| `bracketed(tree)` | fully bracketed text, e.g. `((3 · x) + 5) = 14`, for tests and debugging | tests |

### The tree (`Node`)
| Field | Meaning |
|---|---|
| `type` | `Equation`, `Number`, `Variable`, `Add`, `Sub`, `Mul`, `Div`, `Pow`, `Neg`, `Group` |
| `children` | in source order: `[left, right]`, `[inner]` for `Neg`/`Group`, or `[]` |
| `value` | digits for a `Number` (rounded if needed), `"x"` for `Variable`, otherwise `None` |
| `span` | `(start, end)` positions in the original text |
| `implicit` | `True` only for a `Mul` written like `3x` / `2(x+1)`; `False` for `3*x` and every other node |
| `typed` | `Number` only: what the student typed if the number was rounded, e.g. `"3.14159"`; otherwise `None` |

The student's own brackets are kept as `Group` nodes, so the explorer can say "brackets grouping x plus 3".

### Decisions you should know about
- **Division by zero is undefined, not an error.** `x/0 = 1` is accepted:
  - SymPy (evaluated) gives `nan` for that side.
  - `notes()` says "x/0 divides by zero, which is undefined."
  - This also covers `x/(2-2)` and `0^-1`.
  - `x/(x-1)` is **not** flagged: it's only zero at x = 1, which is a verifier (Member 3) question.
- **Ambiguous input is refused, never guessed.**
  - `1/2x` → "type 1/(2x) or (1/2)x"
  - `2^3x` → "type 2^(3x) or (2^3)x"
- **Two signs in a row are refused** (`--3`). A double negative must be written `-(-3)`.
- **Why `evaluate=True` exists:** random testing found that SymPy's own `simplify()` can crash on unevaluated expressions. The evaluated form had no crashes in 40,000 generated equations.
- **Speed:** worst-case inputs parse in about 10 ms. In 4.2 million random inputs there were no crashes and no hangs.

### Contract notes (`docs/contracts.md`, owned by Member 2)
- **Contract version 1.1** adds `implicit` and `typed` to every OwnAST node, and documents that `Number.value` is rounded to 4 decimal places. **Member 2 should review this change**, since the contract is theirs.
- The parser's JSON matches the contract exactly. A test reads both examples straight from `docs/contracts.md` and compares them with real parser output, so the two can't drift apart.
- **`Variable.value`** is always `"x"`, even when `X` was typed.

---

## `engine/speak.py`
**Job:** tree in, words out. It works on a whole equation or on any part of one, which the explorer needs.

| Function | Example |
|---|---|
| `say(text)` | `say("3x + 5 = 14")` → "three x plus five equals fourteen" |
| `to_words(node)` | `to_words(left_side)` → "three x plus five" |
| `number_to_words(digits)` | `"115"` → "one hundred fifteen", `"2.5"` → "two point five" |

**Rules**, chosen so speech is never more ambiguous than what was typed:
- **"minus" is subtraction; "negative" is a negative number:** `2 - -3` → "two minus negative three".
- **Brackets are read out:** "open bracket … close bracket".
- **A coefficient joins its variable:** "three x", "negative three x squared". Other multiplication says "times".
- **`-x^2` and `(-x)^2` sound different:**
  - `-x^2` → "negative of x squared"
  - `(-x)^2` → "open bracket negative x close bracket squared"
- **Powers:** "squared", "cubed", otherwise "to the power of …".
- **"end power"** marks where a complicated exponent stops: `2^3^2` → "two to the power of three squared, end power".
- **No "and" inside numbers** ("one hundred fifteen"), so it can't be confused with "plus".

---

## `engine/examples.py` and `docs/example_trees.json`
Phase 0 hand-off. Instead of hand-written trees (which could be wrong), `python -m engine.examples` writes 7 real examples, such as `3x + 5 = 14` and `2(x + 3) = 10`. Each one includes:
- the JSON tree
- the bracketed form
- the spoken form
- the SymPy form

A test fails if the file goes out of date.

---

## Tests
| File | Count | What it covers |
|---|---|---|
| `tests/test_parser.py` | 331 | 56 valid inputs with exact trees; 29 invalid inputs with error kinds; one input per error kind; exact messages and positions; contract JSON; spans; SymPy (both modes); Unicode; number limits and rounding; power limits; division by zero; example file up to date |
| `tests/test_parser_integration.py` | 14 | Parser output works with Member 2's inference (add, subtract, multiply, divide, swap), mistakes (arithmetic, one side only), division by zero, and `cli.check()` end to end with a stand-in verifier |
| `tests/test_speak.py` | 56 | Spoken forms of equations, minus vs negative, coefficients, powers, brackets; number words up to a million; subtrees |

Beyond the test files, the code was also checked with random testing:
- 4.2 million random inputs: no crashes, no hangs
- 40,000 generated valid equations: the SymPy output was checked against the expected maths

---

## Hand-offs
| To | What |
|---|---|
| **Member 2** | Use `to_sympy(tree, evaluate=True)` and `X`. Please review contract version 1.1 (`implicit`, `typed`, rounding) |
| **Member 3** | Use `to_sympy(tree, evaluate=True)`. A side that is `sympy.nan` is undefined (division by zero). `undefined_parts()` says where. Non-literal zero divisors like `x/(x-1)` are yours to check |
| **Member 4** | Build the explorer on `walk()`, `source_text()` and `to_words()`. `Group` nodes are the student's brackets. `implicit` tells `3x` from `3*x`. Examples are in `docs/example_trees.json` |
| **Member 5** | On error, show and speak `ParseError.message`, and use `.position` to place the cursor. After a successful parse, also speak `notes(tree, text)`. `node.to_dict()` and `err.to_dict()` are ready for the API |

## Still to do (Member 1)
- **Phase 3:** spoken read-back before checking, e.g. "I read this as three x plus five equals fourteen". `say()` already does the hard part; it needs wiring into the page with Member 5.
- **Phase 4:** final `docs/syntax.md`, report section 4 (outline in `report/final_report.md`), 2–3 slides.
