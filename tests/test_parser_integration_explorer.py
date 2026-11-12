"""Integration: the real parser (engine/parser.py, Member 1) feeding the explorer.

Owner: Member 4. Every test goes through parse(text).to_dict() ->
build_explorer_tree(...), never a hand-built AST, except the fixture drift guard,
which compares the hand-built fixtures with the parser's output for the same source.
"""
import pytest

from engine.explore import ExplorerError, build_explorer_tree
from engine.parser import ParseError, parse
from tests.explorer_fixtures import ALL_FIXTURES


def explore(text):
    return build_explorer_tree(parse(text).to_dict())


def flat(node):
    yield node
    for c in node["children"]:
        yield from flat(c)


def by_id(root):
    return {n["id"]: n for n in flat(root)}


def strip(d):
    return {
        "type": d["type"],
        "value": d.get("value"),
        "span": list(d["span"]),
        "children": [strip(c) for c in d["children"]],
    }


# ---- fixtures cannot drift away from the parser ---------------------------------


@pytest.mark.parametrize("name", list(ALL_FIXTURES))
def test_fixture_equals_real_parser_output(name):
    source, ast = ALL_FIXTURES[name]
    real = parse(source).to_dict()
    assert strip(ast) == strip(real)
    assert build_explorer_tree(ast) == build_explorer_tree(real)


# ---- plumbing -------------------------------------------------------------------


def test_node_must_be_converted_with_to_dict():
    with pytest.raises(ExplorerError, match="node must be a dict"):
        build_explorer_tree(parse("x = 1"))


def test_extra_parser_keys_are_ignored_and_input_is_untouched():
    ast = parse("2x + 3 = 9").to_dict()
    assert "implicit" in ast and "typed" in ast
    before = repr(ast)
    root = build_explorer_tree(ast)
    assert repr(ast) == before
    assert set(root) == {
        "id", "type", "role", "value", "spoken_quick", "spoken_detailed",
        "spoken_context", "children",
    }


@pytest.mark.parametrize(
    "text",
    [
        "x = 5", "3x + 5 = 14", "x - 3 = 4", "-3x = 6", "-x = 4", "x/2 = 3",
        "(x + 1)/2 = 3", "2(x + 3) = 12", "(x + 1)(x - 2) = 0", "x^2 = 4",
        "2x^2 + 1 = 9", "x - -3 = 4", "-(x + 1) = 5", "3x/2 = 6", ".5x = 2",
        "2.5x + 1 = 6", "x = 3.14159", "3*x = 6", "2*(x + 1) = 6", "1/x = 4",
        "((x + 1)/2 + 3)/4 = 1", "2(x + 3)^2 - (x - 1)/4 = 5",
    ],
)
def test_every_parseable_input_explores_to_a_valid_tree(text):
    root = explore(text)
    ids = [n["id"] for n in flat(root)]
    assert len(ids) == len(set(ids)) and root["id"] == "n0"
    for n in flat(root):
        assert n["spoken_quick"] and n["spoken_detailed"] and n["spoken_context"]


def test_decimal_values_are_what_the_parser_produced():
    assert explore("x = 3.14159")["children"][1]["value"] == "3.1416"
    assert explore("2.5x = 5")["children"][0]["children"][0]["value"] == "2.5"
    with pytest.raises(ParseError):
        parse("5. + x = 7")  # the parser rejects what the explorer would tolerate


def test_implicit_and_explicit_multiplication_read_the_same():
    assert explore("3x = 6") == explore("3*x = 6")
    assert explore("2(x + 1) = 6") == explore("2*(x + 1) = 6")


# ---- negative coefficients: Mul(Neg(Number), Variable) --------------------------


def test_negative_coefficient_is_the_coefficient_of_x():
    nodes = by_id(explore("-3x = 6"))
    neg, x = nodes["n0.0.0"], nodes["n0.0.1"]
    assert (neg["type"], neg["role"], neg["value"]) == ("Neg", "coefficient", None)
    assert neg["spoken_quick"] == "Coefficient negative 3"
    assert neg["spoken_detailed"].startswith("Negative 3 is the coefficient of x.")
    assert "not a coefficient" not in neg["spoken_detailed"]
    assert "negative 3 times x" in neg["spoken_detailed"]
    assert "coefficient negative 3" in neg["spoken_context"]
    assert x["role"] == "variable" and "coefficient negative 3" in x["spoken_detailed"]
    inner = nodes["n0.0.0.0"]
    assert inner["role"] == "number"
    assert "number part of the coefficient negative 3" in inner["spoken_detailed"]
    assert "not a coefficient" not in inner["spoken_detailed"]


def test_negative_coefficient_matches_the_positive_one_in_structure():
    pos, neg = explore("3x = 6"), explore("-3x = 6")
    assert pos["children"][0]["children"][0]["role"] == "coefficient"
    assert neg["children"][0]["children"][0]["role"] == "coefficient"
    assert "left side, negative 3 times x," in neg["spoken_detailed"]
    assert "left side, 3x," in pos["spoken_detailed"]


def test_negative_coefficient_of_a_power_and_in_a_sum():
    nodes = by_id(explore("-3x^2 + 1 = 4"))
    neg = nodes["n0.0.0.0"]
    assert (neg["type"], neg["role"]) == ("Neg", "coefficient")
    assert "The exponent belongs to x alone, not to negative 3." in neg["spoken_detailed"]
    sub = by_id(explore("2 - 3x = 1"))["n0.0.1.0"]
    assert (sub["type"], sub["role"], sub["value"]) == ("Number", "coefficient", "3")


def test_negative_multiplier_of_a_group():
    nodes = by_id(explore("-2(x + 3) = 4"))
    neg = nodes["n0.0.0"]
    assert (neg["type"], neg["role"]) == ("Neg", "group_multiplier")
    assert neg["spoken_quick"] == "Multiplier negative 2"
    assert "multiplier of the group x plus 3" in neg["spoken_detailed"]
    assert nodes["n0.0.1"]["role"] == "group"


def test_other_negations_are_not_coefficients():
    # a negated number added/subtracted, a negated group and a negated power base
    assert by_id(explore("x - -3 = 4"))["n0.0.1"]["role"] == "operator"
    assert by_id(explore("-(x + 1) = 5"))["n0.0"]["role"] == "left_side"
    assert by_id(explore("x + -3 = 4"))["n0.0.1"]["role"] == "operator"
    neg_x = by_id(explore("-x = 4"))["n0.0"]
    assert neg_x["role"] == "left_side"


# ---- groups inside Div, Pow order -----------------------------------------------


def test_bracketed_numerator_stays_a_group_inside_the_fraction():
    nodes = by_id(explore("(x + 1)/2 = 3"))
    frac, num, den = nodes["n0.0"], nodes["n0.0.0"], nodes["n0.0.1"]
    assert (frac["type"], frac["role"]) == ("Div", "left_side")
    assert (num["type"], num["role"]) == ("Group", "group")
    assert (den["role"], den["value"]) == ("denominator", "2")
    assert nodes["n0.0.0.0"]["type"] == "Add"
    assert "the group x plus 1" in frac["spoken_detailed"]


def test_bracketed_denominator_and_nested_fractions():
    nodes = by_id(explore("(2x + 1)/(x - 3) = 4"))
    assert nodes["n0.0.0"]["role"] == "group" and nodes["n0.0.1"]["role"] == "group"
    nested = by_id(explore("((x + 1)/2 + 3)/4 = 1"))
    inner = nested["n0.0.0.0.0"]
    assert (inner["type"], inner["role"]) == ("Div", "fraction")
    assert nested["n0.0.1"]["role"] == "denominator"


def test_power_and_division_child_order():
    pw = by_id(explore("x^2 = 4"))
    assert (pw["n0.0.0"]["role"], pw["n0.0.1"]["role"]) == ("variable", "exponent")
    dv = by_id(explore("x/2 = 3"))
    assert dv["n0.0.1"]["role"] == "denominator"
    gp = by_id(explore("(x + 1)^2 = 9"))
    assert (gp["n0.0.0"]["role"], gp["n0.0.1"]["role"]) == ("group", "exponent")


def test_coefficient_and_multiplier_roles_from_real_parser():
    nodes = by_id(explore("2(x + 3) = 12"))
    assert nodes["n0.0.0"]["role"] == "group_multiplier"
    assert by_id(explore("3x/2 = 6"))["n0.0.0.0"]["role"] == "coefficient"
    assert by_id(explore("2x^2 = 8"))["n0.0.0"]["role"] == "coefficient"
    assert by_id(explore("x - 3 = 4"))["n0.0.1"]["role"] == "constant"
