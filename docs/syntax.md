# What students can type

Owner: Member 1
Code: `engine/parser.py`. Tests: `tests/test_parser.py`.

Target: **linear equations for classes 1–5**. The limits below keep input small and
checking fast. To change them, edit the constants at the top of `engine/parser.py`.

## Allowed characters
| Kind | Allowed |
|---|---|
| Numbers | `3`, `14`, `2.5`, `.5` (not `5.` or `1.2.3`) |
| Variable | `x` (a capital `X` also works and is read as `x`) |
| Operators | `+  -  *  /  ^  **` (`**` is the same as `^`) |
| Brackets | `(  )` |
| Equals | exactly one `=` |
| Spaces | anywhere; they are ignored |

**Converted automatically** (from copy-paste or speech-to-text):

| Typed | Becomes |
|---|---|
| `−` (Unicode minus), `–` (en dash) | `-` |
| `×`, `·`, `⋅`, `∗` | `*` |
| `÷` | `/` |
| `²`, `³`, `¹⁰`, `⁻¹` (superscripts) | `^2`, `^3`, `^10`, `^-1` |

## Limits (classes 1–5)
| Limit | Value | If exceeded |
|---|---|---|
| Biggest number | 1,000,000 | error `number_too_large` |
| Decimal places | 4 | **rounded** to 4 places (5 rounds up) and the student is told, e.g. "I rounded 3.14159 to 3.1416" |
| Powers | whole numbers from −10 to 10 | error `unsupported_exponent` (also for `x^0.5`, `x^(1/2)`) |
| x inside a power | not allowed | error `variable_exponent` (`2^x`) |
| Result of a number-only power | at most 1,000,000 | error `power_too_large` (`10^7`, `9^10`) |
| Power of x after nesting | at most x^10 | error `power_too_large` (`(x^2)^6` is x^12) |
| Length | 200 characters | error `too_long` |
| Brackets inside brackets | 30 deep | error `too_deep` |

## Division by zero
Division by zero is **accepted, not rejected**. It is **undefined**:
- `to_sympy(tree, evaluate=True)` gives `sympy.nan` for that part, and for the whole side containing it.
- `undefined_parts(tree)` lists the parts that divide by zero.
- `notes(tree, text)` gives a sentence to tell the student, e.g. "x/0 divides by zero, which is undefined."

This applies to `x/0`, `5/(0)`, `x/(2-2)`, `x/(x-x)`, `0^-1` and `(1-1)^-2`.

`x/(x-1)` is *not* flagged, because it is only zero when x = 1. That case is the verifier's job (Member 3).

## Grammar (tightest-binding operator at the bottom)
```
equation := expr '=' expr
expr     := term (('+' | '-') term)*                    left to right: 8-3-2 = (8-3)-2
term     := unary (('*' | '/') unary | <implicit> power)*
unary    := ('+' | '-') power | power                   ONE sign at most
power    := primary (('^' | '**') unary)?               right to left: 2^3^2 = 2^(3^2)
primary  := NUMBER | 'x' | '(' expr ')'
```
- **Implicit multiplication** happens when `x` or `(` comes right after a number, `x` or `)`.
  - Examples: `3x`, `2(x+1)`, `(x+1)(x-1)`, `x(x+3)`, `x^2(x+1)`.
- **A sign after an operator** is read as a negative (or positive) number:

| Input | Read as |
|---|---|
| `2*-3` | `2 * (-3)` |
| `2/-3` | `2 / (-3)` |
| `2+-3` | `2 + (-3)` |
| `2--3` | `2 - (-3)` |
| `2^-3` | `2 ^ (-3)` |
| `x*-(x+1)` | `x * (-(x+1))` |

- **A unary plus is dropped:** `x = +3` is the same as `x = 3`.

## Negatives and powers (standard maths convention)
| Input | Read as | Note |
|---|---|---|
| `-x^2` | `-(x^2)` | the power is applied first |
| `(-x)^2` | `(-x)^2` | use brackets to square the negative |
| `-3^2` | `-(3^2)` | **= -9**, not 9 |
| `(-3)^2` | `(-3)^2` | = 9 |
| `-3x` | `(-3)·x` | coefficient is -3 |
| `-3x^2` | `(-3)·(x^2)` | |
| `3x^2` | `3·(x^2)` | the power belongs to x only |
| `-2(x+1)` | `(-2)·(x+1)` | |
| `2*-3^2` | `2 * (-(3^2))` | = -18 |
| `-2^-2` | `-(2^(-2))` | |
| `2^3^2` | `2^(3^2)` | = 512 |
| `8-3-2` | `(8-3)-2` | = 3 |

## Things the parser refuses (and asks the student to clarify)
| Input | Why | Student is told to type |
|---|---|---|
| `1/2x`, `2/3(x+1)`, `1/-2x` | Could mean `1/(2x)` or `(1/2)x` | `1/(2x)` or `(1/2)x` (built from their own numbers) |
| `2^3x`, `x^2x`, `2^-3x` | Could mean `2^(3x)` or `(2^3)x` | `2^(3x)` or `(2^3)x` |
| `--3`, `2---3`, `-+3` | Two signs in a row (usually a typo) | `-(-3)` if a double negative is meant |

Allowed on purpose (not ambiguous):
- `1/2*x`: the `*` is explicit, so it reads left to right as `(1/2)*x`.
- `x^2(x+1)`: a power followed by a bracket is the usual factored form, `(x^2)(x+1)`.

## Error kinds
`ParseError` has `.kind`, `.position` (0-based) and `.message`, plus `.to_dict()` for the API.

Messages are read aloud, so they quote the student's own text instead of giving a character number. For example: *Something is missing after "3x +".*

| kind | Example input |
|---|---|
| `empty` | (empty box) |
| `too_long` | more than 200 characters |
| `too_deep` | more than 30 brackets inside each other |
| `bad_symbol` | `3y + 5 = 14`, `2,5x = 1`, `[x] = 1` |
| `bad_number` | `1.2.3 = x`, `5. = x` |
| `number_too_large` | `x = 1000001` |
| `unsupported_exponent` | `x^11 = 1`, `x^0.5 = 3` |
| `variable_exponent` | `2^x = 8` |
| `power_too_large` | `10^7 = x`, `(x^2)^6 = 1` |
| `no_equals` | `3x + 5` |
| `many_equals` | `x = 2 = 3`, `x == 3` |
| `empty_side` | `= 5`, `x =` |
| `missing_operand` | `3x + = 14`, `2^ = x`, `(x+) = 1` |
| `double_sign` | `--3 = x` |
| `adjacent` | `x2 = 4`, `3 4 = x`, `(x+1)3 = 6` |
| `unclosed` | `2(x+3 = 10` |
| `extra_close` | `x) = 3` |
| `empty_brackets` | `() = 3` |
| `ambiguous_division` | `1/2x = 4` |
| `ambiguous_exponent` | `2^3x = 8` |
| `unexpected` | `*3 = x` (anything else out of place) |

## How it is spoken (`engine/speak.py`)
| Input | Spoken |
|---|---|
| `3x + 5 = 14` | three x plus five equals fourteen |
| `2(x+3)` | two times open bracket x plus three close bracket |
| `x - 3` / `x = -3` | x minus three / x equals negative three |
| `-x^2` | negative of x squared |
| `(-x)^2` | open bracket negative x close bracket squared |
| `x^2`, `x^3`, `x^5` | x squared, x cubed, x to the power of five |
| `2^3^2` | two to the power of three squared, end power |
| `x/2` | x over two |
| `2.5` | two point five |
| `115` | one hundred fifteen (no "and", so it can't be confused with "plus") |
