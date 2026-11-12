# Explorer contract: how the explorer reads the shared contract

Owner: Member 4
Audience: Member 1 (parser), Member 2 (shared contracts), Member 5 (API and page)

## 0. Authority and status

- **`docs/contracts.md` (Member 2, contract version 1.1) is the authoritative shared contract** for the OwnAST (input) and the ExplorerNode (output). Where this document and `docs/contracts.md` disagree, `docs/contracts.md` wins and this document has a bug.
- This document records only (a) how `engine/explore.py` interprets the shared contract and (b) what Member 4 adds on top of it. Every statement is labelled:
  - **CONTRACT**: stated in `docs/contracts.md`.
  - **M4**: a Member 4 choice or extension the contract does not state. Member 1 or 2 may overrule it.
  - **UNCONFIRMED**: an assumption about the real parser that Member 1 must confirm.
- `engine/parser.py` is now Member 1's real parser (merged into `main` at `6db652e`). Its output was run through the explorer in `tests/test_parser_integration_explorer.py` (`parse(text).to_dict()` → `build_explorer_tree(...)`), and every fixture in `tests/explorer_fixtures.py` is compared with the parser's output for the same source. That checks the shape conventions below for the syntax the parser accepts; it does not replace Member 1's own tests, and nothing has been tested in a browser or screen reader.
- No browser, NVDA or Orca testing has been done.
- This document follows `docs/contracts.md` **v1.1** (the authoritative shared contract) and `engine/parser.py` as merged in `main`. The parser's extra node fields `implicit` and `typed` are accepted and ignored by the explorer: `3x` and `3*x` are explored identically, and a rounded decimal (`3.14159` → `"3.1416"`) is spoken as the stored value.

### 0.1 What was changed to comply (compared with the earlier explorer)

| Area | Before | Now (contract) |
|---|---|---|
| `Number.value` | `int` / `float` | **string**, the source spelling (`"3"`, `"14"`) |
| Output `value` | raw number | **display string or `null`** |
| Output `span` | present | **removed** (still required and validated on input) |
| `Fraction` node type | accepted (provisional) | **rejected**; `Div` is the one division/fraction node |
| `Div` | inline division, role `operator` | gets the fraction roles (`fraction`, `numerator`, `denominator`) |
| Constant role | `constant_term` | **`constant`** (the name in the contract); spoken text still says "constant term" |
| Negative `Number` | `Number(-3)` accepted | rejected: a minus is a `Neg` node |

## A. Input AST (OwnAST)

`build_explorer_tree(ast)` takes one argument, the root node.

### A.1 Shared requirements (CONTRACT)

Each node has required `type`, `children` and `span`. `value` is optional and is `null` when the node has no payload. `children` are in source order. `span` is a half-open `[start, end]` range of zero-based character offsets in the original input (end exclusive). Allowed types are `Number, Variable, Add, Sub, Mul, Div, Pow, Neg, Group, Equation`. `Number` and `Variable` carry their source spelling in `value`; operator and grouping nodes use `null`. An `Equation` has exactly two children (left, then right). `Group` has one child and preserves explicit parentheses. Binary operators have two children, `Neg` and `Group` one, leaves none.

### A.2 How the explorer enforces them

| Rule | Behaviour (verified by running the code) |
|---|---|
| Representation | A plain `dict`. Anything else (a dataclass, an object, `None`, a list) raises `node must be a dict, got <type>`. |
| Required keys | `type` (a `str`), `children` (a `list`; a tuple is rejected) and `span`. A missing key raises `node is missing '<key>'`. Leaves carry `children: []`. |
| Type names | Exact and case-sensitive: `Equation, Number, Variable, Add, Sub, Mul, Div, Pow, Neg, Group`. Anything else (including `Fraction`) raises `unsupported node type '<name>'`. |
| Child count | Exact: `Equation` 2, `Add`/`Sub`/`Mul`/`Div`/`Pow` 2, `Neg` 1, `Group` 1, `Number`/`Variable` 0. Wrong count raises `<Type> needs N child(ren), found M`. |
| `Number.value` | Required, a **string**, ASCII digits with an optional decimal point (section A.3). Otherwise `ExplorerError`. |
| `Variable.value` | Required, a non-empty `str`. Any name is accepted (`"y"` works); the plan only has `x`. |
| `value` elsewhere | Absent or `null` accepted; any other value raises `<Type> must not have a 'value'`. |
| Root | Must be an `Equation` (`the root must be an Equation, got <type>`); an `Equation` anywhere else raises `an Equation can only be the root`. |
| Depth | At most **100 levels, counting the Equation as level 1**. The 101st raises `the tree is more than 100 levels deep`; a cyclic AST hits this limit and raises `ExplorerError`, not `RecursionError`. `MAX_DEPTH` is 100 in both `engine/explore.py` and `static/explorer_keys.js`; a test keeps them equal. |
| Extra keys | Ignored, and not copied to the output. |

### A.3 Number spelling (M4 validation of a CONTRACT string)

The contract says `Number.value` is the source spelling but not which spellings are legal. The explorer accepts exactly this pattern (`re.fullmatch`): `[0-9]+(\.[0-9]*)?` or `\.[0-9]+`, which is what the plan's tokenizer allows ("digits, decimals").

| Accepted | Rejected (`Number 'value' '<text>' is not a plain decimal number`) |
|---|---|
| `3`, `14`, `0`, `007`, `2.5`, `2.50`, `4.0`, `.5`, `5.` | `""`, `" 3"`, `"3 "`, `"-3"`, `"+3"`, `"1e3"`, `"0x10"`, `"1,000"`, `"1_000"`, `"1.2.3"`, `"."`, `"nan"`, `"inf"`, `"3x"`, non-ASCII digits, a trailing newline |
| any length (a 5000-digit string works) | a non-string (`int`, `float`, `bool`, `None`, `Decimal`) raises `Number needs its source spelling as a string 'value', such as '3'` |

- **The spelling is preserved exactly** in the output `value` and in speech: `"2.50"` stays `2.50`, `"007"` stays `007`. Nothing is normalised or rounded, so a long spelling is never converted to a Python float or int.
- **A Number is never negative.** The tokenizer has no negative literal, so `-3` arrives as `Neg(Number "3")`. A signed spelling is rejected rather than interpreted.
- Where a number must be compared (is an exponent 2, 3, or another whole number?) the explorer uses exact `Decimal`, so `"2"`, `"2.0"` and `"02"` all count as 2.
- `5.` (a trailing point) is accepted by the explorer's number check, but the real parser rejects it (`bad_number`), so it never arrives. The parser stores decimals rounded to 4 places (`3.14159` → `"3.1416"`).

### A.4 Source spans

- **Shape (M4 validation):** two `int`s (bool excluded, `list` or `tuple`) with `0 <= start < end`. An empty span is invalid. Floats, wrong length, negatives and `start >= end` raise `'span' must be [start, end] with 0 <= start < end`.
- **Convention (CONTRACT):** half-open, zero-based, end exclusive. For `3x + 5 = 14` the Number `14` is `[9, 11]`. The explorer cannot verify the convention (it checks only `start < end`).
- **Not checked:** that a child lies inside its parent, that siblings do not overlap, that spans are in order, or that they match the source text.
- **The span is validated and then dropped.** It is not part of the ExplorerNode. No consumer of the explorer output has any span.
- **Confirmed on `engine/parser.py`:** the offsets are into the string exactly as the parser received it, with leading spaces counted, `**` left as two characters (`x ** 2`: Pow `[0, 6)`) and a superscript such as `x²` giving the exponent Number the span of the `²` character. The explorer drops the span, so none of this reaches the output.

### A.5 Structural conventions not stated in the contract (checked against `engine/parser.py` by the integration tests)

| Topic | What the explorer assumes |
|---|---|
| Group span | Includes the brackets; its child's span does not (`2(x + 3)`: Group `[1, 8]`, child `[2, 7]`; the parser's `2(x + 3) = 12` gives Group `[1, 8)`, Add `[2, 7)`). Confirmed on the parser's output. |
| Brackets | Every pair the student typed is a `Group`, including redundant ones. **A bracketed numerator or denominator of a `Div` is kept by the parser as a `Group` inside the `Div`** (`(x + 1)/2` is `Div(Group(Add), 2)`), so that child has the role `group`, its own child is the `Add`, and the spoken text says "the group …". The explorer never adds or removes a Group. |
| Child order | `Sub` `[minuend, subtrahend]`, `Pow` `[base, exponent]`, `Div` `[numerator, denominator]`. Never re-sorted. A reversed order is **not detectable** and gives silently wrong text. |
| Binary operators | `1 + 2 + 3` arrives as nested pairs (left- or right-nested; the explorer does not care). |
| Implicit multiplication | `3x` → `Mul(Number, Variable)`, `2(x+3)` → `Mul(Number, Group)`, `3x^2` → `Mul(3, Pow(x, 2))`, the same node as explicit `*`. |
| Precedence | `^` binds tighter than implicit multiplication; unary minus binds looser than `^` (`-x^2` is `Neg(Pow)`). |
| Negative coefficient | The parser builds `-3x` as `Mul(Neg(3), x)` (implicit), not `Neg(Mul(3, x))`. See A.6. |
| Division | `Div` is both inline division and a stacked fraction (A.7). |

### A.6 Negation

| Source | Tree | Result |
|---|---|---|
| `-3x` | `Mul(Neg(3), x)` (what the parser builds) | the **`Neg` node is the `coefficient`** (`spoken_quick` "Coefficient negative 3"); the `3` inside it is a `number` that is described as "the number part of the coefficient negative 3" |
| `-2(x + 3)` | `Mul(Neg(2), Group)` | the `Neg` node is the `group_multiplier` ("Multiplier negative 2") |
| `-3x^2` | `Mul(Neg(3), Pow(x, 2))` | the `Neg` node is the `coefficient` of the powered variable |
| `-3x` | `Neg(Mul(3, x))` (not produced by the parser) | still accepted: the 3 stays a `coefficient` |
| `x + -3`, `x - -3` | `Add/Sub(x, Neg(3))` | the 3 is a `constant`; the sum is spoken "x plus negative 3" |
| `2 * -3` | `Mul(2, Neg(3))` | neither is a coefficient (no variable or group beside them): the 2 is `number`, the `Neg` is `operator` |
| `-x^2` | `Neg(Pow(x, 2))` | the Pow is `power` under a `Neg` |
| `-(x + 1)` | `Neg(Group(...))` | negation of the group |

### A.7 Division and fractions

The contract has no `Fraction` type, so **`Div` is used for both** inline division (`x/2`) and a stacked fraction. The explorer gives every `Div` the fraction reading: role `fraction` (or `left_side`/`right_side` at the top of a side), children `numerator`/`denominator` when they are bare Numbers, and wording "the fraction with numerator … and denominator …". `x/2` is therefore read as "the fraction with numerator x and denominator 2". This follows plan §7.6, which lists the Fraction role as `a / b`. **M4 choice:** the earlier "Division" operator wording no longer exists.

## B. Output ExplorerNode

The ExplorerNode of `docs/contracts.md`: **"All fields are required."** `build_explorer_tree` returns one `dict` (the root) with exactly these keys, in this order, and nothing else:

| Field | Type | Required | Purpose | Example |
|---|---|---|---|---|
| `id` | `str` | yes | Stable, unique inside the tree (CONTRACT). Convention (M4): the path from the root, `n0`, then `.<child index>` per level | `"n0.0.1"` |
| `type` | `str` | yes | The OwnAST `type`, unchanged (CONTRACT) | `"Mul"` |
| `role` | `str`, never empty | yes | Mathematical role (CONTRACT gives examples only; vocabulary in section C) | `"coefficient"` |
| `value` | `str` or `null` | yes (key always present) | Display string (CONTRACT): a Number's source spelling, a Variable's name, `null` for everything else | `"3"`, `"x"`, `null` |
| `spoken_quick` | non-empty `str` | yes | Short name of the part; it is the accessible name of the tree item | `"Coefficient 3"` |
| `spoken_detailed` | non-empty `str` | yes | What the part means | see D |
| `spoken_context` | non-empty `str` | yes | How the part connects to its neighbours | see D |
| `children` | `list` of ExplorerNode | yes (`[]` for leaves) | Same count and order as the input `children` (CONTRACT: ordered array) | `[ ... ]` |

A leaf (real output for `3x + 5 = 14`):

```json
{
  "id": "n0.0.0.0",
  "type": "Number",
  "role": "coefficient",
  "value": "3",
  "spoken_quick": "Coefficient 3",
  "spoken_detailed": "3 is the coefficient of x. It tells you x is multiplied by 3, so the term means 3 times x.",
  "spoken_context": "The coefficient 3 belongs to the variable x: x is multiplied by 3. Together they form the term 3x.",
  "children": []
}
```

- **No `span`.** The earlier output had one; the contract does not, so it was removed.
- The tree has the same shape as the input: one ExplorerNode per AST node. **Operators are not separate nodes.**
- IDs depend on position only, never on type or value. The contract's example ids (`term-left-1`) are illustrative; the explorer does not use them.
- The result is JSON-serialisable (checked with `json.dumps`).
- **A side-root hides its own role.** The top node of each side is `left_side`/`right_side` even when it is a bare Number or Variable. Use `type` and `value` to see what it is (`n0.1` in `3x + 5 = 14`: role `right_side`, type `Number`, value `"14"`).
- Do not find a base, numerator or denominator by `role`; use child index 0 / 1 of the `Pow`/`Div`. A Variable, Group or operator in those positions keeps its own role.

### B.1 Places where the explorer differs from the contract's example (flagged, not resolved)

The contract's ExplorerNode example is illustrative, and nothing in the text requires these, but Member 2 should know:

- The example gives the product `3x` the role `term` and speaks it as `"3 x"`; the explorer gives it the role `operator` and `"Multiplication"`. The contract lists `operator` as a role name, so `operator` is within its examples; `term` is not produced.
- The example's `spoken_quick` for the coefficient is a sentence ("3 is the coefficient of x."); the explorer's is `"Coefficient 3"`, with the sentence in `spoken_detailed`.

## C. Role vocabulary

**CONTRACT:** `role` "names the node's mathematical role (for example `coefficient`, `variable`, `operator`, or `constant`)". The contract does not fix the set. **M4:** the explorer produces exactly 16 roles; the four in the contract's list are among them, and the other twelve are Member 4's extension.

| Role | In contract's examples | Meaning and when assigned | Example | Why it helps |
|---|---|---|---|---|
| `equation` | no | The root `Equation` | `3x + 5 = 14` | A fixed starting point (Home, R) |
| `left_side` | no | First child of the Equation, whatever its type; overrides every role below | `3x + 5` | Says which side before any detail |
| `right_side` | no | Second child of the Equation, whatever its type | `14` | Same |
| `coefficient` | **yes** | A Number in a `Mul` whose other factor is a `Variable` or a `Pow` with a `Variable` base | `3` in `3x`; `3` in `3x²` is the coefficient of `x²` | Separates "what multiplies x" from "what is added" |
| `variable` | **yes** | Any `Variable` not at a side root | `x` | Names the unknown, including as a power base |
| `constant` | **yes** | A Number directly under `Add`/`Sub` (or under a `Neg` that is itself in such a position) | `5` in `3x + 5` | Says the number multiplies nothing. Spoken as "constant term" |
| `operator` | **yes** | `Add`, `Sub`, `Mul`, `Neg` unless a side, or a more specific role, applies | the `Mul` of `3x` | A stop to hear what an operation combines (operators have no node of their own) |
| `group` | no | A `Group` not at a side root | `(x + 3)` | "Everything inside is one quantity" |
| `group_multiplier` | no | A Number in a `Mul` whose other factor is a `Group` (and not a variable) | `2` in `2(x + 3)` | Stops `2` being heard as a coefficient |
| `power` | no | A `Pow` not at a side root | `x²` in `3x² + 4` | Reads base and exponent together |
| `base` | no | A Number at index 0 of a `Pow` | `2` in `2³` | Orientation inside a power |
| `exponent` | no | A Number at index 1 of a `Pow` | `2` in `x²` | Not heard as a coefficient or constant |
| `fraction` | no | A `Div` not at a side root | `(x + 1)/2` | Reads numerator over denominator as one object |
| `numerator` | no | A Number at index 0 of a `Div` | `4` in `4/x` | Orientation inside a fraction |
| `denominator` | no | A Number at index 1 of a `Div` | `2` in `(x + 1)/2` | Same; the text notes it cannot be zero |
| `number` | no | Fallback: a Number with none of the above | `2`,`3` in `2*3`; `5` in `x + (5)`; `2` in `2(x+3)^2` | Honest wording instead of mislabelling it |

Order of decision (first match wins): Equation → side root → Variable → Group → Div → Pow → other operators → for a Number: Pow parent (`base`/`exponent`), Div parent (`numerator`/`denominator`), Mul parent (`coefficient` if the other factor is a Variable or powered Variable, else `group_multiplier` if it is a Group; a `Neg` whose only child is a Number gets the same role, so `-3x` has a negative coefficient), term position (`constant`), else `number`.

The constant role was renamed from `constant_term` to `constant` to match the contract's name. **Decision for Member 2 (section H, D3):** if the team prefers the plan's "constant term", it is a one-line change, but the contract's name should then be updated too.

Conditional behaviour: the coefficient rule needs a bare Variable or a bare powered Variable (`2 * 3x^2`, `3(x+1)^2`, `3*2^2` give `number`). `Neg(Number)` under a sum gives `constant`; `Neg(Number)` beside a variable, powered variable or group in a `Mul` takes the `coefficient` / `group_multiplier` role itself. A Number under a `Group` that is not a term gives `number`.

## D. Examples (real output)

Run with the real `build_explorer_tree`. Provenance: `3x + 5 = 14`, `2(x + 3) = 12`, `(x + 1)/2 = 3` and the nested example are fixtures in `tests/explorer_fixtures.py`; `3x² + 4 = 16` and `x² = 4` are **not** fixtures and were built with the fixture helpers `_num`, `_var`, `_node` (shown below). All Number values are strings; spans are end-exclusive and are input only. Columns: id, type, role, value, `spoken_quick`.

### D.1 `3x + 5 = 14` — AST

```python
{"type": "Equation", "span": [0, 11], "children": [
  {"type": "Add", "span": [0, 6], "children": [
    {"type": "Mul", "span": [0, 2], "children": [
      {"type": "Number",   "value": "3", "span": [0, 1], "children": []},
      {"type": "Variable", "value": "x", "span": [1, 2], "children": []}]},
    {"type": "Number", "value": "5", "span": [5, 6], "children": []}]},
  {"type": "Number", "value": "14", "span": [9, 11], "children": []}]}
```

| id | type | role | value | spoken_quick |
|---|---|---|---|---|
| `n0` | Equation | equation | null | Equation |
| `n0.0` | Add | left_side | null | Left side |
| `n0.0.0` | Mul | operator | null | Multiplication |
| `n0.0.0.0` | Number | coefficient | "3" | Coefficient 3 |
| `n0.0.0.1` | Variable | variable | "x" | Variable x |
| `n0.0.1` | Number | constant | "5" | Constant term 5 |
| `n0.1` | Number | right_side | "14" | Right side |

- `n0` detailed: "The whole equation. It says that the left side, 3x plus 5, has the same value as the right side, 14."
- `n0.0.0` detailed: "Multiplication. It combines the coefficient 3 and the variable x by multiplying them. So 3x means 3 times x."
- `n0.0.1` context: "The constant term 5 is added to the term 3x. It is part of the left side of the equation."

### D.2 `3x² + 4 = 16` (typed `3x^2 + 4 = 16`) — constructed AST

```python
_node("Equation", [
    _node("Add", [
        _node("Mul", [_num(3, 0, 1), _node("Pow", [_var(1, 2), _num(2, 3, 4)], 1, 4)], 0, 4),
        _num(4, 7, 8)], 0, 8),
    _num(16, 11, 13)], 0, 13)
```

| id | type | role | value | spoken_quick |
|---|---|---|---|---|
| `n0` | Equation | equation | null | Equation |
| `n0.0` | Add | left_side | null | Left side |
| `n0.0.0` | Mul | operator | null | Multiplication |
| `n0.0.0.0` | Number | **coefficient** | "3" | Coefficient 3 |
| `n0.0.0.1` | Pow | power | null | Power |
| `n0.0.0.1.0` | Variable | variable | "x" | Variable x |
| `n0.0.0.1.1` | Number | exponent | "2" | Exponent 2 |
| `n0.0.1` | Number | constant | "4" | Constant term 4 |
| `n0.1` | Number | right_side | "16" | Right side |

The 3 is the coefficient **of x²**; the exponent belongs to `x` alone:

- `n0.0.0.0` detailed: "3 is the coefficient of x to the power of 2. It tells you x to the power of 2 is multiplied by 3, so the term means 3 times x to the power of 2. The exponent belongs to x alone, not to 3."
- `n0.0.0.1` detailed: "Power. The base is x and the exponent is 2. x squared means x is multiplied by itself: x times x."

Wording note: whole-expression phrases currently say "x to the power of 2"; "x squared" appears in the Power node's own explanation. That is temporary wording until `speak.py` lands (plan §7.5).

### D.3 `2(x + 3) = 12`

AST: `Equation[Mul[Number "2", Group[Add[Variable "x", Number "3"]]], Number "12"]`, with Group span `[1, 8]` (brackets included) and the Add inside `[2, 7]`.

| id | type | role | value | spoken_quick |
|---|---|---|---|---|
| `n0` | Equation | equation | null | Equation |
| `n0.0` | Mul | left_side | null | Left side |
| `n0.0.0` | Number | **group_multiplier** | "2" | Multiplier 2 |
| `n0.0.1` | Group | group | null | Group |
| `n0.0.1.0` | Add | operator | null | Addition |
| `n0.0.1.0.0` | Variable | variable | "x" | Variable x |
| `n0.0.1.0.1` | Number | constant | "3" | Constant term 3 |
| `n0.1` | Number | right_side | "12" | Right side |

- `n0.0.0` detailed: "2 is the multiplier of the group x plus 3. It multiplies the entire group x plus 3, so every part inside the brackets is multiplied by 2. It is not a coefficient, because it multiplies a group and not the variable."

### D.4 `x² = 4` (typed `x^2 = 4`) — constructed AST

```python
_node("Equation", [_node("Pow", [_var(0, 1), _num(2, 2, 3)], 0, 3), _num(4, 6, 7)], 0, 7)
```

| id | type | role | value | spoken_quick |
|---|---|---|---|---|
| `n0` | Equation | equation | null | Equation |
| `n0.0` | **Pow** | **left_side** | null | Left side |
| `n0.0.0` | Variable | variable | "x" | Variable x |
| `n0.0.1` | Number | exponent | "2" | Exponent 2 |
| `n0.1` | Number | right_side | "4" | Right side |

The Pow is the top of its side, so it is `left_side`, not `power`; its detailed text still explains the power.

### D.5 `(x + 1) / 2 = 3` (typed `(x + 1)/2 = 3`) — a `Div`

AST (from the real parser): `Equation[Div[Group[Add[Variable "x", Number "1"]], Number "2"], Number "3"]`. The Div span `[0, 9]`, the Group `[0, 7]` (brackets included) and the Add inside `[1, 6]`.

| id | type | role | value | spoken_quick |
|---|---|---|---|---|
| `n0` | Equation | equation | null | Equation |
| `n0.0` | **Div** | left_side | null | Left side |
| `n0.0.0` | **Group** | group | null | Group |
| `n0.0.0.0` | Add | operator | null | Addition |
| `n0.0.0.0.0` | Variable | variable | "x" | Variable x |
| `n0.0.0.0.1` | Number | constant | "1" | Constant term 1 |
| `n0.0.1` | Number | **denominator** | "2" | Denominator 2 |
| `n0.1` | Number | right_side | "3" | Right side |

The numerator is the typed `Group`, so it has the role `group`; find it by child index 0.

- `n0.0` detailed: "The left side of the equation, everything before the equals sign. It reads the fraction with numerator the group x plus 1 end group and denominator 2. Fraction. It has the group x plus 1 as its numerator and 2 as its denominator. The numerator is the top part and the denominator is the bottom part, so the fraction means the group x plus 1 divided by 2."
- `n0.0.1` detailed: "2 is the denominator of the fraction: the bottom part, which the numerator the group x plus 1 is divided by. A denominator cannot be zero."

### D.6 Nested: `2(x + 3)^2 - (x - 1)/4 = 5` (fixture `AST_MULTIPLIED_SQUARED_GROUP_MINUS_FRACTION`)

AST shape (from the real parser): `Equation[Sub[Mul[Number "2", Pow[Group[Add[x, "3"]], "2"]], Div[Group[Sub[x, "1"]], "4"]], Number "5"]`.

| id | type | role | value | spoken_quick |
|---|---|---|---|---|
| `n0` | Equation | equation | null | Equation |
| `n0.0` | Sub | left_side | null | Left side |
| `n0.0.0` | Mul | operator | null | Multiplication |
| `n0.0.0.0` | Number | **number** | "2" | Number 2 |
| `n0.0.0.1` | Pow | power | null | Power |
| `n0.0.0.1.0` | Group | group | null | Group |
| `n0.0.0.1.0.0` | Add | operator | null | Addition |
| `n0.0.0.1.0.0.0` | Variable | variable | "x" | Variable x |
| `n0.0.0.1.0.0.1` | Number | constant | "3" | Constant term 3 |
| `n0.0.0.1.1` | Number | exponent | "2" | Exponent 2 |
| `n0.0.1` | **Div** | fraction | null | Fraction |
| `n0.0.1.0` | Group | group | null | Group |
| `n0.0.1.0.0` | Sub | operator | null | Subtraction |
| `n0.0.1.0.0.0` | Variable | variable | "x" | Variable x |
| `n0.0.1.0.0.1` | Number | constant | "1" | Constant term 1 |
| `n0.0.1.1` | Number | denominator | "4" | Denominator 4 |
| `n0.1` | Number | right_side | "5" | Right side |

- The leading `2` is `number`, not `group_multiplier`: its sibling is a `Pow` of a group, not a `Group`. The parser really does build `2(x + 3)^2` as `Mul(2, Pow(Group, 2))`, so the student hears the 2 described as a plain number (it multiplies the whole power).
- `n0` detailed: "The whole equation. It says that the left side, 2 times the group x plus 3 end group to the power of 2, minus the fraction with numerator the group x minus 1 end group and denominator 4, has the same value as the right side, 5."

Reproduce: `ALL_FIXTURES[...]` from `tests/explorer_fixtures.py` through `build_explorer_tree`. `tests/js/explorer_trees.json` stores the real output for five fixtures and is checked by `tests/test_explorer_keys_fixture.py`.

## E. Parser compatibility checklist for Member 1

**Status after the integration run:** items A8, A9 to A14 and A21 below were checked against `engine/parser.py` (see the status notes in each item and `tests/test_parser_integration_explorer.py`). The wording of the original questions is kept so the reasoning stays visible. Assumption numbers are those of `docs/keyboard_guide.md` section 8. A fix goes in `_read_node` (Member 4) or an adapter that Member 5's API calls between the parser and the explorer. Nothing here requires editing `engine/parser.py`, unless Member 1 prefers it.

- [x] **A8. Dict vs dataclass.** *Resolved:* the parser returns a `Node` dataclass with `to_dict()`; callers must use `build_explorer_tree(parse(text).to_dict())`. Passing the dataclass raises `node must be a dict, got Node` (D4 stays: no change to `_read_node`).
  - *Expects:* plain `dict` (CONTRACT shows JSON). Leaves carry `children: []`.
  - *Confirm:* what the parser returns (dict, dataclass, NamedTuple) and that leaves have a `children` list.
  - *If different:* every node raises `node must be a dict, got <Type>`.
  - *Smallest fix:* the parser exposes `to_dict()` returning the contract shape; or `dataclasses.asdict` in the API layer. Accepting objects in `_read_node` is possible (about 10 lines) but needs approval (D4).
- [x] **A9. Node names.** *Confirmed:* `parser.NODE_TYPES` is exactly the ten contract names.
  - *Expects:* the ten contract names.
  - *Confirm:* names emitted; `Fraction`/`Frac`/`Power`/`Paren` must not appear.
  - *If different:* `unsupported node type '<name>'` with the path; nothing is guessed.
  - *Smallest fix:* rename in the parser, or a name map in the adapter.
- [x] **A10. Number and variable values.** *Confirmed:* strings such as `"3"`, `"2.5"`, `".5"`; never signed; `5.` is rejected by the parser; `Variable.value` is always `"x"` (a typed `X` too).
  - *Expects:* `Number.value` is a string matching A.3 (CONTRACT: source spelling).
  - *Confirm:* the exact string for `3`, `2.5`, `.5`, `5.`; that no sign is ever included; that nothing like `1e3` is produced.
  - *If different:* `ExplorerError` naming the node. A Python `int`/`float` is also rejected.
  - *Smallest fix:* the parser stores the token text unchanged.
- [x] **A11. Child order and arity.** *Confirmed on the parser's output for `x^2`, `x/2`, `(x+1)^2`, `x - 3`:* `Pow` is `[base, exponent]`, `Div` is `[numerator, denominator]`, chains are nested pairs.
  - *Expects:* reading order; exact arity; binary nesting.
  - *Confirm:* a chain `a + b + c` is nested pairs; `Pow` is `[base, exponent]`; `Sub`/`Div` are `[first, second]`.
  - *If different:* a wrong count raises. **A reversed Pow or Div would not raise and would be spoken wrongly.**
  - *Smallest fix:* fix in the parser; the explorer cannot detect it.
- [x] **A12. Groups.** *Confirmed:* one `Group` per typed pair, span includes the brackets, and a bracketed numerator or denominator stays a `Group` inside the `Div`.
  - *Expects:* typed brackets are `Group` with one child; Group span includes the brackets (CONTRACT: "preserves explicit parentheses"; the span detail is an assumption).
  - *Confirm:* one `Group` per pair, including redundant ones; the span convention.
  - *If different:* with no `Group`, `2(x+3)` becomes `Mul(2, Add)`, the 2 becomes a `number` and the "group" explanation disappears. Wrong Group spans are not detected and are not output.
  - *Smallest fix:* parser keeps `Group`.
- [x] **A13. Implicit multiplication and powers.** *Confirmed:* `3x^2` is `Mul*(3, Pow(x, 2))`, `2x(x+1)` is `Mul*(Mul*(2, x), Group)`, `x(x+1)` is `Mul*(x, Group)`; `2 3` is refused (`adjacent`). `2 * 3x^2` is `Mul*(Mul(2, 3), Pow)`, so neither number is a coefficient.
  - *Expects:* same `Mul` as `*`; `3x^2` is `Mul(3, Pow(x, 2))`; `^` tighter than implicit multiplication.
  - *Confirm:* the shapes for `3x^2`, `2x(x+1)`, `(x+1)(x-2)`, `x(x+1)`; that two adjacent numbers (`2 3`) are rejected by the parser.
  - *If different:* `Pow(Mul(3, x), 2)` for `3x^2` is accepted; the 3 is still a coefficient but the text says the whole product is squared.
  - *Smallest fix:* fix precedence in the parser.
- [x] **A14. Negation.** *Confirmed:* `-3x` is `Mul(Neg(3), x)`. The explorer now treats the `Neg` as the (negative) coefficient or group multiplier (D5 resolved).
  - *Expects:* a minus is a `Neg` node; `-3x` is `Mul(Neg(3), x)` or `Neg(Mul(3, x))` (both give a coefficient).
  - *Confirm:* how `-3x`, `x - 3`, `x + -3`, `2*-3`, `-x^2`, `-(x+1)` are built, and unary minus against `^` and implicit multiplication.
  - *If different:* a signed `Number` is rejected.
  - *Fix applied (Member 4):* the explorer treats `Mul(Neg(Number), Variable | powered Variable | Group)` as a negative coefficient / multiplier.
- [x] **A15. Division and fractions.** *Confirmed:* only `Div` is emitted; `1/2x` and `x/2x` are refused (`ambiguous_division`). Whether inline division `x/2` should sound different from a fraction is still open (D7).
  - *Expects:* `Div` only (CONTRACT); each `Div` is read as a fraction.
  - *Confirm:* the parser never emits a different node for a stacked fraction; what `1/2x` and `x/2x` produce; whether any context needs plain inline division wording.
  - *If different:* `Fraction` is rejected as unsupported.
  - *Smallest fix:* none needed if only `Div` is emitted. If inline division must sound different from a fraction, Member 1 and 2 would have to add a distinguishing field to the contract; the explorer does not currently look at one.
- [x] **A16. Depth.** *Checked:* the parser limits input to 200 characters and bracket nesting to 30. The deepest tree 200 characters can make is a left-nested sum of 99 terms, `x=1+1+…+1` (199 characters), which is exactly 100 levels, and the explorer accepts it. There is no margin: raising the parser's `MAX_LENGTH` without raising `MAX_DEPTH` in `explore.py` and `explorer_keys.js` would turn long sums into an `ExplorerError`.
  - *Expects:* at most 100 levels counting the Equation.
  - *Confirm:* the parser has its own nesting or length limit below this and reports it as a spoken error, not an exception. A left-nested sum of 99 terms builds; 100 terms is refused (verified).
  - *If different:* `the tree is more than 100 levels deep`.
  - *Smallest fix:* cap input length or bracket depth in the parser; or ask Member 4 to raise `MAX_DEPTH` in both files (D6).

### E.2 Further assumptions found while writing this document

| # | Assumption | Status |
|---|---|---|
| A17 | Leaves carry `children: []`; a missing key raises | Confirmed (parser `to_dict()` always emits `children`) |
| A18 | Spans are offsets into the exact input string; no empty spans | Confirmed on sample inputs (see A.4); not verifiable by the explorer |
| A19 | Equation sides may be any expression, including a bare Number or Variable (`x = 5`) | handled: role `left_side`/`right_side` |
| A20 | The parser guarantees exactly one `=` (CONTRACT: exactly two Equation children) | MANDATORY on the parser side |
| A21 | `5.` is a legal Number spelling | RESOLVED: the parser rejects it (`bad_number`); the explorer's tolerance is harmless |

## F. Public API and errors

```python
from engine.explore import build_explorer_tree, ExplorerError
```

`__all__` is `["ExplorerError", "build_explorer_tree"]`. `MAX_DEPTH` (100) is importable and tested but not exported; treat it as read-only.

- `build_explorer_tree(ast: Any) -> dict` converts an Equation AST into the root ExplorerNode (section B). It returns a complete tree or raises `ExplorerError`; never partial output.
- `class ExplorerError(ValueError)`. **There are no error codes**: no `code`, `path` or other attribute, only `str(error)`. (The JavaScript module has its own codes, `tree-invalid`, `tree-too-deep`, …; they are never raised by Python.) Whether to add codes is open (D2).
- **Message format:** `"<path>: <problem>"`, where `<path>` is `ast` or `ast.children[i].children[j]…`.

| When | Message after `<path>: ` |
|---|---|
| Node is not a `dict` | `node must be a dict, got <type>` |
| `type`/`children`/`span` missing | `node is missing '<key>'` |
| `type` not a `str` / `children` not a `list` | `'type' must be a string` / `'children' must be a list` |
| Bad span | `'span' must be [start, end] with 0 <= start < end` |
| `Number` value not a string | `Number needs its source spelling as a string 'value', such as '3'` |
| `Number` string not a decimal number | `Number 'value' '<text>' is not a plain decimal number (digits with an optional decimal point)` |
| `Variable` without a non-empty string | `Variable needs a 'value' such as 'x'` |
| Value on any other type | `<Type> must not have a 'value'` |
| Unknown type (including `Fraction`) | `unsupported node type '<name>'` |
| Wrong child count | `<Type> needs N child(ren), found M` |
| Root not an Equation | `the root must be an Equation, got <Type>` |
| Equation not at root | `an Equation can only be the root` |
| Too deep, or cyclic | `the tree is more than 100 levels deep` |

- Which error is reported first is not specified (siblings are checked together before descending). Do not depend on it.
- Messages are for developers. They are not student-facing speech; the page must not read them aloud verbatim.
- **Depth:** 100 levels, Equation = level 1. A 100-level chain builds; 101 raises.
- **Immutability:** the input is never modified, and the output shares no object with it (tested by scribbling over the output).
- **ID stability:** the same AST gives identical output, ids included. Ids are positional, so editing an equation so that a node moves changes the ids below it. Do not store ids between equations. Ids contain only `n`, digits and `.`, so they are safe as DOM ids.
- **Wording is English only and provisional.** `_say`/`_phrase` in `explore.py` are the explorer's own wording; `engine/speak.py` (Member 1) now exists but the explorer does not use it yet, so digits are spoken as digits ("3", "x to the power of 2") and a rounded decimal is not announced as rounded. Do not parse or copy the spoken strings; they will change. The root's `spoken_detailed` is the whole-equation reading used by the keyboard module for **R** and the opening announcement; tell Member 4 before changing it.
- Known wording limits are in `docs/keyboard_guide.md` section 8. Multiple variables, inequalities, roots and logs are out of scope (plan §4).

## G. Integration boundaries

```
Student text
   │  Member 1: engine/parser.py   -> OwnAST (docs/contracts.md)          [merged in main]
   ▼
OwnAST
   │  Member 4: engine/explore.py  build_explorer_tree(ast)
   ▼
ExplorerNode tree (docs/contracts.md; JSON)
   │  Member 5: app.py  /api/parse-expression returns it                   [stub today]
   ▼
JSON in the browser
   │  Member 4: static/explorer_keys.js   ExplorerKeys.createView / createController
   ▼
Keyboard tree + live region  (Member 5: static/app.js, index.html, style.css)
```

| Piece | Owner |
|---|---|
| Tokeniser, parser, AST, `speak.py` | Member 1 |
| `docs/contracts.md` (shared formats) | Member 2 |
| `build_explorer_tree`, roles, the three spoken texts, `ExplorerError`, this document | Member 4 |
| `static/explorer_keys.js`, keyboard guide, accessibility checklist | Member 4 |
| `/api/parse-expression`, calling parser then explorer, error mapping, JSON transport | Member 5 |
| Page markup and CSS, Explore button, choosing the announcement mode, calling `createView`/`open`/`destroy`, moving focus in `onExit` | Member 5 |

- **Parser → explorer:** the parser guarantees the shape in A. The explorer raises on shape errors and cannot detect semantic ones (reversed order, wrong span convention).
- **Explorer → page:** the keyboard module needs only `id` (a unique non-empty string) and `children`, and depth ≤ 100; `role` and the three spoken strings are used when present; every other field is ignored. An ExplorerNode tree from `build_explorer_tree` satisfies all of this. The module no longer sees or uses a `span`.
- **Member 5:** catch the parser's error and `ExplorerError` separately; give the student a spoken message for either; never speak `str(ExplorerError)`; do not keep ids across requests. Return the root ExplorerNode to the keyboard module unwrapped.
- Out of scope by instruction: designing or implementing the frontend.

## H. Open decisions

| # | Question | Who |
|---|---|---|
| D1 | The contract's example gives `3x` the role `term` and ids like `term-left-1`; the explorer uses `operator` and path ids. Is that acceptable, or should `term` be added? | Member 2 |
| D2 | Add machine-readable error codes to `ExplorerError`? None exist | Member 4 (approval) |
| D3 | Constant role is now `constant` (the contract's name), spoken "constant term". Keep it, or change the contract to `constant_term` (the plan's name)? | Member 2 |
| D4 | Accept parser dataclasses in `_read_node`, or require `to_dict()` (currently required; Member 5's API must call it) | Member 1, Member 4 |
| D5 | RESOLVED: `-3x` is `Mul(Neg(3), x)`; the explorer reads the `Neg` as the coefficient | done |
| D6 | Is a 100-level limit acceptable for long sums? | Member 1, Member 4 |
| D7 | Every `Div` is read as a fraction, including `x/2`. Does the team want a different reading for inline division? | Member 2, Member 1 |
