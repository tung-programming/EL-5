"""Exact real solution-set verification for Phase 1.

The public interface accepts SymPy ``Equality`` instances. The parser can
integrate by passing the equalities produced by its ``to_sympy()`` conversion.
This module intentionally has no random-sampling fallback or mistake detector.
"""

from dataclasses import asdict, dataclass

import sympy as sp


@dataclass(frozen=True)
class VerificationResult:
    """JSON-friendly result of comparing two real solution sets."""

    status: str
    previous_solutions: str
    current_solutions: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        """Return only primitive, serializable values."""
        return asdict(self)


def verify_equations(
    previous_equation: sp.Equality,
    current_equation: sp.Equality,
    variable: sp.Symbol,
) -> VerificationResult:
    """Compare exact real solution sets for two SymPy equations.

    The Phase 1 scope is one real symbol and polynomial equations of degree at
    most two. Variable-dependent denominators are reported as ``unknown`` so
    simplification cannot erase domain restrictions such as the exclusion of
    zero in ``x/x``.
    """
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
            return _unknown(support_reason)

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
        return VerificationResult(
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

    return VerificationResult(
        status="unknown",
        previous_solutions=str(previous_solutions),
        current_solutions=str(current_solutions),
        reason="SymPy could not establish whether the real solution sets are equal.",
    )


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
    return None
