"""Tests for algebraic operation inference."""
import sympy as sp

from engine.infer import infer_operation

x = sp.Symbol("x")


def test_subtract_constant():
    assert infer_operation((3*x + 5, 14), (3*x, 9))["operand"] == "5"
    assert infer_operation((3*x + 5, 14), (3*x, 9))["operation"] == "subtract"


def test_add_negative_difference():
    got = infer_operation((x - 3, 7), (x, 10))
    assert (got["operation"], got["operand"]) == ("add", "3")


def test_divide_both_sides():
    got = infer_operation((2*x, 8), (x, 4))
    assert (got["operation"], got["operand"]) == ("divide", "2")


def test_multiply_both_sides():
    got = infer_operation((x/2, 3), (x, 6))
    assert (got["operation"], got["operand"]) == ("multiply", "2")


def test_no_change_is_no_inference():
    assert infer_operation((x + 2, 5), (x + 2, 5)) is None


def test_different_changes_do_not_match():
    assert infer_operation((x + 5, 14), (x, 8)) is None


def test_variable_ratio_not_reported():
    assert infer_operation((x**2, x + 1), (x, x + 1)) is None


def test_zero_denominator_is_safe():
    assert infer_operation((2*x, 0), (x, 0)) is None


def test_negative_constant_difference():
    got = infer_operation((x - 4, 2), (x, 6))
    assert (got["operation"], got["operand"]) == ("add", "4")


def test_equivalent_term_ordering():
    got = infer_operation((3*x + 5, 14), (5 + 3*x - 5, 14 - 5))
    assert (got["operation"], got["operand"]) == ("subtract", "5")


def test_swapped_sides_early_phase_2():
    got = infer_operation((x + 2, 5), (5, x + 2))
    assert got["operation"] == "swap_sides"


def test_negative_ratio():
    got = infer_operation((2*x, 8), (-x, -4))
    assert (got["operation"], got["operand"]) == ("divide", "-2")


def test_fractional_ratio():
    got = infer_operation((x/2, 3), (x, 6))
    assert (got["operation"], got["operand"]) == ("multiply", "2")


def test_decimal_ratio():
    got = infer_operation((sp.Float("3.0")*x, 6), (2*x, 4))
    assert got is not None
    assert got["operation"] == "divide"
    assert sp.Float(got["operand"]) == sp.Float("1.5")


def test_ratio_with_symbolic_denominator_stays_unsupported():
    assert infer_operation((x, x**2), (1, x)) is None


def test_zero_sides_and_zero_simplifications_are_safe():
    assert infer_operation((2*x, 0), (x, 0)) is None
    assert infer_operation((x + 0, 2), (x, 2)) is None


def test_restricted_domain_ratio_is_not_called_constant():
    # Both ratios reduce to x, which is variable and only zero at a restricted value.
    assert infer_operation((x, 2*x), (1, 2)) is None


def test_exact_decimal_constants_are_supported():
    got = infer_operation((2*x, sp.Rational(3, 10)), (x, sp.Rational(3, 20)))
    assert (got["operation"], got["operand"]) == ("divide", "2")
