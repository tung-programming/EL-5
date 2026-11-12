# Known limitations

Owner: Member 3

## Phase 1 verifier scope

- The verifier currently accepts SymPy `Equality` objects and one SymPy
  `Symbol`; it is not wired to M1's parser because that parser is not yet
  implemented.
- It decides only real polynomial equations of degree at most two, with exact
  real coefficients. Inputs with unsupported symbols, floating-point
  coefficients, higher degree, non-polynomial expressions, or unresolved
  `ConditionSet` relationships return `unknown`.
- A variable-dependent denominator or zero power is conservatively classified
  as `unknown`. SymPy may simplify expressions such as `x/x` before the
  verifier receives them; the parser integration must preserve unevaluated
  domain-sensitive expressions for the guard to detect them.
- Set equality uses exact SymPy equality and mutual subset checks. If SymPy
  cannot prove equality or inequality, the verifier returns `unknown` rather
  than approximating roots or sampling values.

## Deferred to Phase 2

The verifier has no random-value fallback, advanced zero-divisor warnings,
solution-based mistake detection, or divide-by-variable / lost-solution /
extra-solution labels. Explanations do not implement detailed templates or
mistake-specific wording. They use only a basic valid/invalid/unknown response
and may name a supported operation only when supplied consistent inference
data is available.

## Integration dependencies

M1 must provide SymPy `Equality` objects while preserving relevant expression
domains. M2 may provide an inference structure with `operation`, `operand`, and
`applied_to`; Phase 1 explanation text uses it only for recognized arithmetic
operations explicitly applied to both sides. The verifier and explanation
modules do not call or modify M1 or M2 code.
