# Known limitations

Owner: Member 3

## Verifier scope

- The app passes the parser's trees to `verify_step`. Plain SymPy pairs and
  `Equality` objects are still accepted (tests and the CLI fallback use them).
- It solves real polynomial equations of degree at most two exactly, with exact
  real coefficients. Unsupported symbols, floating-point coefficients and
  non-polynomial expressions return `unknown`.
- Higher degree: the random-value fallback can still prove a step `valid` when
  the new equation is a constant multiple of the old one (`x^3 = 8 → 2x^3 = 16`).
  It never proves `invalid`, so `x^3 = 8 → x = 2` stays `unknown`.
- The fallback finds the constant with 20 random rationals but then proves the
  identity exactly. It is skipped when either equation divides by x.

## Zero divisors

- With parser trees, every division by an expression with x (and every power
  of x with exponent ≤ 0) removes its zeros from that equation's solution set
  and adds a warning ("x cannot be 0 here, because the equation divides by x.").
  The explanation's detailed level reads these warnings out.
- With plain SymPy input, SymPy may already have cancelled `x/x`, so a
  variable denominator is still classified as `unknown`, as in Phase 1.

## Mistake detection

- A label is given only when the check rebuilds the student's exact line;
  otherwise the mistake is null and the explanation gives both solution sets.
- A one-sided step counts only when it is one a student would take: removing
  the constant term, or multiplying/dividing by a whole number (or its
  reciprocal). Unusual steps such as `x + 7 = 12 → x + 2 = 8` get no label.
- A wrong sign after dividing by a negative (`-3x = 12 → x = 4`) is not named.
- The structural labels (`partial_distribution`, `exponent_error`,
  `coefficient_error`) need the parser's trees; with SymPy input they are skipped.

## Explanations

- Concise and detailed text are built only from the verified JSON. Without
  `operation`/`operand`/`before` evidence, mistake text falls back to "The right
  side should be 9, not 10."
- Maths in explanations is written for speech: `x**2` becomes "x squared",
  `2*x` becomes "2x", `sqrt(2)` becomes "√2".
