"""Positive and near-miss coverage for Phase 1 operation mistakes."""
import sympy as sp

from engine.mistakes import detect_mistake

x = sp.Symbol("x")


def test_one_side_only_division():
    got = detect_mistake((2*x, 8), (x, 8), verifier_result="invalid")
    assert got == {"label": "one_side_only", "expected": "4", "got": "8", "location": "right_side",
                   "operation": "divide", "operand": "2", "before": "8"}


def test_arithmetic_error_after_subtraction():
    got = detect_mistake((3*x + 5, 14), (3*x, 10), verifier_result="invalid")
    assert got == {"label": "arithmetic_error", "expected": "9", "got": "10", "location": "right_side",
                   "operation": "subtract", "operand": "5", "before": "14"}


def test_correct_step_has_no_mistake():
    assert detect_mistake((3*x + 5, 14), (3*x, 9), verifier_result="invalid") is None


def test_unrelated_step_has_no_supported_label():
    assert detect_mistake((x**2 + 2, 8), (x + 7, 3), verifier_result="invalid") is None


def test_one_side_near_miss_requires_unchanged_other_side():
    assert detect_mistake((2*x, 8), (x, 4), verifier_result="invalid") is None


def test_arithmetic_near_miss_with_ambiguous_change():
    assert detect_mistake((x**2 + 2, 8), (x + 7, 3), verifier_result="invalid") is None


def test_zero_constant_does_not_trigger():
    assert detect_mistake((x, 0), (x, 0), verifier_result="invalid") is None


def test_negative_constant_arithmetic():
    got = detect_mistake((x - 3, 7), (x, 11), verifier_result="invalid")
    assert got == {"label": "arithmetic_error", "expected": "10", "got": "11", "location": "right_side",
                   "operation": "add", "operand": "3", "before": "7"}


def test_operation_not_inferred():
    assert detect_mistake((x**2 + 1, 8), (x + 3, 6), verifier_result="invalid") is None


def test_only_runs_after_invalid_verdict():
    assert detect_mistake((2*x, 8), (x, 8)) is None
    assert detect_mistake((2*x, 8), (x, 8), verifier_result="valid") is None
    assert detect_mistake((2*x, 8), (x, 8), verifier_result="unknown") is None


def test_status_dictionary_and_object_are_supported():
    class Verdict:
        status = "invalid"

    expected = {"label": "one_side_only", "expected": "4", "got": "8", "location": "right_side",
                "operation": "divide", "operand": "2", "before": "8"}
    assert detect_mistake((2*x, 8), (x, 8), verifier_result={"status": "invalid"}) == expected
    assert detect_mistake((2*x, 8), (x, 8), verifier_result=Verdict()) == expected


def test_one_side_only_does_not_label_when_expected_value_matches():
    assert detect_mistake((2*x, 4), (x, 2), verifier_result="invalid") is None


# ---- Phase 2 checks: a positive example, a near miss and an edge case each ----

from engine.parser import parse


def _check(previous, current):
    """Run the check the way the app does: on the parser's trees."""
    return detect_mistake(parse(previous), parse(current), verifier_result="invalid")


def _label(previous, current):
    return (_check(previous, current) or {}).get("label")


def test_sign_error():
    assert _check("x + 5 = 9", "x = 14") == {
        "label": "sign_error", "expected": "4", "got": "14", "location": "right_side",
        "operation": "subtract", "operand": "5", "before": "9"}
    assert _label("x + 5 = 9", "x = 5") == "arithmetic_error"   # near miss: wrong number, right sign
    assert _label("x - 6 = 2", "x = -4") == "sign_error"        # edge: negative constant


def test_wrong_inverse_op():
    assert _check("2x = 8", "x = 6")["label"] == "wrong_inverse_op"
    assert _label("3x = 12", "x = 3") == "arithmetic_error"     # near miss: 12 - 3 is 9, not 3
    assert _label("x + 2 = 8", "x = 4") == "wrong_inverse_op"   # edge: subtract on the left, divide on the right


def test_partial_distribution():
    got = _check("2(x + 3) = 10", "2x + 3 = 10")
    assert (got["label"], got["expected"], got["got"]) == ("partial_distribution", "2*x + 6", "2*x + 3")
    assert _label("2(x + 3) = 10", "3x + 9 = 10") is None       # near miss: a different wrong multiplier
    assert _label("2(x - 4) = 6", "2x - 4 = 6") == "partial_distribution"  # edge: subtraction inside


def test_partial_distribution_needs_the_students_brackets():
    # SymPy pairs have lost the brackets, so the structural check cannot run.
    assert detect_mistake((2*(x + 3), 10), (2*x + 3, 10), verifier_result="invalid") is None


def test_coefficient_error():
    got = _check("2x + 3x = 20", "6x = 20")
    assert (got["label"], got["expected"], got["got"]) == ("coefficient_error", "5*x", "6*x")
    assert _label("x + 3 = 10", "4x = 10") is None              # near miss: unlike terms, cases.csv M3_018
    assert _label("5x - 2x + 1 = 7", "2x + 1 = 7") == "coefficient_error"  # edge: subtraction, constant kept


def test_exponent_error():
    got = _check("(x + 1)^2 = 9", "x^2 + 1 = 9")
    assert (got["label"], got["expected"], got["got"]) == ("exponent_error", "x**2 + 2*x + 1", "x**2 + 1")
    assert _label("(x + 1)^2 = 9", "x^2 + 3x + 1 = 9") is None  # near miss: a different slip
    assert _label("(x - 2)^2 = 1", "x^2 - 4 = 1") == "exponent_error"  # edge: a difference


def test_divide_by_variable():
    got = _check("x^2 = x", "x = 1")
    assert (got["label"], got["expected"], got["got"], got["operand"]) == (
        "divide_by_variable", "{0, 1}", "{1}", "x")
    assert _label("x^2 = 4", "x = 2") == "lost_solution"        # near miss: no common factor of x
    assert _label("x^2 = 4x", "x = 4") == "divide_by_variable"  # edge: x times a number


def test_lost_and_extra_solutions():
    assert _check("x^2 = 4", "x = 2")["label"] == "lost_solution"
    assert _check("x = 2", "x^2 = 4")["label"] == "extra_solution"
    assert _label("x^2 = 4", "x = 3") is None                   # near miss: neither set contains the other


def test_rewrites_are_not_read_as_one_sided_steps():
    # 2x + 6 -> 2(x + 6) is a wrong factorisation, not "added 6 to the left" (cases.csv M3_020).
    assert _label("2x + 6 = 10", "2(x + 6) = 10") is None


def test_sign_slip_after_dividing_by_a_negative_is_not_called_arithmetic():
    assert _label("-3x = 12", "x = 4") is None                  # cases.csv M3_011
