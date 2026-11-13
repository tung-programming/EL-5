"""Independent tests for the Phase 1 SymPy solution-set verifier."""

import sympy as sp
import pytest

from engine import verifier
from engine.parser import X
from engine.verifier import VerificationResult, verify_equations, verify_step


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
    # Not a constant multiple of each other, so the random-value fallback can't help.
    result = verify_equations(equation(x, 1), equation(x, 2), x)

    assert result.status == "unknown"
    assert result.previous_solutions == "unknown"
    assert "could not determine" in result.reason


def test_solver_exception_uses_random_value_fallback_for_multiples(x, monkeypatch):
    def raise_solver_error(*args, **kwargs):
        raise RuntimeError("solver failure")

    monkeypatch.setattr(verifier.sp, "solveset", raise_solver_error)
    result = verify_equations(equation(x + 2, 5), equation(2 * x + 4, 10), x)

    assert result.status == "valid"
    assert "random values" in result.reason


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


def test_verify_step_accepts_valid_tuple_inputs():
    result = verify_step((3 * X + 5, sp.Integer(14)), (3 * X, sp.Integer(9)))

    assert result.status == "valid"
    assert result.previous_solutions == result.current_solutions == "{3}"


def test_verify_step_accepts_invalid_tuple_inputs():
    result = verify_step(
        (3 * X + 5, sp.Integer(14)),
        (3 * X, sp.Integer(10)),
    )

    assert result.status == "invalid"
    assert result.previous_solutions == "{3}"
    assert result.current_solutions == "{10/3}"


def test_verify_step_accepts_list_inputs():
    result = verify_step([2 * X, sp.Integer(8)], [X, sp.Integer(4)])

    assert result.status == "valid"


def test_verify_step_accepts_existing_equalities():
    previous = equation(3 * X + 5, 14)
    current = equation(3 * X, 9)

    result = verify_step(previous, current)

    assert result.status == "valid"


def test_verify_step_accepts_mixed_tuple_and_equality_inputs():
    current = equation(3 * X, 9)

    result = verify_step((3 * X + 5, sp.Integer(14)), current)

    assert result.status == "valid"


@pytest.mark.parametrize(
    ("previous", "current"),
    [
        (None, (X, sp.Integer(1))),
        ("x = 1", (X, sp.Integer(1))),
        (7, (X, sp.Integer(1))),
        ((X,), (X, sp.Integer(1))),
        ([X, sp.Integer(1), sp.Integer(2)], (X, sp.Integer(1))),
        ((X, 1), (X, sp.Integer(1))),
    ],
)
def test_verify_step_returns_unknown_for_malformed_inputs(previous, current):
    result = verify_step(previous, current)

    assert result.status == "unknown"
    assert result.reason


def test_verify_step_agrees_with_verify_equations_using_parser_x():
    previous = equation(3 * X + 5, 14)
    current = equation(3 * X, 10)

    adapted = verify_step((previous.lhs, previous.rhs), (current.lhs, current.rhs))
    direct = verify_equations(previous, current, X)

    assert adapted.to_dict() == direct.to_dict()


def test_verify_step_does_not_suppress_unexpected_internal_errors(monkeypatch):
    def raise_internal_error(*args, **kwargs):
        raise RuntimeError("unexpected internal error")

    monkeypatch.setattr(verifier, "verify_equations", raise_internal_error)

    with pytest.raises(RuntimeError, match="unexpected internal error"):
        verify_step((X, sp.Integer(1)), (X, sp.Integer(1)))


# ---- Phase 2: random-value fallback and zero divisors (parser trees) ----------

def test_cubic_multiple_is_proven_valid_by_fallback(x):
    result = verify_equations(equation(x**3, 8), equation(2 * x**3, 16), x)

    assert result.status == "valid"
    assert "multiplied by 2" in result.reason


def test_fallback_never_decides_a_non_multiple(x):
    # Same real solution, but not a multiple: still outside scope, still unknown.
    result = verify_equations(equation(x**3, 8), equation(x, 2), x)

    assert result.status == "unknown"


def test_parser_trees_keep_division_by_x_that_sympy_would_cancel():
    from engine.parser import parse

    result = verify_step(parse("x = 0"), parse("x/x = 1"))

    assert result.status == "invalid"
    assert result.warnings == ("x cannot be 0 here, because the equation divides by x.",)


def test_identity_with_a_hole_is_not_the_same_as_an_identity():
    from engine.parser import parse

    result = verify_step(parse("x/x = 1"), parse("x + 1 = x + 1"))

    assert result.status == "invalid"


def test_reciprocal_equation_is_solved_on_its_domain():
    from engine.parser import parse

    result = verify_step(parse("1/x = 2"), parse("1 = 2x"))

    assert result.status == "valid"
    assert result.current_solutions == "{1/2}"
    assert result.warnings


def test_solution_at_a_zero_divisor_is_removed():
    from engine.parser import parse

    result = verify_step(parse("x/(x - 1) = 1/(x - 1)"), parse("x = 1"))

    assert result.status == "invalid"
    assert result.previous_solutions == "EmptySet"
    assert "x cannot be 1" in result.warnings[0]


def test_parser_trees_without_division_match_tuple_inputs():
    from engine.parser import parse

    from_trees = verify_step(parse("3x + 5 = 14"), parse("3x = 10"))
    from_tuples = verify_step(parse("3x + 5 = 14").to_sympy(), parse("3x = 10").to_sympy())

    assert from_trees.to_dict() == from_tuples.to_dict()
    assert from_trees.warnings == ()
