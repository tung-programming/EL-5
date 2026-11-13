"""Phase 1 explanation tests; these do not perform verification."""

from engine.explain import build_explanation, explain_step
from engine.verifier import VerificationResult


def test_valid_explanation_without_inference():
    result = build_explanation("valid")

    expected = "Correct. Both equations have the same real solution set."
    assert result == {"concise": expected, "detailed": expected}


def test_valid_explanation_uses_supplied_verified_inference():
    result = build_explanation(
        "valid",
        verification={"status": "valid"},
        inference={
            "operation": "subtract",
            "operand": 5,
            "applied_to": "both sides",
        },
    )

    expected = "Correct. You subtracted 5 from both sides."
    assert result["concise"] == expected
    # Phase 2: the detailed level adds why the step works.
    assert result["detailed"].startswith(expected + " ")
    assert "balanced" in result["detailed"]


def test_invalid_explanation_without_mistake_classification():
    result = build_explanation("invalid")

    expected = (
        "This step is incorrect because the two equations have different real "
        "solution sets."
    )
    assert result == {"concise": expected, "detailed": expected}
    assert "error" not in result["concise"]


def test_invalid_explanation_uses_only_verified_solution_values():
    verification = VerificationResult(
        status="invalid",
        previous_solutions="{3}",
        current_solutions="{10/3}",
        reason="different exact sets",
    )

    result = build_explanation("invalid", verification=verification)

    assert "previous equation has solution x = 3" in result["concise"]
    assert "current equation has solution x = 10/3" in result["concise"]
    assert "FiniteSet" not in result["concise"]


def test_unverified_solution_values_are_not_included():
    result = build_explanation(
        "invalid",
        verification={"previous_solutions": "{3}", "current_solutions": "{7}"},
    )

    assert "x = 3" not in result["concise"]
    assert "x = 7" not in result["concise"]


def test_unknown_fallback_is_safe():
    result = build_explanation("unknown")

    expected = "I cannot determine whether this step is correct."
    assert result == {"concise": expected, "detailed": expected}


def test_missing_optional_fields_use_safe_fallbacks():
    valid = build_explanation("valid", inference={})
    invalid = build_explanation("invalid", verification={"status": "invalid"})

    assert valid["concise"] == "Correct. Both equations have the same real solution set."
    assert "different real solution sets" in invalid["concise"]


def test_inference_inconsistent_with_verification_is_not_used():
    result = build_explanation(
        "valid",
        verification={"status": "invalid"},
        inference={
            "operation": "subtract",
            "operand": 5,
            "applied_to": "both sides",
        },
    )

    assert result["concise"] == "Correct. Both equations have the same real solution set."
    assert "subtracted" not in result["concise"]


def test_unsupported_operation_is_not_invented():
    result = build_explanation(
        "valid",
        inference={
            "operation": "complete_the_square",
            "operand": "x",
            "applied_to": "both sides",
        },
    )

    assert result["concise"] == "Correct. Both equations have the same real solution set."
    assert "square" not in result["concise"]


def test_zero_multiplier_or_divisor_is_not_described_as_valid():
    for operation in ("multiply", "divide"):
        result = build_explanation(
            "valid",
            inference={
                "operation": operation,
                "operand": 0,
                "applied_to": "both sides",
            },
        )

        assert result["concise"] == "Correct. Both equations have the same real solution set."
        assert "by 0" not in result["concise"]


def test_invalid_mistake_data_does_not_trigger_phase_two_template():
    result = build_explanation(
        "invalid",
        mistake={"label": "lost_solution"},
    )

    assert "lost solution" not in result["concise"]
    assert "different real solution sets" in result["concise"]


def test_shared_response_has_concise_and_detailed_strings():
    result = build_explanation("unknown")

    assert list(result) == ["concise", "detailed"]
    assert isinstance(result["concise"], str)
    assert isinstance(result["detailed"], str)
    assert result["detailed"] == result["concise"]


def test_explain_step_adapts_valid_verification_result():
    verification = VerificationResult(
        status="valid",
        previous_solutions="{3}",
        current_solutions="{3}",
        reason="same set",
    )

    result = explain_step(verification)

    assert result["concise"] == "Correct. Both equations have the same real solution set."


def test_explain_step_adapts_invalid_verification_result():
    verification = VerificationResult(
        status="invalid",
        previous_solutions="{3}",
        current_solutions="{10/3}",
        reason="different sets",
    )

    result = explain_step(verification)

    assert "previous equation has solution x = 3" in result["concise"]
    assert "current equation has solution x = 10/3" in result["concise"]


def test_explain_step_adapts_unknown_verification_result():
    verification = VerificationResult(
        status="unknown",
        previous_solutions="unknown",
        current_solutions="unknown",
        reason="out of scope",
    )

    assert explain_step(verification) == build_explanation("unknown")


def test_explain_step_accepts_status_dictionary():
    assert explain_step({"status": "valid"}) == build_explanation("valid")
    assert explain_step({"status": "invalid"}) == build_explanation("invalid")


def test_explain_step_handles_missing_or_unsupported_verification():
    assert explain_step(None) == build_explanation("unknown")
    assert explain_step({"status": "not-a-status"}) == build_explanation("unknown")


def test_explain_step_accepts_inference_none():
    verification = VerificationResult(
        status="valid",
        previous_solutions="{3}",
        current_solutions="{3}",
        reason="same set",
    )

    assert explain_step(verification, inference=None) == build_explanation(
        "valid", verification=verification
    )


def test_explain_step_matches_build_explanation_for_equivalent_inputs():
    verification = {"status": "valid"}
    inference = {
        "operation": "subtract",
        "operand": "5",
        "applied_to": "both_sides",
    }

    adapted = explain_step(verification, inference, mistake=None)
    direct = build_explanation("valid", verification, inference, mistake=None)

    assert adapted == direct


# ---- Phase 2 templates ----------------------------------------------------------

from engine.parser import parse
from engine.verifier import verify_step
from engine.infer import infer_operation
from engine.mistakes import detect_mistake


def _explain(previous, current):
    old, new = parse(previous), parse(current)
    verification = verify_step(old, new)
    inference = infer_operation(old, new)
    mistake = detect_mistake(old, new, inference, verification)
    return explain_step(verification, inference, mistake)


def test_arithmetic_error_names_the_operation_and_numbers():
    result = _explain("3x = 9", "x = 2")
    assert result["concise"] == ("This step is incorrect. You divided both sides by 3, which is "
                                 "the right idea, but 9 divided by 3 is 3, not 2.")
    assert "previous equation has solution x = 3" in result["detailed"]


def test_one_side_only_says_which_side_was_missed():
    concise = _explain("3x + 5 = 14", "3x = 14")["concise"]
    assert "subtracted 5 from the left side but not the right side" in concise
    assert "14 minus 5, which is 9, not 14" in concise


def test_sign_error_points_at_the_sign():
    result = _explain("x + 5 = 9", "x = 14")
    assert "Check the sign" in result["concise"]
    assert "added 5 on the right side instead" in result["detailed"]


def test_wrong_inverse_op_names_both_operations():
    concise = _explain("2x = 8", "x = 6")["concise"]
    assert "divided the left side by 2" in concise
    assert "subtracted 2 instead" in concise


def test_structural_mistakes_show_the_correct_form():
    assert "should be 2x + 6, not 2x + 3" in _explain("2(x + 3) = 10", "2x + 3 = 10")["concise"]
    assert "should be 5x, not 6x" in _explain("2x + 3x = 20", "6x = 20")["concise"]
    assert "x squared + 2x + 1, not x squared + 1" in _explain("(x + 1)^2 = 9", "x^2 + 1 = 9")["concise"]


def test_solution_mistakes_name_the_solution():
    assert "divided both sides by x, which could be zero, so the step loses x = 0" in \
        _explain("x^2 = x", "x = 1")["concise"]
    assert "It loses a solution" in _explain("x^2 = 4", "x = 2")["concise"]
    assert "It adds a solution" in _explain("x = 2", "x^2 = 4")["concise"]


def test_valid_rewrites_swaps_and_combined_steps():
    assert _explain("2(x + 3) = 10", "2x + 6 = 10")["concise"] == \
        "Correct. You expanded the brackets on the left side."
    assert _explain("x + 2 = 5", "5 = x + 2")["concise"] == "Correct. You swapped the two sides."
    assert _explain("5x + 2 = 3x + 8", "2x = 6")["concise"] == "Correct. You subtracted 3x + 2 from both sides."
    assert _explain("x + 2 = 5", "2x = 6")["concise"] == "Correct. You did the same steps to both sides."


def test_zero_divisor_warning_is_in_the_detailed_text_only():
    result = _explain("1/x = 2", "1 = 2x")
    assert "cannot be 0" not in result["concise"]
    assert "Note: x cannot be 0 here, because the equation divides by x." in result["detailed"]


def test_mistake_without_operation_evidence_still_gives_the_numbers():
    result = build_explanation("invalid", mistake={
        "label": "arithmetic_error", "expected": "9", "got": "10", "location": "right_side"})
    assert result["concise"] == ("This step is incorrect. Check your arithmetic. "
                                 "The right side should be 9, not 10.")
