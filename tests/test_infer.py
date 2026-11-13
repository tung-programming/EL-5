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
    # No 0/0: a zero side is handled by the generic check, which names the division.
    got = infer_operation((2*x, 0), (x, 0))
    assert (got["operation"], got["operand"]) == ("divide", "2")


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
    assert infer_operation((2*x, 0), (x, 0))["operation"] == "divide"
    assert infer_operation((x + 0, 2), (x, 2)) is None


def test_restricted_domain_ratio_is_not_called_constant():
    # Both ratios reduce to x, which is variable and only zero at a restricted value.
    assert infer_operation((x, 2*x), (1, 2)) is None


def test_exact_decimal_constants_are_supported():
    got = infer_operation((2*x, sp.Rational(3, 10)), (x, sp.Rational(3, 20)))
    assert (got["operation"], got["operand"]) == ("divide", "2")


# ---- Phase 2: x-terms, rewrites and the generic check -----------------------

from engine.parser import parse


def _infer(previous, current):
    return infer_operation(parse(previous), parse(current))


def test_subtracting_an_x_term_from_both_sides():
    got = _infer("5x + 2 = 3x + 8", "2x = 6")
    assert (got["operation"], got["operand"]) == ("subtract", "3*x + 2")
    got = _infer("x = 12 - 2x", "3x = 12")
    assert (got["operation"], got["operand"]) == ("add", "2*x")


def test_rewrite_kinds():
    cases = {
        ("2(x + 3) = 10", "2x + 6 = 10"): "expand",
        ("2x + 6 = 10", "2(x + 3) = 10"): "factor",
        ("2x + 3x = 20", "5x = 20"): "collect_like_terms",
        ("3x + 5 = 14", "5 + 3x = 14"): "reorder",
        ("x*x = 9", "x^2 = 9"): "simplify",
    }
    for (previous, current), kind in cases.items():
        got = _infer(previous, current)
        assert (got["operation"], got["kind"], got["applied_to"]) == ("rewrite", kind, "left_side_only")


def test_rewrite_needs_parser_trees():
    # The same step as SymPy pairs looks unchanged, so nothing is claimed.
    assert infer_operation((2*x + 6, 10), (2*x + 6, 10)) is None


def test_rewrite_on_the_right_side():
    got = _infer("x = 2(3 + 1)", "x = 6 + 2")
    assert (got["operation"], got["applied_to"]) == ("rewrite", "right_side_only")


def test_equal_sides_are_a_rewrite_not_a_swap():
    got = _infer("0*x = 0", "0 = 0")
    assert got["operation"] == "rewrite"


def test_generic_same_steps_on_both_sides():
    assert _infer("x + 2 = 5", "2x = 6")["operation"] == "combined"
    assert _infer("x + 2 = 5", "2x = 7") is None    # near miss: not a multiple
