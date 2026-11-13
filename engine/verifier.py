"""Exact real solution-set verification (plan.md §7.2).

The public interface accepts SymPy ``Equality`` instances or pairs. ``verify_step``
also accepts the parser's Equation nodes, which enables two Phase 2 features:

- Zero divisors: the student's tree still shows every division (SymPy would turn
  x/x into 1), so values of x that make a divisor zero are removed from the
  solution set and reported in ``warnings``.
- Random-value fallback: when SymPy cannot decide (or the equation is outside the
  degree-two scope), 20 random values of x look for a constant k with
  current = k * previous. A k found this way is then checked exactly, so the
  fallback only ever proves "valid"; otherwise the result stays "unknown".

This module has no mistake detector.
"""

import random
from dataclasses import dataclass

import sympy as sp

FALLBACK_SAMPLES = 20


@dataclass(frozen=True)
class VerificationResult:
    """JSON-friendly result of comparing two real solution sets.

    ``warnings`` are things to tell the student, e.g. that x cannot be 0 because
    the equation divides by x. They are not part of ``to_dict()``.
    """

    status: str
    previous_solutions: str
    current_solutions: str
    reason: str
    warnings: tuple = ()

    def to_dict(self) -> dict[str, str]:
        """Return only primitive, serializable values."""
        return {
            "status": self.status,
            "previous_solutions": self.previous_solutions,
            "current_solutions": self.current_solutions,
            "reason": self.reason,
        }


def verify_equations(
    previous_equation: sp.Equality,
    current_equation: sp.Equality,
    variable: sp.Symbol,
    excluded=None,
) -> VerificationResult:
    """Compare exact real solution sets for two SymPy equations.

    The scope is one real symbol and polynomial equations of degree at most two.
    Without ``excluded``, variable-dependent denominators are reported as
    ``unknown`` so simplification cannot erase domain restrictions such as the
    exclusion of zero in ``x/x``.

    ``excluded`` is a pair of SymPy sets: the values of x where the previous and
    the current equation divide by zero, read from the student's own trees (see
    ``verify_step``). With it, denominators are handled exactly: each equation is
    solved on its own domain.
    """
    if excluded is not None:
        return _verify_on_domains(previous_equation, current_equation, variable, excluded)

    if not isinstance(variable, sp.Symbol):
        return _unknown("The verification variable must be a SymPy Symbol.")

    if not isinstance(previous_equation, sp.Equality) or not isinstance(
        current_equation, sp.Equality
    ):
        return _unknown("Both inputs must be SymPy Equality objects.")

    previous_expression = previous_equation.lhs - previous_equation.rhs
    current_expression = current_equation.lhs - current_equation.rhs

    for expression in (previous_expression, current_expression):
        unsupported_symbols = expression.free_symbols - {variable}
        if unsupported_symbols:
            return _unknown("Only one variable is supported by the Phase 1 verifier.")

        if _has_variable_domain_restriction(expression, variable):
            return _unknown(
                "A variable-dependent reciprocal or zero power may restrict "
                "the real domain; "
                "this Phase 1 verifier cannot establish that domain safely."
            )

        support_reason = _unsupported_expression_reason(expression, variable)
        if support_reason:
            return _fallback(previous_expression, current_expression, variable) or _unknown(support_reason)

    previous_solutions = None
    current_solutions = None
    try:
        previous_solutions = sp.solveset(
            previous_expression, variable, domain=sp.S.Reals
        )
        current_solutions = sp.solveset(
            current_expression, variable, domain=sp.S.Reals
        )
    except Exception:
        return _fallback(previous_expression, current_expression, variable) or VerificationResult(
            status="unknown",
            previous_solutions=_solution_text(previous_solutions),
            current_solutions=_solution_text(current_solutions),
            reason="SymPy could not determine both real solution sets exactly.",
        )

    if not isinstance(previous_solutions, sp.Set) or not isinstance(
        current_solutions, sp.Set
    ):
        return VerificationResult(
            status="unknown",
            previous_solutions=_solution_text(previous_solutions),
            current_solutions=_solution_text(current_solutions),
            reason="SymPy did not return comparable solution sets.",
        )

    comparison = _compare_solution_sets(previous_solutions, current_solutions)
    if comparison is True:
        return VerificationResult(
            status="valid",
            previous_solutions=str(previous_solutions),
            current_solutions=str(current_solutions),
            reason="Both equations have the same real solution set.",
        )
    if comparison is False:
        return VerificationResult(
            status="invalid",
            previous_solutions=str(previous_solutions),
            current_solutions=str(current_solutions),
            reason="The equations have different real solution sets.",
        )

    return _fallback(previous_expression, current_expression, variable) or VerificationResult(
        status="unknown",
        previous_solutions=str(previous_solutions),
        current_solutions=str(current_solutions),
        reason="SymPy could not establish whether the real solution sets are equal.",
    )


def _fallback(previous_expression, current_expression, variable):
    """Random-value fallback. Returns a "valid" result or None.

    Finds k with current = k * previous at FALLBACK_SAMPLES random rationals, then
    proves current - k * previous == 0 exactly. Only for expressions with no
    division by x and no floats, where that identity means equal solution sets.
    """
    for expression in (previous_expression, current_expression):
        if (expression.has(sp.Float, sp.nan, sp.zoo)
                or expression.free_symbols - {variable}
                or _has_variable_domain_restriction(expression, variable)
                or any(variable in d.free_symbols for d in _denominators(expression))):
            return None
    rng = random.Random(20261113)
    ratio = None
    usable = 0
    for _ in range(FALLBACK_SAMPLES * 3):
        point = sp.Rational(rng.randint(-997, 997), rng.randint(1, 61))
        try:
            before = previous_expression.subs(variable, point)
            after = current_expression.subs(variable, point)
        except Exception:
            continue
        if before == 0 or not before.is_finite or not after.is_finite:
            continue
        sample = sp.nsimplify(after / before)
        if ratio is None:
            ratio = sample
        elif sample != ratio:
            return None
        usable += 1
        if usable == FALLBACK_SAMPLES:
            break
    if ratio is None or usable < FALLBACK_SAMPLES or ratio == 0 or ratio.is_real is not True:
        return None
    try:
        proven = sp.expand(current_expression - ratio * previous_expression) == 0
    except Exception:
        return None
    if not proven:
        return None
    return VerificationResult(
        status="valid",
        previous_solutions="unknown",
        current_solutions="unknown",
        reason=(
            f"The current equation is the previous one multiplied by {ratio} "
            f"(found with {FALLBACK_SAMPLES} random values of x, then checked "
            "exactly), so both have the same real solutions."
        ),
    )


def _denominators(expression):
    _, denominator = sp.fraction(sp.together(expression))
    return [denominator]


def _verify_on_domains(previous_equation, current_equation, variable, excluded):
    """Solve each equation on its own domain: reals minus where it divides by zero."""
    previous_excluded, current_excluded = excluded
    solved = []
    for equation, excluded_points in ((previous_equation, previous_excluded),
                                      (current_equation, current_excluded)):
        if not isinstance(equation, sp.Equality):
            return _unknown("Both inputs must be SymPy Equality objects.")
        expression = equation.lhs - equation.rhs
        if expression.free_symbols - {variable}:
            return _unknown("Only one variable is supported by the verifier.")
        if expression.has(sp.nan, sp.zoo):
            return _unknown("The equation divides by zero, so it has no value.")
        try:
            numerator, denominator = sp.fraction(sp.together(expression))
        except Exception:
            return _unknown("The equation is outside the supported polynomial scope.")
        support_reason = _unsupported_expression_reason(numerator, variable)
        if support_reason:
            if variable in denominator.free_symbols:
                return _unknown(support_reason)
            return (_fallback(previous_equation.lhs - previous_equation.rhs,
                              current_equation.lhs - current_equation.rhs, variable)
                    or _unknown(support_reason))
        try:
            solutions = sp.solveset(numerator, variable, domain=sp.S.Reals)
            if variable in denominator.free_symbols:
                excluded_points = sp.Union(
                    excluded_points, sp.solveset(denominator, variable, domain=sp.S.Reals))
            solutions = sp.Complement(solutions, excluded_points)
        except Exception:
            return _unknown("SymPy could not determine both real solution sets exactly.")
        solved.append(solutions)

    previous_solutions, current_solutions = solved
    comparison = _compare_solution_sets(previous_solutions, current_solutions)
    status = {True: "valid", False: "invalid"}.get(comparison, "unknown")
    reason = {
        "valid": "Both equations have the same real solution set.",
        "invalid": "The equations have different real solution sets.",
        "unknown": "SymPy could not establish whether the real solution sets are equal.",
    }[status]
    return VerificationResult(status, str(previous_solutions), str(current_solutions), reason)


def _unknown(reason: str) -> VerificationResult:
    return VerificationResult(
        status="unknown",
        previous_solutions="unknown",
        current_solutions="unknown",
        reason=reason,
    )


def _solution_text(solution_set) -> str:
    return "unknown" if solution_set is None else str(solution_set)


def _has_variable_domain_restriction(expression, variable) -> bool:
    """Detect preserved reciprocal or zero powers depending on x."""
    for node in sp.preorder_traversal(expression):
        if (
            isinstance(node, sp.Pow)
            and variable in node.base.free_symbols
            and (node.exp.is_negative is True or node.exp == 0)
        ):
            return True
    return False


def _unsupported_expression_reason(expression, variable):
    """Return a reason when an input is outside the small exact MVP scope."""
    if expression.has(sp.Float):
        return "Floating-point coefficients are not accepted for exact verification."

    try:
        polynomial = sp.Poly(expression, variable)
    except (sp.PolynomialError, TypeError, ValueError):
        return "The equation is outside the supported polynomial scope."

    if polynomial.degree() > 2:
        return "The Phase 1 verifier supports equations of degree at most two."

    if any(coefficient.is_real is not True for coefficient in polynomial.all_coeffs()):
        return "The Phase 1 verifier supports only real polynomial coefficients."

    return None


def _compare_solution_sets(previous, current):
    """Return True/False only when exact set equality/inequality is established."""
    try:
        if previous == current:
            return True
    except Exception:
        return None

    # A non-identical ConditionSet is unresolved unless a future exact set
    # procedure can prove its relationship to the other set.
    if isinstance(previous, sp.ConditionSet) or isinstance(current, sp.ConditionSet):
        return None

    try:
        previous_is_subset = previous.is_subset(current)
        current_is_subset = current.is_subset(previous)
    except Exception:
        return None

    if previous_is_subset is True and current_is_subset is True:
        return True
    if previous_is_subset is False or current_is_subset is False:
        return False
    # is_subset can be undecided for intervals with holes (all reals except 0);
    # a set difference that is provably nonempty still settles it.
    try:
        if (sp.Complement(previous, current).is_empty is False
                or sp.Complement(current, previous).is_empty is False):
            return False
    except Exception:
        return None
    return None


def verify_step(previous, current) -> VerificationResult:
    """Adapt parser outputs to the equation-based verifier interface.

    ``previous`` and ``current`` may each be a parser Equation node, a two-item
    tuple/list of SymPy expressions or an existing SymPy Equality. Raw strings
    and other values are rejected; user text must go through the custom parser.

    When both are parser nodes, divisions in the student's own trees define each
    equation's domain, and every divisor that can be zero becomes a warning.
    """
    if _is_equation_node(previous) and _is_equation_node(current):
        return _verify_nodes(previous, current)

    previous_equation, error = _as_equation(previous, "previous")
    if error:
        return _unknown(error)

    current_equation, error = _as_equation(current, "current")
    if error:
        return _unknown(error)

    try:
        from engine.parser import X
    except ImportError:
        return _unknown("The parser's shared variable X is unavailable.")

    return verify_equations(previous_equation, current_equation, X)


def _is_equation_node(value) -> bool:
    return getattr(value, "type", None) == "Equation" and callable(getattr(value, "to_sympy", None))


def _zero_divisors(tree):
    """Values of x that make a divisor in the student's tree zero, and a warning
    for each such divisor: (excluded set, [warning text])."""
    from engine.parser import X, to_sympy, walk

    excluded = sp.S.EmptySet
    warnings = []
    for node in walk(tree):
        divisor = None
        if node.type == "Div":
            divisor = node.children[1]
        elif node.type == "Pow" and node.children[1].type in ("Neg", "Number"):
            exponent = to_sympy(node.children[1], evaluate=True)
            if exponent.is_number and exponent <= 0:
                divisor = node.children[0]   # x^-1 is 1/x; x^0 is undefined at x = 0
        if divisor is None:
            continue
        value = to_sympy(divisor, evaluate=True)
        if X not in value.free_symbols:
            continue
        zeros = sp.solveset(value, X, domain=sp.S.Reals)
        if not isinstance(zeros, sp.FiniteSet) or not zeros:
            continue
        excluded = sp.Union(excluded, zeros)
        values = " or ".join(str(z) for z in sorted(zeros, key=lambda z: float(z)))
        warnings.append(f"x cannot be {values} here, because the equation divides by {value}.")
    return excluded, warnings


def _verify_nodes(previous, current):
    from engine.parser import X

    previous_equation, error = _as_equation(previous.to_sympy(), "previous")
    if error:
        return _unknown(error)
    current_equation, error = _as_equation(current.to_sympy(), "current")
    if error:
        return _unknown(error)
    previous_excluded, previous_warnings = _zero_divisors(previous)
    current_excluded, current_warnings = _zero_divisors(current)
    result = verify_equations(previous_equation, current_equation, X,
                              excluded=(previous_excluded, current_excluded))
    warnings = tuple(dict.fromkeys(previous_warnings + current_warnings))
    if not warnings:
        return result
    return VerificationResult(result.status, result.previous_solutions,
                              result.current_solutions, result.reason, warnings)


def _as_equation(value, name: str):
    if isinstance(value, sp.Equality):
        return value, None

    if not isinstance(value, (tuple, list)):
        return None, f"The {name} step must be a SymPy Equality or a pair of SymPy expressions."
    if len(value) != 2:
        return None, f"The {name} equation pair must contain exactly two expressions."

    lhs, rhs = value
    if not isinstance(lhs, sp.Expr) or not isinstance(rhs, sp.Expr):
        return None, f"The {name} equation pair must contain SymPy expressions, not raw values."

    try:
        equation = sp.Eq(lhs, rhs, evaluate=False)
    except (TypeError, ValueError) as exc:
        return None, f"The {name} equation pair could not be converted: {exc}"
    if not isinstance(equation, sp.Equality):
        return None, f"The {name} equation pair did not produce a SymPy Equality."
    return equation, None
