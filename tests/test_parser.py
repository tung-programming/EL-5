"""Parser tests.

Owner: Member 1
See plan.md §13 and docs/syntax.md

These tests expect engine/parser.py to provide:
  parse(text)    -> Equation tree, or raises ParseError
  ParseError     -> has .kind (str) and .position (int)
  bracketed(tree)-> fully bracketed string, used only for testing:
                      binary ops  "(a + b)", "(a - b)", "(a * b)", "(a / b)", "(a ^ b)"
                      implicit *  "(a · b)"
                      negative    "(-a)"
                      group       "[a]"      (the student's own brackets)
                      equation    "L = R"
"""
import pytest

parser = pytest.importorskip("engine.parser")
if not hasattr(parser, "parse"):
    pytest.skip("engine.parser.parse not written yet", allow_module_level=True)

parse, ParseError, bracketed = parser.parse, parser.ParseError, parser.bracketed


VALID = [
    # basic
    ("3x + 5 = 14",     "((3 · x) + 5) = 14"),
    ("3*x + 5 = 14",    "((3 * x) + 5) = 14"),
    ("3 x + 5 = 14",    "((3 · x) + 5) = 14"),
    ("2(x+3) = 10",     "(2 · [(x + 3)]) = 10"),
    ("(x+1)(x-1) = 0",  "([(x + 1)] · [(x - 1)]) = 0"),
    ("((x+1)) = 2",     "[[(x + 1)]] = 2"),
    ("x/2 = 3",         "(x / 2) = 3"),
    ("2.5x = 5",        "(2.5 · x) = 5"),
    (".5x = 1",         "(.5 · x) = 1"),
    ("8-3-2 = x",       "((8 - 3) - 2) = x"),
    # sign after an operator -> negative number
    ("2*-3 = -6",       "(2 * (-3)) = (-6)"),
    ("2 * -3 = -6",     "(2 * (-3)) = (-6)"),
    ("2/-3 = x",        "(2 / (-3)) = x"),
    ("2+-3 = x",        "(2 + (-3)) = x"),
    ("2--3 = x",        "(2 - (-3)) = x"),
    ("2 - -3 = x",      "(2 - (-3)) = x"),
    ("2*-3x = 6",       "((2 * (-3)) · x) = 6"),
    ("x*-(x+1) = 0",    "(x * (-[(x + 1)])) = 0"),
    ("-3x - -2x = 5",   "(((-3) · x) - ((-2) · x)) = 5"),
    # unary minus / plus
    ("x = -3",          "x = (-3)"),
    ("-x = 3",          "(-x) = 3"),
    ("-(x+1) = 2",      "(-[(x + 1)]) = 2"),
    ("3-(-2) = x",      "(3 - [(-2)]) = x"),
    ("2(-3) = x",       "(2 · [(-3)]) = x"),
    ("2(-x) = 4",       "(2 · [(-x)]) = 4"),
    ("-3x = 6",         "((-3) · x) = 6"),
    ("-2(x+1) = 4",     "((-2) · [(x + 1)]) = 4"),
    ("+3 = x",          "3 = x"),
    ("x = +3",          "x = 3"),
    ("2*+3 = x",        "(2 * 3) = x"),
    # powers and negatives
    ("x^2 = 4",         "(x ^ 2) = 4"),
    ("x**2 = 4",        "(x ^ 2) = 4"),
    ("-x^2 = -4",       "(-(x ^ 2)) = (-4)"),
    ("(-x)^2 = 4",      "([(-x)] ^ 2) = 4"),
    ("-3^2 = -9",       "(-(3 ^ 2)) = (-9)"),
    ("(-3)^2 = 9",      "([(-3)] ^ 2) = 9"),
    ("3x^2 = 12",       "(3 · (x ^ 2)) = 12"),
    ("-3x^2 = 6",       "((-3) · (x ^ 2)) = 6"),
    ("2^-3 = x",        "(2 ^ (-3)) = x"),
    ("2**-3 = x",       "(2 ^ (-3)) = x"),
    ("x^-1 = 2",        "(x ^ (-1)) = 2"),
    ("-x^-2 = 1",       "(-(x ^ (-2))) = 1"),
    ("2^3^2 = x",       "(2 ^ (3 ^ 2)) = x"),
    ("-2^-2 = x",       "(-(2 ^ (-2))) = x"),
    ("2*-3^2 = x",      "(2 * (-(3 ^ 2))) = x"),
    ("(x+1)^2 = 9",     "([(x + 1)] ^ 2) = 9"),
    ("x^2(x+1) = 0",    "((x ^ 2) · [(x + 1)]) = 0"),
    # ambiguous cases written unambiguously
    ("1/(2x) = 4",      "(1 / [(2 · x)]) = 4"),
    ("(1/2)x = 4",      "([(1 / 2)] · x) = 4"),
    ("1/2*x = 4",       "((1 / 2) * x) = 4"),
    ("2^(1+2) = 8",     "(2 ^ [(1 + 2)]) = 8"),
    ("(x^2)x = 8",      "([(x ^ 2)] · x) = 8"),
    # unicode symbols
    ("3x − 5 = 4", "((3 · x) - 5) = 4"),
    ("2×3 = x",    "(2 * 3) = x"),
    ("6÷2 = x",    "(6 / 2) = x"),
    ("x² = 4",     "(x ^ 2) = 4"),
]


INVALID = [
    ("",              "empty"),
    ("2^-x^2 = 1",    "variable_exponent"),
    ("2^(3x) = 8",    "variable_exponent"),
    ("x^2^-1 = 2",    "unsupported_exponent"),
    ("3y + 5 = 14",   "bad_symbol"),
    ("1.2.3 = x",     "bad_number"),
    ("5. = x",        "bad_number"),
    ("3x + 5",        "no_equals"),
    ("x = 2 = 3",     "many_equals"),
    ("3x + = 14",     "missing_operand"),
    ("2^ = x",        "missing_operand"),
    ("2^- = x",       "missing_operand"),
    ("2* = x",        "missing_operand"),
    ("- = 3",         "missing_operand"),
    ("--3 = x",       "double_sign"),
    ("2---3 = x",     "double_sign"),
    ("-+3 = x",       "double_sign"),
    ("x2 = 4",        "adjacent"),
    ("3 4 = x",       "adjacent"),
    ("2(x+3 = 10",    "unclosed"),
    ("x) = 3",        "extra_close"),
    ("(x+1)) = 3",    "extra_close"),
    ("() = 3",        "empty_brackets"),
    ("1/2x = 4",      "ambiguous_division"),
    ("2/3(x+1) = 4",  "ambiguous_division"),
    ("1/-2x = 4",     "ambiguous_division"),
    ("2^3x = 8",      "ambiguous_exponent"),
    ("x^2x = 8",      "ambiguous_exponent"),
    ("2^-3x = 1",     "ambiguous_exponent"),
]


@pytest.mark.parametrize("text, expected", VALID)
def test_valid(text, expected):
    assert bracketed(parse(text)) == expected


@pytest.mark.parametrize("text, kind", INVALID)
def test_invalid(text, kind):
    with pytest.raises(ParseError) as err:
        parse(text)
    assert err.value.kind == kind


# --------------------------------------------------------------------------- #
# More checks (Phase 1-2): contract JSON, spans, SymPy, every error message.
# --------------------------------------------------------------------------- #
import json

import sympy

from engine.parser import (ERROR_TEMPLATES, MAX_DECIMALS, MAX_DEPTH, MAX_EXPONENT, MAX_LENGTH, MAX_NUMBER, X,
                           notes, source_text, to_sympy, undefined_parts, walk)


def _expected_sympy(expected_side: str):
    """Turn the bracketed form from VALID into a SymPy value (test-only, trusted text)."""
    s = expected_side.replace("·", "*").replace("[", "(").replace("]", ")").replace("^", "**")
    return sympy.sympify(s, locals={"x": X})


@pytest.mark.parametrize("text, expected", VALID)
def test_to_sympy_matches_tree(text, expected):
    left, right = to_sympy(parse(text))
    exp_left, exp_right = expected.split(" = ")
    assert sympy.simplify(left - _expected_sympy(exp_left)) == 0
    assert sympy.simplify(right - _expected_sympy(exp_right)) == 0


# The examples in docs/contracts.md must come out exactly (read from the file, so they can't drift).
def _contract_examples() -> dict[str, dict]:
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "docs" / "contracts.md").read_text(encoding="utf-8")
    section = text[text.index("## OwnAST node"):text.index("## InferenceResult")]
    examples = {}
    for chunk in section.split("Example")[1:]:
        source = chunk[chunk.index("`") + 1:]
        source = source[:source.index("`")]
        body = chunk[chunk.index("```json") + 7:]
        examples[source] = json.loads(body[:body.index("```")])
    return examples


def test_contract_examples_json():
    examples = _contract_examples()
    assert set(examples) == {"3x + 5 = 14", "x = 3.14159"}
    for source, expected in examples.items():
        assert parse(source).to_dict() == expected, source


def test_contract_example_shapes():
    assert bracketed(parse("2(x + 3) = 10")) == "(2 · [(x + 3)]) = 10"
    assert bracketed(parse("x^2 - 4 = 0")) == "((x ^ 2) - 4) = 0"


def test_to_dict_is_plain_json():
    d = parse("-2(x^2 + 1)/3 = x").to_dict()
    assert json.loads(json.dumps(d)) == d
    stack = [d]
    while stack:
        node = stack.pop()
        assert set(node) == {"type", "value", "children", "span", "implicit", "typed"}
        assert node["value"] is None or isinstance(node["value"], str)
        assert isinstance(node["implicit"], bool)
        assert node["implicit"] is False or node["type"] == "Mul"
        assert node["typed"] is None or node["type"] == "Number"
        stack.extend(node["children"])


def test_spans_point_at_the_source():
    text = "2(x + 3) = -10"
    tree = parse(text)
    pieces = {(n.type, source_text(n, text)) for n in walk(tree)}
    assert ("Group", "(x + 3)") in pieces
    assert ("Add", "x + 3") in pieces
    assert ("Mul", "2(x + 3)") in pieces
    assert ("Neg", "-10") in pieces
    assert ("Number", "10") in pieces
    assert tree.span == (0, len(text))


def test_implicit_flag():
    assert parse("3x = 6").children[0].implicit is True
    assert parse("3*x = 6").children[0].implicit is False
    assert parse("2(x+1) = 6").children[0].implicit is True


def test_walk_order():
    types = [n.type for n in walk(parse("3x + 5 = 14"))]
    assert types == ["Equation", "Add", "Mul", "Number", "Variable", "Number", "Number"]


def test_to_sympy_does_not_simplify():
    left, _ = to_sympy(parse("2 + 3 = x"))
    assert isinstance(left, sympy.Add) and set(left.args) == {2, 3}


def test_to_sympy_is_exact():
    left, _ = to_sympy(parse("0.1 + 0.2 = x"))
    assert sympy.simplify(left) == sympy.Rational(3, 10)


def test_to_sympy_uses_shared_x():
    left, _ = to_sympy(parse("x = 1"))
    assert left is X
    left, _ = to_sympy(parse("X = 1"))
    assert left is X


def test_negative_number_is_a_plain_number():
    _, right = to_sympy(parse("x = -4"))
    assert right == -4 and right.is_Number


MORE_VALID = [
    ("X + 1 = 2",          "(x + 1) = 2"),
    ("x⁻¹ = 2",  "(x ^ (-1)) = 2"),       # x⁻¹
    ("x¹⁰ = 1",  "(x ^ 10) = 1"),         # x¹⁰
    ("2x² = 8",       "(2 · (x ^ 2)) = 8"),    # 2x²
    ("2·x = 4",       "(2 * x) = 4"),          # 2·x
    ("3x – 5 = 4",    "((3 · x) - 5) = 4"),    # en dash
    ("x x = 4",            "(x · x) = 4"),
    ("2(3) = 6",           "(2 · [3]) = 6"),
    ("2 = 2",              "2 = 2"),
    ("  3x=9  ",           "(3 · x) = 9"),
    ("2x/3 = 4",           "((2 · x) / 3) = 4"),
]


@pytest.mark.parametrize("text, expected", MORE_VALID)
def test_more_valid(text, expected):
    assert bracketed(parse(text)) == expected


# One input per error kind; every template must format without crashing.
ONE_PER_KIND = {
    "empty":              "   ",
    "too_long":           "x = " + "1+" * MAX_LENGTH + "1",
    "too_deep":           "(" * (MAX_DEPTH + 1) + "x" + ")" * (MAX_DEPTH + 1) + " = 1",
    "bad_symbol":         "3y + 5 = 14",
    "bad_number":         "5. = x",
    "no_equals":          "3x + 5",
    "many_equals":        "x == 3",
    "empty_side":         "= 5",
    "missing_operand":    "(x+) = 1",
    "double_sign":        "x = --3",
    "adjacent":           "(x+1)3 = 6",
    "unclosed":           "2(x+3 = 10",
    "extra_close":        "x) = 3",
    "empty_brackets":     "() = 3",
    "number_too_large":   "x = 1000001",
    "unsupported_exponent": "x^11 = 1",
    "variable_exponent":  "2^x = 8",
    "power_too_large":    "10^7 = x",
    "ambiguous_division": "1/2x = 4",
    "ambiguous_exponent": "2^3x = 8",
    "unexpected":         "*3 = x",
}


def test_every_kind_is_covered():
    assert set(ONE_PER_KIND) == set(ERROR_TEMPLATES)


@pytest.mark.parametrize("kind, text", ONE_PER_KIND.items())
def test_each_error_kind(kind, text):
    with pytest.raises(ParseError) as err:
        parse(text)
    e = err.value
    assert e.kind == kind
    assert e.message and "{" not in e.message           # template fully filled in
    assert e.to_dict() == {"kind": kind, "position": e.position, "message": e.message}
    assert 0 <= e.position <= len(text)


@pytest.mark.parametrize("text, kind", [
    ("x =", "empty_side"),
    ("x = 2 = 3", "many_equals"),
    ("(*3) = x", "unexpected"),
    ("x⁻ = 2", "bad_symbol"),        # superscript minus with no digits
    ("٣x = 1", "bad_symbol"),        # Arabic-Indic digit three
    ("2,5x = 1", "bad_symbol"),
    ("[x] = 1", "bad_symbol"),
])
def test_more_invalid(text, kind):
    with pytest.raises(ParseError) as err:
        parse(text)
    assert err.value.kind == kind


@pytest.mark.parametrize("text, message", [
    ("3x + = 14", 'Something is missing after "3x +".'),
    ("2(x+3 = 10", 'The bracket after "2" is never closed.'),
    ("(x+3 = 10", "The bracket at the start is never closed."),
    ("x) = 3", 'The closing bracket after "x" has no opening bracket.'),
    ("x = 1000001", "The number 1000001 is too big. Please use numbers up to 1,000,000."),
    ("x^11 = 1", 'I can only use whole-number powers from -10 to 10, and "x^11" doesn\'t fit that.'),
    ("2^x = 8", 'Powers with x in them, like in "2^x", aren\'t supported.'),
    ("1/2x = 4", 'I\'m not sure what "1/2x" means. Please add brackets: type 1/(2x) or (1/2)x.'),
    ("2/3(x+1) = 4", 'I\'m not sure what "2/3(x+1)" means. Please add brackets: type 2/(3(x+1)) or (2/3)(x+1).'),
    ("2^3x = 8", 'I\'m not sure what "2^3x" means. Please add brackets: type 2^(3x) or (2^3)x.'),
    ("3y = 6", 'I don\'t understand "y" after "3". Only the letter x can be used as the variable.'),
    ("x = 2,5", 'I don\'t understand "," after "x = 2". Write decimals with a point, like 2.5.'),
    ("= 5", "The left side of the equals sign is empty."),
    ("x = ", "The right side of the equals sign is empty."),
])
def test_messages(text, message):
    with pytest.raises(ParseError) as err:
        parse(text)
    assert err.value.message == message


def test_positions():
    for text, position in [("3y = 6", 1), ("3x + = 14", 3), ("x = 2 = 3", 6), ("2(x+3 = 10", 1)]:
        with pytest.raises(ParseError) as err:
            parse(text)
        assert err.value.position == position, text


def test_long_snippets_are_shortened():
    with pytest.raises(ParseError) as err:
        parse("x + x + x + x + x + x + x + x + = 1")
    assert "…" in err.value.message


def test_rejects_non_string():
    with pytest.raises(TypeError):
        parse(None)


@pytest.mark.parametrize("text", ["x^10 = 1", "2^-10 = x", "x^(2*5) = 1", "x^2^3 = 1", "(x+1)^0 = 1",
                                  "x^(4/2) = 4", "x^2.0 = 4", "2^-(1+1) = x"])
def test_exponent_limit_allows(text):
    parse(text)


@pytest.mark.parametrize("text, kind", [
    ("x^11 = 1", "unsupported_exponent"),
    ("2^-11 = x", "unsupported_exponent"),
    ("9^9^9 = x", "power_too_large"),          # inner 9^9 is already too big
    ("x^(10*11) = 1", "unsupported_exponent"),
    ("x^0.5 = 3", "unsupported_exponent"),
    ("x^(1/2) = 3", "unsupported_exponent"),
    ("63^-55^-8 = 1", "unsupported_exponent"),
    ("2^x = 8", "variable_exponent"),
    ("x^x = 1", "variable_exponent"),
    ("2^(x-x) = 1", "variable_exponent"),
])
def test_exponent_limit_rejects(text, kind):
    with pytest.raises(ParseError) as err:
        parse(text)
    assert err.value.kind == kind


# ---- number limits and rounding ------------------------------------------- #
@pytest.mark.parametrize("text", ["x = 1000000", "x = 999999.9999", "x = 0.0001", "x = 1000000.00001"])
def test_number_limit_allows(text):
    parse(text)


@pytest.mark.parametrize("text", ["x = 1000001", "x = 1000000.0001", "99999999x = 1"])
def test_number_limit_rejects(text):
    with pytest.raises(ParseError) as err:
        parse(text)
    assert err.value.kind == "number_too_large"


@pytest.mark.parametrize("typed, value", [
    ("3.14159", "3.1416"),
    ("2.99999", "3"),
    ("0.123456", "0.1235"),
    ("1.00005", "1.0001"),      # 5 rounds up (school rounding, not banker's)
    ("1.00004", "1"),
    ("0.00004", "0"),
    (".123456", "0.1235"),
])
def test_rounding_to_four_places(typed, value):
    text = f"x = {typed}"
    tree = parse(text)
    number = tree.children[1]
    assert number.value == value
    assert number.typed == typed
    assert to_sympy(number) == sympy.Rational(value)
    assert notes(tree, text) == [f"I rounded {typed} to {value}, because I use up to {MAX_DECIMALS} decimal places."]


@pytest.mark.parametrize("typed", ["3", "2.5", "3.1416", ".5", "007", "2.5000"])
def test_four_places_or_fewer_are_kept_as_typed(typed):
    number = parse(f"x = {typed}").children[1]
    assert number.value == typed and number.typed is None


def test_rounded_number_keeps_its_span():
    text = "x + 3.14159 = 5"
    number = parse(text).children[0].children[1]
    assert source_text(number, text) == "3.14159"


# ---- division by zero is undefined, not an error -------------------------- #
@pytest.mark.parametrize("text, part", [
    ("x/0 = 1", "x/0"),
    ("x = 5/(0)", "5/(0)"),
    ("x = 5/-0.0", "5/-0.0"),
    ("x/(2-2) = 1", "x/(2-2)"),
    ("x/(x-x) = 1", "x/(x-x)"),
    ("(1-1)^-2 = x", "(1-1)^-2"),
    ("0^-1 = x", "0^-1"),
])
def test_division_by_zero_is_undefined(text, part):
    tree = parse(text)
    assert [source_text(n, text) for n in undefined_parts(tree)] == [part]
    assert notes(tree, text) == [f"{part} divides by zero, which is undefined."]
    left, right = to_sympy(tree, evaluate=True)
    assert sympy.nan in (left, right)


def test_division_by_zero_makes_the_whole_side_undefined():
    left, right = to_sympy(parse("3x + 1/0 = 4"), evaluate=True)
    assert left is sympy.nan and right == 4


def test_nonzero_divisor_is_fine():
    text = "x/(x-1) = 1"
    assert undefined_parts(parse(text)) == [] and notes(parse(text), text) == []


def test_limits_are_class_1_to_5_sized():
    assert (MAX_NUMBER, MAX_DECIMALS, MAX_EXPONENT) == (1_000_000, 4, 10)


@pytest.mark.parametrize("text, expected", VALID)
def test_evaluated_sympy_matches(text, expected):
    left, right = to_sympy(parse(text), evaluate=True)
    exp_left, exp_right = expected.split(" = ")
    assert sympy.simplify(left - _expected_sympy(exp_left)) == 0
    assert sympy.simplify(right - _expected_sympy(exp_right)) == 0


def test_evaluated_form_is_normal_sympy():
    left, right = to_sympy(parse("2 + 3 = 2(x + 1)"), evaluate=True)
    assert left == 5
    assert right == 2 * X + 2 or sympy.expand(right) == 2 * X + 2


def test_evaluated_form_survives_simplify():
    # This input made SymPy's simplify() crash on the unevaluated form (found by fuzzing).
    text = "-((8x^2)/(((x) - (0)))) = ((((2.5)*(15))^0)*(19))^3"
    left, right = to_sympy(parse(text), evaluate=True)
    assert sympy.simplify(left + 8 * X) == 0
    assert right == 19 ** 3


@pytest.mark.parametrize("text", ["2^10 = x", "1000^2 = x", "(x^2)^5 = 1", "((x+1)^5)^2 = 1", "x^10 = 1",
                                  "(1/2)^10 = x", "(-10)^6 = x", "0^5 = x"])
def test_power_result_allows(text):
    parse(text)


@pytest.mark.parametrize("text", ["10^7 = x", "9^10 = x", "((9^10)^10)^10 = x", "(x^2)^6 = 1",
                                  "((x+1)^5)^3 = 1", "(0.001)^-3 = x", "(((x^2)^2)^2)^2 = 1"])
def test_power_result_rejects(text):
    with pytest.raises(ParseError) as err:
        parse(text)
    assert err.value.kind == "power_too_large"


def test_example_trees_file_is_up_to_date():
    # If this fails, run:  python -m engine.examples
    from engine.examples import OUTPUT, render
    assert OUTPUT.read_text(encoding="utf-8") == render()
