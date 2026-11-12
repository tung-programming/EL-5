"""API end-to-end tests.

Owner: Member 5
See plan.md §13
"""

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health_endpoint_reports_ok():
	response = client.get("/api/health")

	assert response.status_code == 200
	payload = response.json()
	assert payload["status"] == "ok"
	assert payload["service"] == "algebra-step-checker"


def test_rules_endpoint_lists_supported_contracts():
	response = client.get("/api/rules")

	assert response.status_code == 200
	payload = response.json()
	assert "operations" in payload
	assert "mistake_labels" in payload
	assert "subtract" in payload["operations"]


def test_check_step_valid_case_uses_verifier_and_inference():
	response = client.post(
		"/api/check-step",
		json={"previous_equation": "3x + 5 = 14", "current_equation": "3x = 9"},
	)

	assert response.status_code == 200
	payload = response.json()
	assert payload["status"] == "valid"
	assert payload["mistake"] is None
	assert payload["inference"]["operation"] == "subtract"
	assert payload["explanation"]["concise"].startswith("Correct")


def test_check_step_invalid_case_reports_mistake_evidence():
	response = client.post(
		"/api/check-step",
		json={"previous_equation": "x + 3 = 7", "current_equation": "x = 5"},
	)

	assert response.status_code == 200
	payload = response.json()
	assert payload["status"] == "invalid"
	assert payload["mistake"] is not None
	assert payload["explanation"]["concise"].startswith("This step is incorrect")


def test_parse_expression_returns_explorer_tree_for_equation():
	response = client.post(
		"/api/parse-expression",
		json={"expression": "2(x + 3) = 12"},
	)

	assert response.status_code == 200
	payload = response.json()
	assert payload["type"] == "Equation"
	assert payload["children"]
	assert payload["spoken_quick"]
