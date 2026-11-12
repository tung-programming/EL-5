"""CLI integration tests using the real Phase 1 parser and algebra modules."""

import json

from cli import main


def _json_payload(stdout):
    text = stdout.lstrip()
    payload, end = json.JSONDecoder().raw_decode(text)
    return payload, text[end:].strip()


def test_valid_step_returns_verdict_mistake_and_explanations(capsys):
    assert main(["3x+5=14", "3x=9"]) == 0
    output = capsys.readouterr()
    payload, printed_explanation = _json_payload(output.out)

    assert payload["status"] == "valid"
    assert payload["mistake"] is None
    assert payload["inference"]["operation"] == "subtract"
    assert payload["inference"]["operand"] == "5"
    assert payload["explanation"]["concise"]
    assert payload["explanation"]["detailed"]
    assert printed_explanation == payload["explanation"]["concise"]


def test_invalid_arithmetic_step_has_grounded_mistake_data(capsys):
    assert main(["3x+5=14", "3x=10"]) == 0
    output = capsys.readouterr()
    payload, printed_explanation = _json_payload(output.out)

    assert payload["status"] == "invalid"
    assert payload["mistake"] == {
        "label": "arithmetic_error",
        "expected": "9",
        "got": "10",
        "location": "right_side",
    }
    assert payload["explanation"]["concise"]
    assert payload["explanation"]["detailed"]
    assert printed_explanation == payload["explanation"]["concise"]


def test_parser_error_is_clean_and_has_no_traceback(capsys):
    assert main(["3y+5=14", "3x=9"]) == 2
    output = capsys.readouterr()

    assert "Traceback" not in output.err
    assert "Only the letter x" in output.err
    assert output.out == ""


def test_missing_second_equation_is_clean_user_error(capsys):
    try:
        main(["x=2"])
    except SystemExit as exc:
        assert exc.code == 2
    output = capsys.readouterr()

    assert "Traceback" not in output.err
    assert "provide both" in output.err


def test_missing_explanation_adapter_reports_dependency_error(capsys, monkeypatch):
    from engine import explain

    monkeypatch.setattr(explain, "explain_step", None)

    assert main(["3x+5=14", "3x=9"]) == 2
    output = capsys.readouterr()

    assert "Traceback" not in output.err
    assert "dependency unavailable" in output.err
    assert "engine.explain.explain_step" in output.err
