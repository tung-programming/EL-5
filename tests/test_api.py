"""API end-to-end tests.

Owner: Member 5
See plan.md §13
"""

from fastapi.testclient import TestClient

import app as api
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


def test_parse_expression_passes_real_parser_ast_to_explorer(monkeypatch):
	calls = []
	original_parse = api.parse

	def tracked_parse(text):
		calls.append(text)
		return original_parse(text)

	monkeypatch.setattr(api, "parse", tracked_parse)
	response = client.post("/api/parse-expression", json={"expression": "2(x + 3) = 10"})

	assert response.status_code == 200
	assert calls == ["2(x + 3) = 10"]
	tree = response.json()
	left, right = tree["children"]
	assert tree["type"] == "Equation"
	assert left["type"] == "Mul"
	assert left["children"][0]["type"] == "Number"
	assert left["children"][0]["value"] == "2"
	group = left["children"][1]
	assert group["type"] == "Group"
	assert group["spoken_quick"] == "Group containing x plus three"
	addition = group["children"][0]
	assert addition["type"] == "Add"
	assert [(node["type"], node["value"]) for node in addition["children"]] == [
		("Variable", "x"),
		("Number", "3"),
	]
	assert (right["type"], right["value"]) == ("Number", "10")


def test_parse_expression_returns_a_new_tree_for_a_different_expression():
	first = client.post("/api/parse-expression", json={"expression": "2(x + 3) = 10"}).json()
	second = client.post("/api/parse-expression", json={"expression": "3x + 5 = 14"}).json()

	assert first["children"][0]["type"] == "Mul"
	assert second["children"][0]["type"] == "Add"
	assert second["children"][0]["children"][0]["type"] == "Mul"
	assert second["children"][0]["children"][1]["value"] == "5"
	assert second["children"][1]["value"] == "14"


def test_parse_expression_reports_parser_errors_as_bad_requests():
	response = client.post("/api/parse-expression", json={"expression": "2x + = 10"})

	assert response.status_code == 400
	assert "missing" in response.json()["detail"].lower()


def test_required_invalid_step_is_decided_by_verifier():
	response = client.post(
		"/api/check-step",
		json={"previous_equation": "3x + 5 = 14", "current_equation": "3x = 10"},
	)

	assert response.status_code == 200
	result = response.json()
	assert result["status"] == "invalid"
	assert result["mistake"] == {
		"label": "arithmetic_error",
		"expected": "9",
		"got": "10",
		"location": "right_side",
		"operation": "subtract",
		"operand": "5",
		"before": "14",
	}
