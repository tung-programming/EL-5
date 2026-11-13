# Shared data contracts

Owner: Member 2

Contract version: 1.2 (Phase 2; 13 November 2026)

Changes:
- 1.2: MistakeResult gains `operation`, `operand` and `before` (null when not known), and all ten labels are active. InferenceResult gains the `combined` operation and, for `rewrite`, a `kind`. Operands may be x-expressions (`"3*x + 2"`). All additions; no existing field changed meaning.
- 1.1: OwnAST nodes gain `implicit` and `typed`. Number `value` is rounded to 4 decimal places. Scope is classes 1–5, linear equations.

These JSON contracts are shared by the Python backend, CLI, API, and frontend. Keep serialized mathematical values as strings; never put SymPy/Python objects in JSON. A change to a frozen field, meaning, or allowed value requires agreement from the team.

## OwnAST node

Each node has required `type`, `value`, `children`, `span`, `implicit`, and `typed`. `value` is `null` when the node has no payload. `children` are ordered in the same order as the source expression. `span` is a half-open `[start, end]` range of zero-based character offsets in the original input (end is exclusive). An `Equation` has exactly two children, left side then right side. `Group` has one child and preserves explicit parentheses.

Allowed types are `Number`, `Variable`, `Add`, `Sub`, `Mul`, `Div`, `Pow`, `Neg`, `Group`, and `Equation`. Binary operators have two children, `Neg` and `Group` one, and leaves none.

| Field | Meaning |
|---|---|
| `value` | `Number`: the digits as typed (`"3"`, `"2.5"`, `".5"`). If the student typed more than 4 decimal places, the value is rounded to 4 (5 rounds up), e.g. `"3.1416"`. `Variable`: always `"x"`, even if `X` was typed. Every other type: `null` |
| `implicit` | `true` only for a `Mul` written without a sign (`3x`, `2(x+1)`); `false` for `3*x` and for every other node. Lets the explorer and speech say "three x" instead of "three times x" |
| `typed` | `Number` only: the original text when `value` was rounded (`"3.14159"`); otherwise `null`. Lets the app say "I rounded 3.14159 to 3.1416" |

Example: `3x + 5 = 14`

```json
{"type":"Equation","value":null,"children":[{"type":"Add","value":null,"children":[{"type":"Mul","value":null,"children":[{"type":"Number","value":"3","children":[],"span":[0,1],"implicit":false,"typed":null},{"type":"Variable","value":"x","children":[],"span":[1,2],"implicit":false,"typed":null}],"span":[0,2],"implicit":true,"typed":null},{"type":"Number","value":"5","children":[],"span":[5,6],"implicit":false,"typed":null}],"span":[0,6],"implicit":false,"typed":null},{"type":"Number","value":"14","children":[],"span":[9,11],"implicit":false,"typed":null}],"span":[0,11],"implicit":false,"typed":null}
```

Example with rounding: `x = 3.14159`

```json
{"type":"Equation","value":null,"children":[{"type":"Variable","value":"x","children":[],"span":[0,1],"implicit":false,"typed":null},{"type":"Number","value":"3.1416","children":[],"span":[4,11],"implicit":false,"typed":"3.14159"}],"span":[0,11],"implicit":false,"typed":null}
```

Additional equation examples (shown as source → tree shape):

- `2(x + 3) = 10` → `Equation(Mul(Number("2"), Group(Add(Variable("x"), Number("3")))), Number("10"))`.
- `x^2 - 4 = 0` → `Equation(Sub(Pow(Variable("x"), Number("2")), Number("4")), Number("0"))`.

## InferenceResult

All fields are required. `operation` is a string operation identifier (`add`, `subtract`, `multiply`, `divide`, `swap_sides`, `rewrite`, `combined`, or `unknown`). `combined` means several steps were applied to both sides at once (`x + 2 = 5 → 2x = 6`). `operand` is a stringified constant/expression (`"5"`, `"3*x + 2"`), or null when no operand applies or no operation can be inferred. `applied_to` is `both_sides`, `left_side_only`, `right_side_only`, or `unknown`; for `rewrite` it names the side(s) that were rewritten. A `rewrite` also has `kind`: `expand`, `factor`, `collect_like_terms`, `reorder`, or `simplify`. Rewrites are only detected when the engine is given the parser's trees, because SymPy has already lost the student's brackets. `expected` and `got` are serialized mathematical values or null when unavailable. `warnings` is an array of strings. No inference is represented by `null` from the inference function; if a response requires an inference object, use `operation:"unknown"`, null operand/expected/got, `applied_to:"unknown"`, and a warning explaining why.

```json
{"operation":"subtract","operand":"5","applied_to":"both_sides","expected":null,"got":null,"warnings":[]}
```

```json
{"operation":"rewrite","operand":null,"applied_to":"left_side_only","expected":null,"got":null,"warnings":[],"kind":"expand"}
```

## MistakeResult

All fields are required when a result exists. Labels: `one_side_only`, `sign_error`, `wrong_inverse_op`, `arithmetic_error`, `partial_distribution`, `coefficient_error`, `exponent_error`, `divide_by_variable`, `lost_solution`, `extra_solution` (detection rules: plan.md §7.4). `expected` and `got` are serialized values (strings), or null if unavailable; for `divide_by_variable`, `lost_solution` and `extra_solution` they are the previous and current solution sets (`"{0, 1}"`, `"{1}"`, `"EmptySet"`). `location` identifies the side containing the discrepant value: `left_side`, `right_side`, or `unknown` (always `unknown` for the solution-set labels). A null result means no supported mistake was proven.

`operation`, `operand` and `before` describe the step that was done correctly on the other side, so the explanation can show the calculation ("14 minus 5 is 9, not 10"). `operation` is `add`, `subtract`, `multiply` or `divide`; `operand` is the number (or, for `divide_by_variable`, the expression with x); `before` is the value of the `location` side before the step. Each is null when it does not apply (the structural and solution-set labels).

```json
{"label":"arithmetic_error","expected":"9","got":"10","location":"right_side","operation":"subtract","operand":"5","before":"14"}
```

## CheckStepResponse

All fields are required. `status` is `valid`, `invalid`, or `unknown`. `inference` is an InferenceResult object or null. `mistake` is a MistakeResult object or null. `explanation` contains required `concise` and `detailed` strings. The verifier owns the valid/invalid/unknown decision; inference describes the likely operation and does not decide validity. Mistake detection runs only for an `invalid` verdict and supplies evidence to the explanation engine. The explanation engine turns these verified structures into text and does not redo verification.

```json
{"status":"valid","inference":{"operation":"subtract","operand":"5","applied_to":"both_sides","expected":null,"got":null,"warnings":[]},"mistake":null,"explanation":{"concise":"Correct: you subtracted 5 from both sides.","detailed":"Subtracting 5 from each side keeps the equation equivalent."}}
```

## ExplorerNode

All fields are required. `id` is a stable unique string within the tree; `type` is an OwnAST type; `role` names the node's mathematical role (for example `coefficient`, `variable`, `operator`, or `constant`); `value` is a display string or null; the three `spoken_*` fields contain quick, detailed, and contextual speech; `children` is an ordered array of ExplorerNode objects.

```json
{"id":"term-left-1","type":"Mul","role":"term","value":null,"spoken_quick":"3 x","spoken_detailed":"3x means 3 multiplied by x.","spoken_context":"This term is on the left side and is added to 5.","children":[{"id":"coefficient","type":"Number","role":"coefficient","value":"3","spoken_quick":"3 is the coefficient of x.","spoken_detailed":"3x means 3 multiplied by x.","spoken_context":"3 multiplies x in the first term on the left.","children":[]},{"id":"variable","type":"Variable","role":"variable","value":"x","spoken_quick":"x is the variable.","spoken_detailed":"x is the unknown value.","spoken_context":"x is multiplied by 3.","children":[]}]}
```
