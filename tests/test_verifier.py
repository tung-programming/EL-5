"""Independent tests for the Phase 1 SymPy solution-set verifier."""

import sympy as sp
import pytest

from engine import verifier
from engine.verifier import VerificationResult, verify_equations


def equation(lhs, rhs):
    return sp.Eq(lhs, rhs, evaluate=False)


@pytest.fixture
def x():
    return sp.Symbol("x")


def test_valid_linear_transformation(x):
    previous = equation(3 * x + 5, 14)
    current = equation(3 * x, 9)

    result = verify_equations(previous, current, x)

    assert result.status == "valid"
    assert result.previous_solutions == "{3}"
    assert result.current_solutions == "{3}"


def test_invalid_arithmetic_transformation(x):
    result = verify_equations(
        equation(3 * x + 5, 14), equation(3 * x, 10), x
    )

    assert result.status == "invalid"
    assert result.previous_solutions == "{3}"
    assert result.current_solutions == "{10/3}"


@pytest.mark.parametrize(
    ("previous", "current", "expected_solution"),
    [
        (lambda x: equation(2 * x, 8), lambda x: equation(x, 4), "{4}"),
        (
            lambda x: equation(x / 3, sp.Rational(2, 3)),
            lambda x: equation(x, 2),
            "{2}",
        ),
        (lambda x: equation(-3 * x, 12), lambda x: equation(x, -4), "{-4}"),
    ],
)
def test_valid_multiplication_or_division_by_constants(
    x, previous, current, expected_solution
):
    result = verify_equations(previous(x), current(x), x)

    assert result.status == "valid"
    assert result.previous_solutions == expected_solution
    assert result.current_solutions == expected_solution


def test_lost_solution_is_invalid(x):
    result = verify_equations(equation(x**2, 1), equation(x, 1), x)

    assert result.status == "invalid"
    assert result.previous_solutions == "{-1, 1}"
    assert result.current_solutions == "{1}"


def test_extra_solution_is_invalid(x):
    result = verify_equations(equation(x, 2), equation(x**2, 4), x)

    assert result.status == "invalid"
    assert result.previous_solutions == "{2}"
    assert result.current_solutions == "{-2, 2}"


def test_swapped_sides_are_valid(x):
    result = verify_equations(
        equation(x + 2, 5), equation(5, x + 2), x
    )

    assert result.status == "valid"
    assert result.previous_solutions == result.current_solutions == "{3}"


def test_equivalent_polynomial_representations_are_valid(x):
    result = verify_equations(equation(x * x, 9), equation(x**2, 9), x)

    assert result.status == "valid"
    assert result.previous_solutions == result.current_solutions == "{-3, 3}"


def test_different_sympy_representations_of_the_same_set_are_valid(x, monkeypatch):
    returned_sets = iter((sp.S.Reals, sp.Interval(-sp.oo, sp.oo)))
    monkeypatch.setattr(verifier.sp, "solveset", lambda *args, **kwargs: next(returned_sets))

    result = verify_equations(equation(x, 0), equation(x, 1), x)

    assert result.status == "valid"


def test_identity_equations_have_all_real_solutions(x):
    result = verify_equations(equation(x + 1, x + 1), equation(0, 0), x)

    assert result.status == "valid"
    assert result.previous_solutions == "Reals"
    assert result.current_solutions == "Reals"


def test_contradiction_equations_have_no_real_solutions(x):
    result = verify_equations(equation(x + 2, x + 5), equation(2, 5), x)

    assert result.status == "valid"
    assert result.previous_solutions == "EmptySet"
    assert result.current_solutions == "EmptySet"


def test_different_finite_real_solution_sets_are_invalid(x):
    result = verify_equations(equation(x**2, 4), equation(x, 2), x)

    assert result.status == "invalid"


def test_cubic_outside_phase_one_scope_is_unknown(x):
    result = verify_equations(equation(x**3, 8), equation(x, 2), x)

    assert result.status == "unknown"
    assert "degree at most two" in result.reason


def test_non_polynomial_expression_outside_scope_is_unknown(x):
    result = verify_equations(equation(sp.sin(x), 0), equation(x, 0), x)

    assert result.status == "unknown"
    assert "polynomial scope" in result.reason


def test_unresolved_condition_sets_return_unknown(x, monkeypatch):
    previous_set = sp.ConditionSet(x, sp.Eq(sp.sin(x), 0), sp.S.Reals)
    current_set = sp.ConditionSet(x, sp.Eq(sp.cos(x), 0), sp.S.Reals)
    returned_sets = iter((previous_set, current_set))
    monkeypatch.setattr(verifier.sp, "solveset", lambda *args, **kwargs: next(returned_sets))

    result = verify_equations(equation(x, 1), equation(x, 2), x)

    assert result.status == "unknown"
    assert result.previous_solutions.startswith("ConditionSet(")


def test_unsupported_symbol_returns_unknown(x):
    y = sp.Symbol("y")

    result = verify_equations(equation(x + y, 1), equation(x, 1), x)

    assert result.status == "unknown"
    assert "Only one variable" in result.reason


def test_variable_dependent_denominator_returns_unknown(x):
    reciprocal_x = sp.Pow(x, -1, evaluate=False)
    quotient = sp.Mul(x, reciprocal_x, evaluate=False)

    result = verify_equations(equation(x, 0), equation(quotient, 1), x)

    assert result.status == "unknown"
    assert "real domain" in result.reason


def test_zero_power_that_may_restrict_domain_returns_unknown(x):
    zero_power = sp.Pow(x, 0, evaluate=False)

    result = verify_equations(equation(zero_power, 1), equation(1, 1), x)

    assert result.status == "unknown"
    assert "real domain" in result.reason


def test_solver_exception_returns_unknown(x, monkeypatch):
    def raise_solver_error(*args, **kwargs):
        raise RuntimeError("solver failure")

    monkeypatch.setattr(verifier.sp, "solveset", raise_solver_error)
    result = verify_equations(equation(x, 1), equation(x, 1), x)

    assert result.status == "unknown"
    assert result.previous_solutions == "unknown"
    assert "could not determine" in result.reason


def test_result_serializes_only_plain_strings(x):
    result = verify_equations(equation(x, 1), equation(x, 2), x)

    assert isinstance(result, VerificationResult)
    serialized = result.to_dict()
    assert set(serialized) == {
        "status",
        "previous_solutions",
        "current_solutions",
        "reason",
    }
    assert all(isinstance(value, str) for value in serialized.values())
