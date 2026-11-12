"""Positive and near-miss coverage for Phase 1 operation mistakes."""
import sympy as sp

from engine.mistakes import detect_mistake

x = sp.Symbol("x")


def test_one_side_only_division():
    got = detect_mistake((2*x, 8), (x, 8), verifier_result="invalid")
    assert got == {"label": "one_side_only", "expected": "4", "got": "8", "location": "right_side"}


def test_arithmetic_error_after_subtraction():
    got = detect_mistake((3*x + 5, 14), (3*x, 10), verifier_result="invalid")
    assert got == {"label": "arithmetic_error", "expected": "9", "got": "10", "location": "right_side"}


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
    assert got == {"label": "arithmetic_error", "expected": "10", "got": "11", "location": "right_side"}


def test_operation_not_inferred():
    assert detect_mistake((x**2 + 1, 8), (x + 3, 6), verifier_result="invalid") is None


def test_only_runs_after_invalid_verdict():
    assert detect_mistake((2*x, 8), (x, 8)) is None
    assert detect_mistake((2*x, 8), (x, 8), verifier_result="valid") is None
    assert detect_mistake((2*x, 8), (x, 8), verifier_result="unknown") is None


def test_status_dictionary_and_object_are_supported():
    class Verdict:
        status = "invalid"

    expected = {"label": "one_side_only", "expected": "4", "got": "8", "location": "right_side"}
    assert detect_mistake((2*x, 8), (x, 8), verifier_result={"status": "invalid"}) == expected
    assert detect_mistake((2*x, 8), (x, 8), verifier_result=Verdict()) == expected


def test_one_side_only_does_not_label_when_expected_value_matches():
    assert detect_mistake((2*x, 4), (x, 2), verifier_result="invalid") is None
