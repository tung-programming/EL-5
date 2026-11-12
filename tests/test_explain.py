"""Phase 1 explanation tests; these do not perform verification."""

from engine.explain import build_explanation
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
    assert result == {"concise": expected, "detailed": expected}


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
