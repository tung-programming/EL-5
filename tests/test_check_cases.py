"""Phase 2 exit check (plan.md §12): every row of tests/cases.csv passes end to end.

Each row goes through the real API, so this covers the parser, verifier,
inference, mistake checks and explanations together. A row passes when the
status and the mistake label match, and the explanation is not empty.

Owner: Member 3
"""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app

CASES = list(csv.DictReader(Path(__file__).with_name("cases.csv").open(encoding="utf-8", newline="")))
client = TestClient(app)


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_case_passes_end_to_end(case):
    response = client.post(
        "/api/check-step",
        json={"previous_equation": case["previous_step"], "current_equation": case["current_step"]},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == case["expected_status"], case["expected_reason"]
    label = (result["mistake"] or {}).get("label") or ""
    assert label == case["expected_mistake"], result["explanation"]["concise"]
    assert result["explanation"]["concise"].strip()
    assert result["explanation"]["detailed"].startswith(result["explanation"]["concise"])


def test_named_mistakes_explain_what_went_wrong():
    """A named mistake never falls back to the generic "different solution sets" text."""
    for case in CASES:
        if not case["expected_mistake"]:
            continue
        result = client.post(
            "/api/check-step",
            json={"previous_equation": case["previous_step"], "current_equation": case["current_step"]},
        ).json()
        assert "different real solution sets" not in result["explanation"]["concise"], case["case_id"]
