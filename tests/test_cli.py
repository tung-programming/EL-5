"""CLI input handling tests while parser/verifier integration is pending."""
from cli import main


def test_missing_second_equation_is_clean_user_error(capsys):
    try:
        main(["x = 2"])
    except SystemExit as exc:
        assert exc.code == 2
    out = capsys.readouterr()
    assert "Traceback" not in out.err
    assert "provide both" in out.err


def test_unimplemented_parser_is_reported_without_traceback(capsys):
    assert main(["x = 2", "x = 2"]) == 2
    out = capsys.readouterr()
    assert "Traceback" not in out.err
    assert "dependency unavailable" in out.err
