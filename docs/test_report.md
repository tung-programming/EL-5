# Test report

Owner: Member 3

## Phase 1 symbolic verifier

`engine.verifier.verify_equations(previous_equation, current_equation, variable)`
accepts two SymPy `Equality` objects and a SymPy `Symbol`. Each equation is
solved with `sympy.solveset(lhs - rhs, variable, domain=sympy.S.Reals)`. The
returned sets are compared exactly: equal sets produce `valid`, provably
different sets produce `invalid`, and unresolved or out-of-scope inputs produce
`unknown`.

The verifier supports one real variable and polynomial equations up to degree
two. It returns a `VerificationResult`; `to_dict()` serializes the status,
solution-set strings, and reason without exposing SymPy objects.

## Phase 1 explanations

`engine.explain.build_explanation(status, verification=None, inference=None,
mistake=None)` returns `{"concise": ..., "detailed": ...}`. Valid and invalid
outcomes use short deterministic templates; an unknown outcome uses a safe
fallback. Detailed text repeats concise text in Phase 1. A valid step may name
an operation only when supported inference data explicitly says it was applied
to both sides. Invalid explanations may include only simple solution values
from the verification result. Mistake labels are not rendered by this phase.

## Running the tests

Install the dependencies when needed with `python -m pip install pytest sympy`,
then run:

```text
python -m pytest tests/test_verifier.py tests/test_explain.py tests/test_cases.py -v
```

The verifier and explanation tests construct SymPy equations directly and do
not depend on the parser, inference, mistake, API, or frontend modules.

## Current Phase 1 run

On Python 3.11 with SymPy 1.14.0 and pytest 9.2.0, the combined command above
collected **48 tests and all passed**: 21 verifier tests, 12 explanation tests,
and 15 catalogue tests. The catalogue-only command
`python -m pytest tests/test_cases.py -v` collected **15 tests and all passed**.
Both runs also reported a deprecation warning from the environment's existing
AnyIO pytest plugin; it did not affect test results.
