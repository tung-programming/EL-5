"""Explorer role and spoken-text tests.

Owner: Member 4
See plan.md §13

Part 1 checks the mock OwnAST fixtures (tests/explorer_fixtures.py).
Part 2 tests engine/explore.py (Phase 1) against those mocks. Both parts use
the AST and ExplorerNode shapes of docs/contracts.md (the authoritative shared
contract): Number.value is a string, there is no Fraction type (Div is the
fraction node) and the ExplorerNode has no span. The last part of this file
tests that contract directly. engine/parser.py does not exist yet.
"""

import copy
import math
import random
import re
from pathlib import Path

import pytest

from engine.explore import MAX_DEPTH, ExplorerError, build_explorer_tree
from tests.explorer_fixtures import (
    ALL_FIXTURES,
    FIXTURE_NODE_TYPES,
    FIXTURES,
    REVIEW_FIXTURES,
)


def walk(node):
    yield node
    for child in node["children"]:
        yield from walk(child)


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_nodes_follow_ownast_shape(name):
    _, ast = FIXTURES[name]
    for node in walk(ast):
        assert set(node) <= {"type", "value", "children", "span"}
        assert {"type", "children", "span"} <= set(node)
        assert node["type"] in FIXTURE_NODE_TYPES
        assert isinstance(node["children"], list)
        start, end = node["span"]
        assert isinstance(start, int) and isinstance(end, int)
        assert start < end


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_value_only_on_leaves(name):
    _, ast = FIXTURES[name]
    for node in walk(ast):
        if node["type"] in {"Number", "Variable"}:
            assert "value" in node and node["children"] == []
        else:
            assert "value" not in node and node["children"]


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_spans_are_inside_source_and_nested(name):
    source, ast = FIXTURES[name]
    assert ast["span"] == [0, len(source)]
    for node in walk(ast):
        start, end = node["span"]
        assert 0 <= start < end <= len(source)
        for child in node["children"]:
            assert start <= child["span"][0] and child["span"][1] <= end


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_children_are_in_source_order(name):
    _, ast = FIXTURES[name]
    for node in walk(ast):
        starts = [c["span"][0] for c in node["children"]]
        assert starts == sorted(starts)


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_arity(name):
    _, ast = FIXTURES[name]
    assert ast["type"] == "Equation" and len(ast["children"]) == 2
    for node in walk(ast):
        if node["type"] in {"Add", "Mul"}:
            assert len(node["children"]) == 2


def test_fixture_3x_plus_5_eq_14_spans_slice_to_expected_text():
    # (the AST fixture itself, not the explorer output: spans are input-only)
    source, ast = FIXTURES["3x+5=14"]
    left, right = ast["children"]
    mul, five = left["children"]
    three, x = mul["children"]

    def text(n):
        return source[n["span"][0] : n["span"][1]]

    assert text(left) == "3x + 5"
    assert text(mul) == "3x"
    assert (text(three), three["value"]) == ("3", "3")
    assert (text(x), x["value"]) == ("x", "x")
    assert (text(five), five["value"]) == ("5", "5")
    assert (text(right), right["value"]) == ("14", "14")


def test_fixture_2x_plus_3_eq_9_spans_slice_to_expected_text():
    source, ast = FIXTURES["2x+3=9"]
    left, right = ast["children"]
    mul, three = left["children"]

    def text(n):
        return source[n["span"][0] : n["span"][1]]

    assert text(left) == "2x + 3"
    assert text(mul) == "2x"
    assert text(mul["children"][0]) == "2"
    assert text(three) == "3"
    assert text(right) == "9"


# ===========================================================================
# Part 2: engine/explore.py (Phase 1)
# ===========================================================================

# The ExplorerNode schema of docs/contracts.md. `span` is NOT part of it.
EXPLORER_FIELDS = {
    "id", "type", "role", "value", "spoken_quick", "spoken_detailed",
    "spoken_context", "children",
}


def tree(name):
    return build_explorer_tree(FIXTURES[name][1])


def flat(node):
    yield node
    for c in node["children"]:
        yield from flat(c)


def Ng(inner):
    """Neg(inner): a leading minus is a Neg node, never a negative Number."""
    return op("Neg", [inner], max(inner["span"][0] - 1, 0), inner["span"][1])


def leaf(type_, start, end, value=None):
    """A leaf. A Number's `value` is its source spelling, a string (docs/contracts.md);
    a plain int or float is spelled with str() for brevity. Anything else (bool,
    None, nan...) is passed through untouched so malformed-input tests still work."""
    n = {"type": type_, "children": [], "span": [start, end]}
    if (
        type_ == "Number"
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (isinstance(value, int) or math.isfinite(value))
    ):
        value = str(value)
    if value is not None:
        n["value"] = value
    return n


def op(type_, children, start, end):
    return {"type": type_, "children": children, "span": [start, end]}


def equation(left, right, end=20):
    return op("Equation", [left, right], 0, end)


# ---- structure ------------------------------------------------------------


def test_3x_plus_5_eq_14_structure_and_roles():
    root = tree("3x+5=14")
    assert (root["role"], root["type"]) == ("equation", "Equation")
    left, right = root["children"]
    assert (left["role"], left["type"]) == ("left_side", "Add")
    assert (right["role"], right["type"]) == ("right_side", "Number")
    mul, five = left["children"]
    assert (mul["role"], mul["type"]) == ("operator", "Mul")
    assert (five["role"], five["type"]) == ("constant", "Number")
    three, x = mul["children"]
    assert (three["role"], three["value"]) == ("coefficient", "3")
    assert (x["role"], x["value"]) == ("variable", "x")


def test_2x_plus_3_eq_9_structure_and_roles():
    root = tree("2x+3=9")
    left, right = root["children"]
    mul, three = left["children"]
    two, x = mul["children"]
    assert [n["role"] for n in (root, left, right)] == ["equation", "left_side", "right_side"]
    assert (two["role"], two["value"]) == ("coefficient", "2")
    assert x["role"] == "variable"
    assert (three["role"], three["value"]) == ("constant", "3")
    assert right["value"] == "9"


@pytest.mark.parametrize("name", FIXTURES)
def test_every_node_has_exactly_the_explorer_fields(name):
    for n in flat(tree(name)):
        assert set(n) == EXPLORER_FIELDS
        for key in ("spoken_quick", "spoken_detailed", "spoken_context"):
            assert isinstance(n[key], str) and n[key]


@pytest.mark.parametrize("name", FIXTURES)
def test_same_nodes_same_order_as_ast(name):
    def pairs(ast, ex):
        assert ex["type"] == ast["type"]
        assert len(ex["children"]) == len(ast["children"])
        for a, e in zip(ast["children"], ex["children"]):
            pairs(a, e)
    ast = FIXTURES[name][1]
    pairs(ast, build_explorer_tree(ast))


@pytest.mark.parametrize("name", FIXTURES)
def test_span_is_validated_but_not_part_of_the_public_output(name):
    # docs/contracts.md's ExplorerNode has no span field
    ast = FIXTURES[name][1]
    for n in flat(build_explorer_tree(ast)):
        assert "span" not in n


@pytest.mark.parametrize("name", FIXTURES)
def test_ids_unique_and_stable(name):
    ids = [n["id"] for n in flat(tree(name))]
    assert len(ids) == len(set(ids))
    assert ids == [n["id"] for n in flat(tree(name))]
    assert tree(name)["id"] == "n0"


def test_ids_follow_child_path():
    root = tree("3x+5=14")
    assert [c["id"] for c in root["children"]] == ["n0.0", "n0.1"]
    assert [c["id"] for c in root["children"][0]["children"]] == ["n0.0.0", "n0.0.1"]


def test_input_is_not_modified():
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    before = copy.deepcopy(ast)
    build_explorer_tree(ast)
    assert ast == before


# ---- roles in other shapes ---------------------------------------------------


def test_standalone_number_is_not_a_coefficient():
    # 7 = 7 ; both sides are plain numbers
    root = build_explorer_tree(equation(leaf("Number", 0, 1, 7), leaf("Number", 4, 5, 7), 5))
    assert [c["role"] for c in root["children"]] == ["left_side", "right_side"]
    assert all(c["role"] != "coefficient" for c in flat(root))


def test_coefficient_when_variable_comes_first():
    # x*3 = 6  -> 3 multiplies x, so it is a coefficient
    mul = op("Mul", [leaf("Variable", 0, 1, "x"), leaf("Number", 2, 3, 3)], 0, 3)
    root = build_explorer_tree(equation(mul, leaf("Number", 6, 7, 6), 7))
    assert root["children"][0]["children"][1]["role"] == "coefficient"


def test_number_times_number_is_not_a_coefficient_or_constant():
    # 2*3 + x = 7
    mul = op("Mul", [leaf("Number", 0, 1, 2), leaf("Number", 2, 3, 3)], 0, 3)
    add = op("Add", [mul, leaf("Variable", 6, 7, "x")], 0, 7)
    root = build_explorer_tree(equation(add, leaf("Number", 10, 11, 7), 11))
    two, three = root["children"][0]["children"][0]["children"]
    assert two["role"] == three["role"] == "number"


def test_exponent_is_not_called_constant_or_coefficient():
    # x^2 = 4
    pow_ = op("Pow", [leaf("Variable", 0, 1, "x"), leaf("Number", 2, 3, 2)], 0, 3)
    root = build_explorer_tree(equation(pow_, leaf("Number", 6, 7, 4), 7))
    left = root["children"][0]
    assert (left["role"], left["type"]) == ("left_side", "Pow")
    # Phase 2: the exponent has its own role, still not constant/coefficient
    assert left["children"][1]["role"] == "exponent"
    assert left["children"][1]["role"] not in ("constant", "coefficient", "number")
    assert left["children"][0]["role"] == "variable"


def test_subtraction_and_division_are_operators():
    # 3x - 5 = 4/2   (left side is Sub, right side is Div)
    mul = op("Mul", [leaf("Number", 0, 1, 3), leaf("Variable", 1, 2, "x")], 0, 2)
    sub = op("Sub", [mul, leaf("Number", 5, 6, 5)], 0, 6)
    div = op("Div", [leaf("Number", 9, 10, 4), leaf("Number", 11, 12, 2)], 9, 12)
    root = build_explorer_tree(equation(sub, div, 12))
    left, right = root["children"]
    assert left["children"][1]["role"] == "constant"
    assert right["role"] == "right_side" and right["type"] == "Div"
    # Div is the fraction node: its parts are numerator and denominator
    assert right["children"][0]["role"] == "numerator" and right["children"][1]["role"] == "denominator"


def test_nested_operations():
    # 3x + 2x + 5 = 14  ->  Add(Add(Mul, Mul), 5)
    m1 = op("Mul", [leaf("Number", 0, 1, 3), leaf("Variable", 1, 2, "x")], 0, 2)
    m2 = op("Mul", [leaf("Number", 5, 6, 2), leaf("Variable", 6, 7, "x")], 5, 7)
    inner = op("Add", [m1, m2], 0, 7)
    outer = op("Add", [inner, leaf("Number", 10, 11, 5)], 0, 11)
    root = build_explorer_tree(equation(outer, leaf("Number", 14, 16, 14), 16))
    left = root["children"][0]
    inner_ex, five = left["children"]
    assert inner_ex["role"] == "operator" and five["role"] == "constant"
    assert [m["children"][0]["role"] for m in inner_ex["children"]] == ["coefficient"] * 2
    ids = [n["id"] for n in flat(root)]
    assert len(ids) == len(set(ids))


def test_negative_number_via_neg_node():
    # 3x + -5 = 1 : the 5 inside Neg is still a term of the sum
    neg = op("Neg", [leaf("Number", 6, 7, 5)], 5, 7)
    mul = op("Mul", [leaf("Number", 0, 1, 3), leaf("Variable", 1, 2, "x")], 0, 2)
    root = build_explorer_tree(
        equation(op("Add", [mul, neg], 0, 7), leaf("Number", 10, 11, 1), 11)
    )
    neg_ex = root["children"][0]["children"][1]
    assert (neg_ex["role"], neg_ex["spoken_quick"]) == ("operator", "Negation")
    assert neg_ex["children"][0]["role"] == "constant"


def test_neg_of_coefficient_product():
    # -3x = 6 : Neg(Mul(3, x)); 3 still multiplies x
    mul = op("Mul", [leaf("Number", 1, 2, 3), leaf("Variable", 2, 3, "x")], 1, 3)
    neg = op("Neg", [mul], 0, 3)
    root = build_explorer_tree(equation(neg, leaf("Number", 6, 7, 6), 7))
    left = root["children"][0]
    assert left["role"] == "left_side"
    assert left["children"][0]["children"][0]["role"] == "coefficient"


@pytest.mark.parametrize("spelling", ["-3", "-0.5", "+3", "- 3"])
def test_a_signed_number_is_rejected_a_minus_is_a_neg_node(spelling):
    # docs/contracts.md: a Number carries its source spelling and the tokenizer has no
    # negative literal, so a sign can only arrive as a Neg node
    mul = op("Mul", [leaf("Number", 0, 2, spelling), leaf("Variable", 2, 3, "x")], 0, 3)
    with pytest.raises(ExplorerError, match="not a plain decimal number"):
        build_explorer_tree(equation(mul, leaf("Number", 6, 7, "6"), 7))


# ---- spoken text -------------------------------------------------------------


def test_quick_descriptions_for_3x_plus_5_eq_14():
    root = tree("3x+5=14")
    left, right = root["children"]
    mul, five = left["children"]
    three, x = mul["children"]
    assert root["spoken_quick"] == "Equation"
    assert left["spoken_quick"] == "Left side"
    assert right["spoken_quick"] == "Right side"
    assert mul["spoken_quick"] == "Multiplication"
    assert three["spoken_quick"] == "Coefficient 3"
    assert x["spoken_quick"] == "Variable x"
    assert five["spoken_quick"] == "Constant term 5"


@pytest.mark.parametrize(
    "type_, word",
    [("Add", "Addition"), ("Sub", "Subtraction"), ("Mul", "Multiplication"),
     ("Div", "Fraction"), ("Pow", "Power")],
)
def test_operator_quick_names(type_, word):
    inner = op(type_, [leaf("Number", 4, 5, 1), leaf("Number", 6, 7, 2)], 4, 7)
    root = build_explorer_tree(equation(leaf("Variable", 0, 1, "x"), inner, 7))
    # the operator is the right side, so check its detailed text starts with the name
    assert word in root["children"][1]["spoken_detailed"]
    outer = op("Add", [inner, leaf("Number", 8, 9, 1)], 4, 9)
    root = build_explorer_tree(equation(leaf("Variable", 0, 1, "x"), outer, 9))
    assert root["children"][1]["children"][0]["spoken_quick"] == word


def test_detailed_and_context_text():
    root = tree("3x+5=14")
    left = root["children"][0]
    mul, five = left["children"]
    three = mul["children"][0]
    assert "coefficient" in three["spoken_detailed"] and "multiplied by 3" in three["spoken_detailed"]
    assert "constant term" in five["spoken_detailed"]
    assert root["spoken_context"] == "This is the whole equation."
    # Context wording was enriched in the explanation milestone: the old
    # position-only strings became relationship statements (see the
    # "explanation quality" tests below for the full set).
    assert left["spoken_context"] == (
        "The addition expression 3x plus 5 forms the left side of the equation. "
        "The right side is 14."
    )
    assert five["spoken_context"] == (
        "The constant term 5 is added to the term 3x. "
        "It is part of the left side of the equation."
    )
    assert root["children"][1]["spoken_context"] == (
        "The number 14 forms the right side of the equation. The left side is 3x plus 5."
    )


def test_quick_text_has_no_math_symbols():
    for name in FIXTURES:
        for n in flat(tree(name)):
            assert not any(ch in n["spoken_quick"] for ch in "+-*/^=()")


# ---- malformed / unsupported input -----------------------------------------


def test_root_must_be_equation():
    with pytest.raises(ExplorerError, match="root must be an Equation"):
        build_explorer_tree(leaf("Number", 0, 1, 3))


def test_nested_equation_rejected():
    inner = equation(leaf("Number", 0, 1, 1), leaf("Number", 2, 3, 1), 3)
    with pytest.raises(ExplorerError, match="only be the root"):
        build_explorer_tree(equation(inner, leaf("Number", 6, 7, 1), 7))


@pytest.mark.parametrize("children", [[], [leaf("Number", 0, 1, 1)],
                                      [leaf("Number", 0, 1, 1)] * 3])
def test_equation_needs_exactly_two_children(children):
    with pytest.raises(ExplorerError, match="needs 2"):
        build_explorer_tree(op("Equation", children, 0, 5))


def test_operator_with_wrong_child_count_rejected():
    add = op("Add", [leaf("Number", 0, 1, 1)], 0, 3)
    with pytest.raises(ExplorerError, match="Add needs 2"):
        build_explorer_tree(equation(add, leaf("Number", 6, 7, 1), 7))


def test_leaf_with_children_rejected():
    bad = {"type": "Number", "value": "1", "span": [0, 1], "children": [leaf("Number", 0, 1, 1)]}
    with pytest.raises(ExplorerError, match="needs 0"):
        build_explorer_tree(equation(bad, leaf("Number", 6, 7, 1), 7))


@pytest.mark.parametrize("bad", [
    {"type": "Number", "children": [], "span": [0, 1]},                # no value
    {"type": "Number", "value": 3, "children": [], "span": [0, 1]},     # int, not a string
    {"type": "Number", "value": "", "children": [], "span": [0, 1]},    # empty spelling
    {"type": "Number", "value": True, "children": [], "span": [0, 1]},  # bool
    {"type": "Variable", "children": [], "span": [0, 1]},               # no value
    {"type": "Variable", "value": "", "children": [], "span": [0, 1]},  # empty value
])
def test_missing_or_bad_values_rejected(bad):
    with pytest.raises(ExplorerError, match="value"):
        build_explorer_tree(equation(bad, leaf("Number", 6, 7, 1), 7))


def test_unexpected_value_on_operator_rejected():
    bad = {"type": "Add", "value": 1, "span": [0, 3],
           "children": [leaf("Number", 0, 1, 1), leaf("Number", 2, 3, 1)]}
    with pytest.raises(ExplorerError, match="must not have a 'value'"):
        build_explorer_tree(equation(bad, leaf("Number", 6, 7, 1), 7))


@pytest.mark.parametrize("node_type", ["Abs", "Sqrt", "", "number"])
def test_unsupported_node_type_fails_clearly(node_type):
    bad = {"type": node_type, "children": [], "span": [0, 1]}
    with pytest.raises(ExplorerError, match="unsupported node type"):
        build_explorer_tree(equation(bad, leaf("Number", 6, 7, 1), 7))


def test_unsupported_node_deep_in_tree_reports_its_path():
    bad = {"type": "Sqrt", "children": [leaf("Number", 0, 1, 1)], "span": [0, 3]}
    add = op("Add", [leaf("Number", 0, 1, 1), bad], 0, 7)
    with pytest.raises(ExplorerError, match=r"ast\.children\[0\]\.children\[1\]"):
        build_explorer_tree(equation(add, leaf("Number", 10, 11, 1), 11))


@pytest.mark.parametrize("bad", [None, 5, "3x", [], ["Number"]])
def test_non_dict_input_rejected(bad):
    with pytest.raises(ExplorerError, match="must be a dict"):
        build_explorer_tree(bad)


@pytest.mark.parametrize("missing", ["type", "children", "span"])
def test_missing_required_key_rejected(missing):
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    del ast[missing]
    with pytest.raises(ExplorerError, match=f"missing '{missing}'"):
        build_explorer_tree(ast)


@pytest.mark.parametrize("span", [None, [0], [0, 1, 2], [3, 3], [5, 2], [-1, 2], ["a", "b"], [0.5, 1]])
def test_bad_span_rejected(span):
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    ast["span"] = span
    with pytest.raises(ExplorerError, match="span"):
        build_explorer_tree(ast)


def test_children_must_be_a_list():
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    ast["children"] = None
    with pytest.raises(ExplorerError, match="'children' must be a list"):
        build_explorer_tree(ast)


def test_explorer_error_is_a_value_error():
    assert issubclass(ExplorerError, ValueError)


# ===========================================================================
# Part 3: explanation quality (detailed + context text)
# ===========================================================================
# These tests check what the sentences SAY (which numbers, roles and
# relationships they name), not just that a string exists.

X = lambda s=0: leaf("Variable", s, s + 1, "x")  # noqa: E731


def N(v, s=0):
    return leaf("Number", s, s + len(str(v)), v)


def term(c, s=0):
    """c x as Mul(Number, Variable)"""
    return op("Mul", [N(c, s), X(s + 1)], s, s + 2)


def eq(left, right):
    return equation(left, right, 30)


def build(left, right):
    return build_explorer_tree(eq(left, right))


def by_role(root, role):
    return [n for n in flat(root) if n["role"] == role]


def spoken(n):
    return " ".join((n["spoken_quick"], n["spoken_detailed"], n["spoken_context"]))


def sentences(text):
    return [s.strip() for s in text.split(".") if s.strip()]


# ---- 3x + 5 = 14 : every role, all three depths -------------------------------


def test_equation_detailed_says_left_equals_right():
    root = tree("3x+5=14")
    d = root["spoken_detailed"]
    assert "left side, 3x plus 5," in d and "same value as the right side, 14" in d
    assert root["spoken_context"] == "This is the whole equation."


def test_left_side_detailed_contains_the_expression_and_its_operation():
    left = tree("3x+5=14")["children"][0]
    d = left["spoken_detailed"]
    assert "before the equals sign" in d
    assert "3x plus 5" in d
    assert "combines the term 3x and the constant 5 by adding" in d


def test_right_side_detailed_contains_the_value():
    right = tree("3x+5=14")["children"][1]
    assert "after the equals sign" in right["spoken_detailed"]
    assert "just the number 14" in right["spoken_detailed"]


def test_side_context_names_the_other_side():
    left, right = tree("3x+5=14")["children"]
    assert "forms the left side of the equation" in left["spoken_context"]
    assert left["spoken_context"].endswith("The right side is 14.")
    assert "forms the right side of the equation" in right["spoken_context"]
    assert right["spoken_context"].endswith("The left side is 3x plus 5.")


def test_coefficient_detailed_and_context():
    coef = tree("3x+5=14")["children"][0]["children"][0]["children"][0]
    assert coef["role"] == "coefficient"
    assert "3 is the coefficient of x" in coef["spoken_detailed"]
    assert "x is multiplied by 3" in coef["spoken_detailed"]
    assert coef["spoken_context"].startswith(
        "The coefficient 3 belongs to the variable x: x is multiplied by 3."
    )
    # it names the term it forms; where that term goes is said by the Mul node
    assert coef["spoken_context"].endswith("Together they form the term 3x.")


def test_variable_detailed_and_context():
    x = tree("3x+5=14")["children"][0]["children"][0]["children"][1]
    assert "unknown number" in x["spoken_detailed"]
    assert "multiplied by the coefficient 3" in x["spoken_detailed"]
    assert x["spoken_context"] == (
        "The variable x is multiplied by the coefficient 3. "
        "It is part of the left side of the equation."
    )


def test_constant_detailed_and_context():
    five = tree("3x+5=14")["children"][0]["children"][1]
    assert "constant term" in five["spoken_detailed"]
    assert "does not multiply x" in five["spoken_detailed"]
    assert five["spoken_detailed"].endswith("It is added to the term 3x.")
    assert five["spoken_context"].startswith("The constant term 5 is added to the term 3x.")


def test_multiplication_detailed_and_context():
    mul = tree("3x+5=14")["children"][0]["children"][0]
    assert "combines the coefficient 3 and the variable x by multiplying" in mul["spoken_detailed"]
    assert "3x means 3 times x" in mul["spoken_detailed"]
    assert mul["spoken_context"].startswith("The term 3x is added to the constant 5.")


def test_addition_detailed_is_on_the_left_side_node():
    left = tree("3x+5=14")["children"][0]
    assert left["type"] == "Add"
    assert left["spoken_detailed"].count("Addition.") == 1


# ---- other expressions ----------------------------------------------------


def test_2x_plus_3_eq_9_uses_its_own_numbers():
    left = tree("2x+3=9")["children"][0]
    mul, three = left["children"]
    assert "term 2x" in three["spoken_detailed"]
    assert "constant term 3 is added to the term 2x" in three["spoken_context"]
    assert "coefficient 2" in mul["spoken_detailed"]
    assert "just the number 9" in tree("2x+3=9")["children"][1]["spoken_detailed"]
    assert "5" not in spoken(three) and "14" not in spoken(mul)


def test_2x_plus_3x_eq_10_same_node_type_two_terms_name_each_other():
    # Both terms are Mul nodes under the same Add; each must point at the OTHER.
    root = build(op("Add", [term(2), term(3, 5)], 0, 7), N(10, 10))
    first, second = root["children"][0]["children"]
    assert "The term 2x is added to the term 3x." in first["spoken_context"]
    assert "The term 3x is added to the term 2x." in second["spoken_context"]
    assert "combines the term 2x and the term 3x" in root["children"][0]["spoken_detailed"]
    c1, c2 = by_role(root, "coefficient")
    assert "coefficient 2 belongs" in c1["spoken_context"]
    assert "coefficient 3 belongs" in c2["spoken_context"]
    assert c1["spoken_context"].endswith("form the term 2x.")
    assert c2["spoken_context"].endswith("form the term 3x.")


def test_3x_minus_5_eq_10_subtraction_direction_is_clear():
    root = build(op("Sub", [term(3), N(5, 5)], 0, 6), N(10, 9))
    left = root["children"][0]
    mul, five = left["children"]
    assert left["spoken_detailed"].count("Subtraction.") == 1
    assert "takes the constant 5 away from the term 3x" in left["spoken_detailed"]
    assert "The constant term 5 is subtracted from the term 3x." in five["spoken_context"]
    assert "subtracted from the term 3x" in five["spoken_detailed"]
    # the term sees the subtraction from the other direction
    assert "The term 3x has the constant 5 subtracted from it." in mul["spoken_context"]
    assert "added" not in spoken(five)


def test_constant_first_in_subtraction():
    # 5 - 3x = 1 : here 5 is the minuend
    root = build(op("Sub", [N(5), term(3, 4)], 0, 6), N(1, 9))
    five = root["children"][0]["children"][0]
    assert five["role"] == "constant"
    assert "The term 3x is subtracted from the constant term 5" not in five["spoken_context"]
    assert "has the term 3x subtracted from it" in five["spoken_context"]


def test_same_node_type_different_roles_get_different_explanations():
    # 3x + 5 = 5 : Number 5 is a constant term on the left, a plain right side
    root = build(op("Add", [term(3), N(5, 5)], 0, 6), N(5, 9))
    constant = root["children"][0]["children"][1]
    right = root["children"][1]
    assert constant["type"] == right["type"] == "Number"
    assert (constant["role"], right["role"]) == ("constant", "right_side")
    assert constant["spoken_detailed"] != right["spoken_detailed"]
    assert "constant term" in constant["spoken_detailed"]
    assert "constant" not in right["spoken_detailed"]
    # the Number 3 in 3x is a coefficient; the Number 3 in 2*3 is neither
    root = build(op("Add", [term(3), op("Mul", [N(2, 5), N(3, 7)], 5, 8)], 0, 8), N(1, 11))
    coef = by_role(root, "coefficient")[0]
    plain = by_role(root, "number")
    assert "coefficient of x" in coef["spoken_detailed"]
    assert all("coefficient of x" not in p["spoken_detailed"] for p in plain)


def test_plain_number_explains_why_it_is_not_a_coefficient():
    root = build(op("Mul", [N(2), N(3, 2)], 0, 3), X(6))
    two, three = root["children"][0]["children"]
    assert two["role"] == "number"
    assert "not a coefficient" in two["spoken_detailed"]
    assert "The number 2 is multiplied by the number 3." in two["spoken_context"]
    assert "The number 3 is multiplied by the number 2." in three["spoken_context"]


def test_variable_alone_has_no_coefficient_claim():
    root = build(X(), N(4, 4))
    x = root["children"][0]
    assert x["role"] == "left_side"
    assert "just the variable x" in x["spoken_detailed"]
    assert "coefficient" not in spoken(x)


def test_variable_before_coefficient_x_times_3():
    root = build(op("Mul", [X(), N(3, 2)], 0, 3), N(6, 6))
    left = root["children"][0]
    x, three = left["children"]
    assert "combines the variable x and the coefficient 3" in left["spoken_detailed"]
    assert "3x means" not in left["spoken_detailed"]  # only for number-first
    assert "x is multiplied by 3" in three["spoken_detailed"]
    assert "multiplied by the coefficient 3" in x["spoken_context"]


def test_power_expression_roles_and_wording():
    # x^2 + 3 = 7 : Pow wording was generic in Phase 1; Phase 2 adds
    # base / exponent / squared wording (full coverage in Part 4).
    root = build(op("Add", [op("Pow", [X(), N(2, 2)], 0, 3), N(3, 6)], 0, 7), N(7, 10))
    pow_node = root["children"][0]["children"][0]
    x, two = pow_node["children"]
    three = root["children"][0]["children"][1]
    assert pow_node["role"] == "power"
    assert "squared" in pow_node["spoken_detailed"]
    assert two["role"] == "exponent"
    assert "not a constant term or a coefficient" in two["spoken_detailed"]
    assert "is the base, raised to the power 2" in x["spoken_context"]
    assert "exponent that the variable x is raised to" not in x["spoken_context"]
    assert "constant term 3 is added to the expression x to the power of 2" in three["spoken_context"]


def test_power_followed_by_more_terms_is_not_ambiguous():
    root = build(op("Add", [op("Pow", [X(), N(2, 2)], 0, 3), N(3, 6)], 0, 7), N(7, 10))
    # a pause separates the exponent from "plus 3"
    assert "x to the power of 2, plus 3" in root["children"][0]["spoken_detailed"]


def test_group_is_supported_since_phase_2():
    # was test_group_still_rejected_so_2_times_bracket_is_phase_2
    group = {"type": "Group", "children": [op("Add", [X(2), N(3, 6)], 2, 7)], "span": [1, 8]}
    root = build(op("Mul", [N(2), group], 0, 8), N(12, 11))
    assert root["children"][0]["children"][1]["role"] == "group"


# ---- negatives ---------------------------------------------------------------


def test_negated_constant_in_a_sum():
    # -5 + 3x = 1 as Add(Neg(5), 3x)
    root = build(op("Add", [op("Neg", [N(5, 1)], 0, 2), term(3, 5)], 0, 7), N(1, 10))
    neg, mul = root["children"][0]["children"]
    five = neg["children"][0]
    assert "changes the sign of the constant 5" in neg["spoken_detailed"]
    assert "The negation of 5 is added to the term 3x." in neg["spoken_context"]
    assert "negation changes its sign" in five["spoken_detailed"]
    assert "sign changed" in five["spoken_context"]
    assert "The term 3x is added to the negation of 5." in mul["spoken_context"]


def test_negations_are_spoken_as_negative_and_never_print_a_minus_sign():
    # -3x + -5 = -1 with every minus a Neg node (docs/contracts.md)
    root = build(op("Add", [Ng(op("Mul", [N(3, 1), X(2)], 1, 3)), Ng(N(5, 7))], 0, 8), Ng(N(1, 12)))
    assert "negative 3x plus negative 5" in root["spoken_detailed"]
    assert "It reads negative 1." in root["children"][1]["spoken_detailed"]
    coef = by_role(root, "coefficient")[0]
    const = by_role(root, "constant")[0]
    assert (coef["value"], const["value"]) == ("3", "5")
    assert "-" not in " ".join(spoken(n) for n in flat(root))


def test_number_spelling_is_kept_exactly_in_value_and_speech():
    # docs/contracts.md: Number.value is the source spelling; "2.0" is not rewritten to "2"
    root = build(op("Add", [term("2.0"), N("1.50", 5)], 0, 8), N("4.0", 11))
    assert [n["value"] for n in flat(root) if n["type"] == "Number"] == ["2.0", "1.50", "4.0"]
    assert "term 2.0x" in root["children"][0]["children"][1]["spoken_context"]
    assert "constant term 1.50" in root["children"][0]["children"][1]["spoken_context"]
    assert "just the number 4.0." in root["children"][1]["spoken_detailed"]


# ---- nesting and ambiguity ------------------------------------------------------


def test_deeply_nested_sum_names_the_right_neighbours():
    # 3x + 2x + 5 = 14  ->  Add(Add(3x, 2x), 5)
    inner = op("Add", [term(3), term(2, 5)], 0, 7)
    root = build(op("Add", [inner, N(5, 10)], 0, 11), N(14, 14))
    left = root["children"][0]
    inner_ex, five = left["children"]
    assert "3x plus 2x plus 5" in left["spoken_detailed"]
    assert "combines the sum 3x plus 2x and the constant 5" in left["spoken_detailed"]
    assert "The sum 3x plus 2x is added to the constant 5." in inner_ex["spoken_context"]
    assert "The constant term 5 is added to the sum 3x plus 2x." in five["spoken_context"]
    # the terms inside are described relative to each other, not to the 5
    t1, t2 = inner_ex["children"]
    assert "The term 3x is added to the term 2x." in t1["spoken_context"]
    assert "The term 2x is added to the term 3x." in t2["spoken_context"]


def test_subtracting_a_sum_is_grouped_in_speech():
    # 10 - (x + 2) = 0 written as Sub(10, Add(x, 2)) without a Group node
    root = build(op("Sub", [N(10), op("Add", [X(5), N(2, 9)], 5, 10)], 0, 10), N(0, 13))
    d = root["children"][0]["spoken_detailed"]
    assert "10 minus the quantity x plus 2" in d


def test_multiplying_a_sum_is_grouped_in_speech():
    root = build(op("Mul", [N(2), op("Add", [X(2), N(3, 6)], 2, 7)], 0, 8), N(12, 11))
    assert "2 times the quantity x plus 3" in root["children"][0]["spoken_detailed"]


def test_no_two_nodes_share_identical_context_text():
    # in 2x + 3x the two terms look alike; their context must still differ
    root = build(op("Add", [term(2), term(3, 5)], 0, 7), N(10, 10))
    contexts = [n["spoken_context"] for n in flat(root)]
    assert len(contexts) == len(set(contexts))


def test_sentences_not_repeated_across_a_path():
    # the same sentence should not be read at every level when going down
    for name in FIXTURES:
        node = tree(name)
        while node["children"]:
            child = node["children"][0]
            for key in ("spoken_detailed", "spoken_context"):
                shared = set(sentences(node[key])) & set(sentences(child[key]))
                assert not shared, (name, key, shared)
            node = child


# ---- quick text stays short and unchanged in meaning ---------------------------


def test_quick_text_is_short_and_exact_for_every_role():
    root = build(op("Add", [term(3), N(5, 5)], 0, 6), N(14, 9))
    quick = {n["role"]: n["spoken_quick"] for n in flat(root)}
    assert quick == {
        "equation": "Equation",
        "left_side": "Left side",
        "right_side": "Right side",
        "operator": "Multiplication",
        "coefficient": "Coefficient 3",
        "variable": "Variable x",
        "constant": "Constant term 5",
    }
    assert all(len(n["spoken_quick"].split()) <= 3 for n in flat(root))


def test_addition_and_subtraction_quick_names():
    root = build(
        op("Sub", [op("Add", [term(2), N(1, 5)], 0, 6), N(4, 9)], 0, 10), N(0, 13)
    )
    inner = root["children"][0]["children"][0]
    assert inner["spoken_quick"] == "Addition"
    assert root["children"][0]["spoken_quick"] == "Left side"


# ---- missing / incomplete context ------------------------------------------


def test_lone_operator_child_with_no_sibling_still_explains():
    # Neg has one child: there is no sibling to name
    root = build(op("Neg", [term(3, 1)], 0, 3), N(6, 6))
    neg = root["children"][0]
    mul = neg["children"][0]
    assert "changes the sign of the term 3x" in neg["spoken_detailed"]
    assert "has its sign changed" in mul["spoken_context"]
    assert "None" not in spoken(mul)


def test_context_never_leaks_python_placeholders():
    shapes = [
        build(op("Add", [term(3), N(5, 5)], 0, 6), N(14, 9)),
        build(op("Sub", [N(5), N(2, 4)], 0, 5), X(8)),
        build(op("Div", [X(), N(2, 4)], 0, 5), N(3, 8)),
        build(op("Pow", [X(), N(2, 2)], 0, 3), N(4, 6)),
        build(op("Neg", [X(1)], 0, 2), N(4, 5)),
    ]
    for root in shapes:
        for n in flat(root):
            for key in ("spoken_quick", "spoken_detailed", "spoken_context"):
                text = n[key]
                assert text.strip() and "None" not in text
                assert "{" not in text and "}" not in text


def test_division_explanations():
    root = build(op("Div", [X(), N(2, 4)], 0, 5), N(3, 8))
    left = root["children"][0]
    x, two = left["children"]
    assert "the fraction means x divided by 2" in left["spoken_detailed"]
    assert "numerator of a fraction whose denominator is 2" in x["spoken_context"]
    assert "The denominator 2 divides the numerator x" in two["spoken_context"]
    assert "the fraction with numerator x and denominator 2" in root["spoken_detailed"]


def test_spoken_text_has_no_math_symbols_anywhere():
    for name in FIXTURES:
        for n in flat(tree(name)):
            assert not any(ch in spoken(n) for ch in "+*/^=()")


def test_explanations_are_deterministic_and_do_not_change_structure():
    first, second = tree("3x+5=14"), tree("3x+5=14")
    assert first == second
    for n in flat(first):
        assert set(n) == EXPLORER_FIELDS


# ===========================================================================
# Part 4: Phase 2 mathematical structures (Group, multiplier, Power, Fraction)
# ===========================================================================
# A fraction is a Div node (docs/contracts.md has no Fraction type); `Fr` below
# builds one. Group and Pow follow docs/contracts.md.

SYMBOLS = "+*/^=()"
NEW_FIXTURES = [
    "2(x+3)=12", "(x+1)(x-2)=0", "2(3(x+1)+4)=20",
    "x^2+3=7", "(x+1)^2=9", "(x+1)/2=3", "x^2/3=4", "(x/2)^2=9",
]


def G(inner, start=1, end=8):
    return {"type": "Group", "children": [inner], "span": [start, end]}


def Fr(num, den, start=0, end=9):
    return {"type": "Div", "children": [num, den], "span": [start, end]}


def Pw(base, exp, start=0, end=3):
    return op("Pow", [base, exp], start, end)


def x_plus_3():
    return op("Add", [X(2), N(3, 6)], 2, 7)


def two_times_group():
    # 2(x + 3)
    return op("Mul", [N(2), G(x_plus_3())], 0, 8)


def find(root, type_, role=None):
    return [n for n in flat(root) if n["type"] == type_ and (role is None or n["role"] == role)]


# ---- 1. Group -----------------------------------------------------------------


def test_group_fixture_roles_2_group_x_plus_3():
    root = tree("2(x+3)=12")
    mul = root["children"][0]
    two, group = mul["children"]
    add = group["children"][0]
    x, three = add["children"]
    assert (mul["role"], mul["type"]) == ("left_side", "Mul")
    assert (two["role"], two["value"]) == ("group_multiplier", "2")
    assert (group["role"], group["type"]) == ("group", "Group")
    assert (add["role"], add["type"]) == ("operator", "Add")
    assert (x["role"], x["value"]) == ("variable", "x")
    assert (three["role"], three["value"]) == ("constant", "3")
    assert root["children"][1]["role"] == "right_side"


def test_group_keeps_child_structure_and_ids():
    root = tree("2(x+3)=12")
    group = root["children"][0]["children"][1]
    assert group["id"] == "n0.0.1"
    assert len(group["children"]) == 1
    assert group["children"][0]["id"] == "n0.0.1.0"
    assert "span" not in group and "span" not in group["children"][0]


def test_group_fixture_span_includes_the_brackets_but_the_child_span_does_not():
    # a property of the AST fixture (the explorer output has no span)
    source, ast = FIXTURES["2(x+3)=12"]
    group = ast["children"][0]["children"][1]
    assert source[slice(*group["span"])] == "(x + 3)"
    assert source[slice(*group["children"][0]["span"])] == "x + 3"


def test_group_quick_text():
    group = tree("2(x+3)=12")["children"][0]["children"][1]
    assert group["spoken_quick"] == "Group"
    assert group["children"][0]["spoken_quick"] == "Addition"


def test_group_detailed_distinguishes_group_from_its_contents():
    group = tree("2(x+3)=12")["children"][0]["children"][1]
    text = group["spoken_detailed"]
    assert "The group contains x plus 3" in text
    assert "treated as one quantity" in text
    assert "the group is the brackets as a whole" in text.lower()
    assert "the sum x plus 3 is the expression inside it" in text
    # the contents are described separately, as being inside the group
    inner = group["children"][0]["spoken_detailed"]
    assert inner.startswith("Addition.")
    assert "content of the group" in inner
    assert "The group contains" not in inner


def test_group_detailed_says_the_whole_group_is_multiplied():
    group = tree("2(x+3)=12")["children"][0]["children"][1]
    assert "The entire group is multiplied by the multiplier 2" in group["spoken_detailed"]


def test_group_context():
    group = tree("2(x+3)=12")["children"][0]["children"][1]
    assert group["spoken_context"] == (
        "The group x plus 3 is multiplied by the multiplier 2. "
        "It is treated as one quantity. It is part of the left side of the equation."
    )
    inner = group["children"][0]
    assert inner["spoken_context"] == (
        "The sum x plus 3 is the content of the group, enclosed by its brackets."
    )


def test_group_contents_keep_their_own_roles_and_explanations():
    root = tree("2(x+3)=12")
    group = root["children"][0]["children"][1]
    x, three = group["children"][0]["children"]
    assert "added to the constant 3" in x["spoken_context"]
    assert "is a constant term" in three["spoken_detailed"]
    assert "added to the variable x" in three["spoken_detailed"]


def test_group_as_a_whole_side_of_the_equation():
    # (x + 3) = 5 : the group is the left side; side role wins (as for operators)
    root = build(G(x_plus_3()), N(5, 11))
    left = root["children"][0]
    assert (left["role"], left["type"]) == ("left_side", "Group")
    assert left["spoken_quick"] == "Left side"
    assert "It reads the group x plus 3" in left["spoken_detailed"]
    assert "The group contains x plus 3" in left["spoken_detailed"]
    assert left["spoken_context"].startswith("The group x plus 3 forms the left side")
    inner = left["children"][0]
    assert inner["role"] == "operator"  # contents of a side-root group are not the side
    assert "content of the group" in inner["spoken_context"]


def test_group_alone_in_a_sum():
    # (x + 3) + 5 = 9
    root = build(op("Add", [G(x_plus_3()), N(5, 11)], 0, 12), N(9, 16))
    group, five = root["children"][0]["children"]
    assert group["role"] == "group"
    assert "The entire group is added to the constant 5" in group["spoken_detailed"]
    assert five["role"] == "constant"
    assert "added to the group x plus 3" in five["spoken_context"]


def test_nested_groups():
    root = tree("2(3(x+1)+4)=20")
    outer = root["children"][0]["children"][1]
    add = outer["children"][0]
    inner_mul, four = add["children"]
    three, inner = inner_mul["children"]
    assert [outer["role"], inner["role"]] == ["group", "group"]
    assert three["role"] == "group_multiplier"
    assert four["role"] == "constant"
    assert "The group contains 3 times the group x plus 1, plus 4" in outer["spoken_detailed"]
    assert "The group contains x plus 1" in inner["spoken_detailed"]
    # the two groups are told apart in their context text
    assert outer["spoken_context"] != inner["spoken_context"]
    assert "multiplied by the multiplier 3" in inner["spoken_context"]
    assert "multiplied by the multiplier 2" in outer["spoken_context"]
    ids = [n["id"] for n in flat(root)]
    assert len(ids) == len(set(ids))


def test_group_directly_inside_group():
    # ((x + 3)) = 5
    inner = G(x_plus_3(), 2, 9)
    outer = G(inner, 1, 10)
    root = build(outer, N(5, 13))
    og = root["children"][0]
    ig = og["children"][0]
    assert (og["role"], ig["role"]) == ("left_side", "group")
    assert "The group contains the group x plus 3" in og["spoken_detailed"]
    assert "content of the group" in ig["spoken_context"]


def test_two_groups_multiplied_have_no_multiplier_role():
    # (x + 1)(x - 2) = 0 : no bare number multiplies a group here
    root = tree("(x+1)(x-2)=0")
    assert find(root, "Number", "group_multiplier") == []
    g1, g2 = root["children"][0]["children"]
    assert [g1["role"], g2["role"]] == ["group", "group"]
    assert "multiplied by the group x minus 2" in g1["spoken_context"]
    assert "multiplied by the group x plus 1" in g2["spoken_context"]
    assert g1["spoken_context"] != g2["spoken_context"]
    sub = g2["children"][0]
    assert sub["role"] == "operator" and sub["spoken_quick"] == "Subtraction"
    assert "takes the constant 2 away from the variable x" in sub["spoken_detailed"]


# ---- 2. Multiplier of a group --------------------------------------------------


def test_multiplier_role_and_quick():
    two = tree("2(x+3)=12")["children"][0]["children"][0]
    assert two["role"] == "group_multiplier"
    assert two["spoken_quick"] == "Multiplier 2"


def test_multiplier_detailed():
    two = tree("2(x+3)=12")["children"][0]["children"][0]
    assert two["spoken_detailed"] == (
        "2 is the multiplier of the group x plus 3. It multiplies the entire group "
        "x plus 3, so every part inside the brackets is multiplied by 2. "
        "It is not a coefficient, because it multiplies a group and not the variable."
    )


def test_multiplier_context():
    two = tree("2(x+3)=12")["children"][0]["children"][0]
    assert two["spoken_context"] == (
        "The multiplier 2 multiplies the entire group x plus 3. "
        "Together they form the product 2 times the group x plus 3. "
        "It is part of the left side of the equation."
    )


def test_multiplication_node_mentions_the_whole_group():
    mul = tree("2(x+3)=12")["children"][0]
    assert "So 2 multiplies the entire group x plus 3." in mul["spoken_detailed"]
    assert "2 times the group x plus 3" in mul["spoken_context"]


def test_multiplier_after_the_group():
    # (x + 3)2 : same role regardless of order
    root = build(op("Mul", [G(x_plus_3(), 0, 7), N(2, 7)], 0, 8), N(12, 11))
    group, two = root["children"][0]["children"]
    assert two["role"] == "group_multiplier"
    assert group["role"] == "group"
    assert "So 2 multiplies the entire group x plus 3." in root["children"][0]["spoken_detailed"]
    assert "the group x plus 3 end group times 2" in root["children"][0]["spoken_detailed"]


def test_multiplier_is_not_a_coefficient_and_a_coefficient_is_not_a_multiplier():
    # 2x + 2(x + 3) = 10 : two 2s, two different roles
    left = op("Add", [term(2), two_times_group()], 0, 12)
    root = build(left, N(10, 15))
    assert [n["value"] for n in by_role(root, "coefficient")] == ["2"]
    assert [n["value"] for n in by_role(root, "group_multiplier")] == ["2"]
    coeff = by_role(root, "coefficient")[0]
    mult = by_role(root, "group_multiplier")[0]
    assert coeff["spoken_quick"] == "Coefficient 2"
    assert mult["spoken_quick"] == "Multiplier 2"
    assert "coefficient of x" in coeff["spoken_detailed"]
    assert "multiplier of the group" in mult["spoken_detailed"]
    assert "not a coefficient" in mult["spoken_detailed"]
    assert "group" not in coeff["spoken_detailed"]
    assert coeff["spoken_context"] != mult["spoken_context"]


def test_variable_times_group_has_no_multiplier_role():
    # x(x + 3) = 4 : the variable multiplies the group, it is not a number
    root = build(op("Mul", [X(0), G(x_plus_3(), 1, 8)], 0, 8), N(4, 11))
    x, group = root["children"][0]["children"]
    assert x["role"] == "variable"
    assert find(root, "Number", "group_multiplier") == []
    assert find(root, "Number", "coefficient") == []
    assert x["spoken_context"] == (
        "The variable x is multiplied by the group x plus 3. "
        "It is part of the left side of the equation."
    )
    assert "coefficient" not in x["spoken_detailed"]
    assert "multiplier" not in spoken(x)
    assert "The group x plus 3 is multiplied by the variable x." in group["spoken_context"]


def test_number_times_variable_is_still_a_coefficient():
    root = build(op("Add", [term(3), N(5, 5)], 0, 6), N(14, 9))
    assert by_role(root, "group_multiplier") == []
    assert [n["value"] for n in by_role(root, "coefficient")] == ["3"]


def test_number_times_number_is_neither():
    root = build(op("Mul", [N(2), N(3, 2)], 0, 3), N(6, 6))
    assert {n["role"] for n in root["children"][0]["children"]} == {"number"}


def test_negated_multiplier_is_a_negation_of_a_number_not_a_multiplier():
    # -2(x + 3): a Neg node is not a bare number, so the 2 below it is not a multiplier
    group = G(x_plus_3(), 2, 9)
    root = build(op("Mul", [Ng(N(2, 1)), group], 0, 9), N(4, 12))
    neg, grp = root["children"][0]["children"]
    assert (neg["type"], neg["role"], grp["role"]) == ("Neg", "operator", "group")
    assert neg["children"][0]["role"] == "number"
    assert find(root, "Number", "group_multiplier") == []
    assert "-" not in spoken(neg)


def test_negated_group_is_a_negation_not_a_multiplier():
    # -(x + 3) = 5 as Neg(Group(...))
    root = build(op("Neg", [G(x_plus_3(), 1, 8)], 0, 8), N(5, 11))
    neg = root["children"][0]
    group = neg["children"][0]
    assert (neg["role"], neg["type"]) == ("left_side", "Neg")
    assert group["role"] == "group"
    assert find(root, "Number", "group_multiplier") == []
    assert "The entire group has its sign changed" in group["spoken_detailed"]
    assert "negative the group x plus 3" in neg["spoken_detailed"]


def test_multiplier_keeps_its_source_spelling():
    root = build(op("Mul", [N("2.0"), G(x_plus_3())], 0, 8), N(1, 11))
    mult = root["children"][0]["children"][0]
    assert (mult["spoken_quick"], mult["value"]) == ("Multiplier 2.0", "2.0")


# ---- 3. Power -----------------------------------------------------------------


def test_power_fixture_roles():
    root = tree("x^2+3=7")
    pow_node = root["children"][0]["children"][0]
    x, two = pow_node["children"]
    assert (pow_node["role"], pow_node["type"]) == ("power", "Pow")
    assert (x["role"], x["value"]) == ("variable", "x")
    assert (two["role"], two["value"]) == ("exponent", "2")
    assert root["children"][0]["children"][1]["role"] == "constant"


def test_power_quick_text():
    pow_node = tree("x^2+3=7")["children"][0]["children"][0]
    assert pow_node["spoken_quick"] == "Power"
    assert pow_node["children"][1]["spoken_quick"] == "Exponent 2"


def test_squared_detailed_explains_base_exponent_and_meaning():
    pow_node = tree("x^2+3=7")["children"][0]["children"][0]
    assert pow_node["spoken_detailed"] == (
        "Power. The base is x and the exponent is 2. "
        "x squared means x is multiplied by itself: x times x."
    )


def test_exponent_detailed_and_context():
    two = tree("x^2+3=7")["children"][0]["children"][0]["children"][1]
    assert two["spoken_detailed"].startswith(
        "2 is the exponent. It indicates that x is multiplied by itself."
    )
    assert "not a constant term or a coefficient" in two["spoken_detailed"]
    # the power's own context already says which side it is on; not repeated here
    assert two["spoken_context"] == (
        "The exponent 2 belongs to the base x. Together they form x to the power of 2."
    )


def test_base_variable_text_names_its_role_as_base():
    x = tree("x^2+3=7")["children"][0]["children"][0]["children"][0]
    assert x["role"] == "variable"  # a variable base keeps the variable role
    assert "It is the base, raised to the power 2." in x["spoken_detailed"]
    assert x["spoken_context"] == "The variable x is the base, raised to the power 2."


def test_power_context_inside_a_sum():
    pow_node = tree("x^2+3=7")["children"][0]["children"][0]
    assert pow_node["spoken_context"] == (
        "The expression x to the power of 2 is added to the constant 3. "
        "It is part of the left side of the equation."
    )


def test_exponent_is_never_a_constant_or_coefficient():
    # x^2 + 2 = 6 : both numbers are 2, with different roles
    root = build(op("Add", [Pw(X(), N(2, 2)), N(2, 6)], 0, 7), N(6, 10))
    exp = root["children"][0]["children"][0]["children"][1]
    const = root["children"][0]["children"][1]
    assert exp["role"] == "exponent" and const["role"] == "constant"
    assert exp["spoken_quick"] == "Exponent 2" and const["spoken_quick"] == "Constant term 2"
    assert exp["spoken_context"] != const["spoken_context"]
    assert "constant term" not in exp["spoken_context"]
    assert "coefficient" not in exp["spoken_context"]


def test_number_base():
    # 2^3 = 8
    root = build(Pw(N(2), N(3, 2)), N(8, 6))
    pow_node = root["children"][0]
    base, exp = pow_node["children"]
    assert (pow_node["role"], pow_node["type"]) == ("left_side", "Pow")
    assert (base["role"], base["spoken_quick"]) == ("base", "Base 2")
    assert (exp["role"], exp["spoken_quick"]) == ("exponent", "Exponent 3")
    assert "2 is the base of the power" in base["spoken_detailed"]
    assert "the exponent 3 says how many times" in base["spoken_detailed"]
    assert base["spoken_context"].startswith("The base 2 is raised to the exponent 3.")
    assert "2 cubed means 2 is used as a factor three times: 2 times 2 times 2" in pow_node["spoken_detailed"]
    assert "3 is the exponent. It indicates that 2 is used as a factor 3 times." in exp["spoken_detailed"]


def test_higher_exponent_wording():
    root = build(Pw(X(), N(5, 2)), N(1, 6))
    pow_node = root["children"][0]
    assert "x is used as a factor 5 times" in pow_node["spoken_detailed"]
    assert "squared" not in pow_node["spoken_detailed"]
    assert "cubed" not in pow_node["spoken_detailed"]


@pytest.mark.parametrize("value", [0, 1, 0.5, "00"])
def test_other_exponents_get_generic_wording(value):
    root = build(Pw(X(), N(value, 2)), N(1, 8))
    pow_node = root["children"][0]
    assert "It means x is raised to the power" in pow_node["spoken_detailed"]
    for word in ("squared", "cubed", "multiplied by itself"):
        assert word not in pow_node["spoken_detailed"]
    exp = pow_node["children"][1]
    assert exp["role"] == "exponent"
    assert "It is the power that x is raised to." in exp["spoken_detailed"]
    assert "-" not in spoken(exp)


def test_negative_exponent_via_neg_node():
    # x^(-2) written with a Neg node: the exponent is an operator, not a bare number
    neg = op("Neg", [N(2, 4)], 3, 5)
    root = build(Pw(X(), neg, 0, 5), N(1, 9))
    pow_node = root["children"][0]
    exp = pow_node["children"][1]
    assert exp["role"] == "operator" and exp["type"] == "Neg"
    assert "It is the exponent that the variable x is raised to." in exp["spoken_detailed"]
    assert "the exponent is negative 2" in pow_node["spoken_detailed"]


def test_group_as_base_of_a_power():
    root = tree("(x+1)^2=9")
    pow_node = root["children"][0]
    group, two = pow_node["children"]
    assert (pow_node["role"], pow_node["type"]) == ("left_side", "Pow")
    assert (group["role"], two["role"]) == ("group", "exponent")
    assert "The base is the group x plus 1 and the exponent is 2" in pow_node["spoken_detailed"]
    assert "The group x plus 1 squared means the group x plus 1 is multiplied by itself" in (
        pow_node["spoken_detailed"]
    )
    assert "It is the base, raised to the power 2." in group["spoken_detailed"]
    assert "The entire group" not in group["spoken_detailed"]  # no double wording
    assert "belongs to the base the group x plus 1" in two["spoken_context"]


def test_group_base_is_separate_from_exponent_in_speech():
    # the spoken "end group" stops "to the power of" attaching to the wrong thing
    pow_node = tree("(x+1)^2=9")["children"][0]
    assert "the group x plus 1 end group to the power of 2" in tree("(x+1)^2=9")["spoken_detailed"]
    assert pow_node["spoken_context"].startswith("The power expression the group x plus 1")


def test_unwrapped_compound_base_is_marked_as_a_quantity():
    # no Group node: Pow(Add(...), 2) still reads unambiguously
    root = build(Pw(op("Add", [X(), N(1, 4)], 0, 5), N(2, 7), 0, 8), N(9, 12))
    text = root["children"][0]["spoken_detailed"]
    assert "The base is the quantity x plus 1" in text


def test_power_with_variable_exponent_expression_is_grouped():
    # 2^(x + 1) = 8 : exponent is a Group
    root = build(Pw(N(2), G(op("Add", [X(3), N(1, 7)], 3, 8), 2, 9), 0, 9), N(8, 12))
    pow_node = root["children"][0]
    base, exp = pow_node["children"]
    assert (base["role"], exp["role"]) == ("base", "group")
    assert "the exponent is the group x plus 1" in pow_node["spoken_detailed"]
    assert "It is the exponent that the base 2 is raised to." in exp["spoken_detailed"]
    assert "2 is the base of the power" in base["spoken_detailed"]


def test_power_of_power_is_distinguishable():
    # (x^2)^3 = 8
    inner = Pw(X(1), N(2, 3), 1, 4)
    root = build(Pw(G(inner, 0, 5), N(3, 6), 0, 7), N(8, 10))
    outer = root["children"][0]
    group, three = outer["children"]
    pow_inner = group["children"][0]
    assert pow_inner["role"] == "power"
    assert pow_inner["spoken_context"] != outer["spoken_context"]
    assert "x squared means" in pow_inner["spoken_detailed"]
    assert "cubed" in outer["spoken_detailed"]


def test_power_within_product_with_coefficient():
    # 3x^2 = 12 as Mul(3, Pow(x, 2)): the 3 multiplies the powered variable, so it
    # is its coefficient (changed from role "number", which wrongly said that the
    # 3 "does not multiply x")
    root = build(op("Mul", [N(3), Pw(X(1), N(2, 3), 1, 4)], 0, 4), N(12, 7))
    three, pow_node = root["children"][0]["children"]
    assert three["role"] == "coefficient"
    assert three["spoken_quick"] == "Coefficient 3"
    assert pow_node["role"] == "power"
    assert pow_node["children"][1]["role"] == "exponent"


# ---- 4. Fraction (the Div node) ----------------------------------------------


def test_fraction_fixture_roles():
    root = tree("(x+1)/2=3")
    frac = root["children"][0]
    num, den = frac["children"]
    assert (frac["role"], frac["type"]) == ("left_side", "Div")
    assert (num["role"], num["type"]) == ("operator", "Add")
    assert (den["role"], den["value"]) == ("denominator", "2")


def test_fraction_inside_a_sum_gets_the_fraction_role():
    # 2/3 + x = 5
    root = build(op("Add", [Fr(N(2), N(3, 2), 0, 3), X(6)], 0, 7), N(5, 10))
    frac = root["children"][0]["children"][0]
    num, den = frac["children"]
    assert (frac["role"], frac["spoken_quick"]) == ("fraction", "Fraction")
    assert (num["role"], num["spoken_quick"]) == ("numerator", "Numerator 2")
    assert (den["role"], den["spoken_quick"]) == ("denominator", "Denominator 3")


def test_fraction_detailed_explains_the_relationship():
    root = build(op("Add", [Fr(N(2), N(3, 2), 0, 3), X(6)], 0, 7), N(5, 10))
    frac = root["children"][0]["children"][0]
    assert frac["spoken_detailed"] == (
        "Fraction. It has 2 as its numerator and 3 as its denominator. "
        "The numerator is the top part and the denominator is the bottom part, "
        "so the fraction means 2 divided by 3."
    )


def test_fraction_numerator_and_denominator_text():
    root = build(op("Add", [Fr(N(2), N(3, 2), 0, 3), X(6)], 0, 7), N(5, 10))
    frac = root["children"][0]["children"][0]
    num, den = frac["children"]
    assert num["spoken_detailed"] == (
        "2 is the numerator of the fraction: the top part, which is divided by "
        "the denominator 3."
    )
    assert den["spoken_detailed"] == (
        "3 is the denominator of the fraction: the bottom part, which the numerator "
        "2 is divided by. A denominator cannot be zero."
    )
    assert num["spoken_context"].startswith(
        "The numerator 2 is divided by the denominator 3. Together they form "
        "the fraction with numerator 2 and denominator 3."
    )
    assert den["spoken_context"].startswith(
        "The denominator 3 divides the numerator 2. Together they form "
        "the fraction with numerator 2 and denominator 3."
    )
    assert frac["spoken_context"] == (
        "The fraction with numerator 2 and denominator 3 is added to the variable x. "
        "It is part of the left side of the equation."
    )


def test_fraction_with_compound_numerator():
    # (x + 1)/2 = 3 : the numerator is a sum, so it keeps the operator role and
    # says where it sits; "x plus 1 divided by 2" must not be ambiguous
    frac = tree("(x+1)/2=3")["children"][0]
    num, den = frac["children"]
    assert frac["spoken_detailed"].startswith("The left side of the equation")
    assert "It has x plus 1 as its numerator and 2 as its denominator." in frac["spoken_detailed"]
    assert "the quantity x plus 1 divided by 2" in frac["spoken_detailed"]
    assert "It is the numerator of a fraction whose denominator is 2." in num["spoken_detailed"]
    assert num["spoken_context"].startswith(
        "The sum x plus 1 is the numerator of a fraction whose denominator is 2."
    )
    assert "the numerator x plus 1 is divided by" in den["spoken_detailed"]


def test_fraction_with_variable_denominator_keeps_variable_role():
    # 1/x = 4
    root = build(Fr(N(1), X(2), 0, 3), N(4, 6))
    num, den = root["children"][0]["children"]
    assert (num["role"], den["role"]) == ("numerator", "variable")
    assert "It is the denominator of a fraction whose numerator is 1." in den["spoken_detailed"]
    assert den["spoken_context"].startswith("The variable x is the denominator of a fraction")


def test_fraction_with_negated_numerator():
    root = build(Fr(Ng(N(1, 1)), N(2, 3), 0, 4), N(4, 7))
    num = root["children"][0]["children"][0]
    assert (num["role"], num["spoken_quick"]) == ("operator", "Negation")
    assert "the fraction with numerator negative 1 and denominator 2" in (
        root["children"][0]["spoken_detailed"]
    )
    assert "-" not in spoken(num)


def test_fraction_numerator_is_a_power():
    root = tree("x^2/3=4")
    frac = root["children"][0]
    pow_node, three = frac["children"]
    assert pow_node["role"] == "power"
    assert three["role"] == "denominator"
    assert "It has x to the power of 2 as its numerator and 3 as its denominator" in (
        frac["spoken_detailed"]
    )
    assert "x squared means" in pow_node["spoken_detailed"]
    assert "It is the numerator of a fraction whose denominator is 3." in pow_node["spoken_detailed"]


def test_nested_fraction_speech_is_unambiguous():
    # (1/2)/3 as Div(Div(1, 2), 3)
    inner = Fr(N(1), N(2, 2), 0, 3)
    root = build(Fr(inner, N(3, 6), 0, 7), N(4, 10))
    outer = root["children"][0]
    inner_ex = outer["children"][0]
    assert inner_ex["role"] == "fraction"
    assert "the fraction with numerator the fraction with numerator 1 and denominator 2, and denominator 3" in (
        root["spoken_detailed"]
    )
    assert "It is the numerator of a fraction whose denominator is 3." in inner_ex["spoken_detailed"]
    assert outer["spoken_context"] != inner_ex["spoken_context"]


def test_nested_fraction_in_denominator():
    # 1/(1/2) as Div(1, Div(1, 2))
    root = build(Fr(N(1), Fr(N(1, 4), N(2, 6), 4, 7), 0, 7), N(4, 10))
    outer = root["children"][0]
    num, den = outer["children"]
    assert (num["role"], den["role"]) == ("numerator", "fraction")
    assert "denominator the fraction with numerator 1 and denominator 2" in root["spoken_detailed"]
    assert "It is the denominator of a fraction whose numerator is 1." in den["spoken_detailed"]


def test_fraction_followed_by_a_term_is_not_ambiguous():
    # (x + 1)/2 + 5 = 3: a pause stops "plus 5" joining the denominator
    frac = Fr(op("Add", [X(1), N(1, 5)], 1, 6), N(2, 8), 0, 9)
    root = build(op("Add", [frac, N(5, 12)], 0, 13), N(3, 16))
    assert "and denominator 2, plus 5" in root["spoken_detailed"]


def test_group_followed_by_a_term_is_not_ambiguous():
    # 2(x + 3) + 5 = 9
    root = build(op("Add", [two_times_group(), N(5, 11)], 0, 12), N(9, 15))
    assert "2 times the group x plus 3 end group plus 5" in root["spoken_detailed"]
    five = root["children"][0]["children"][1]
    assert five["role"] == "constant"
    assert "added to the product 2 times the group x plus 3" in five["spoken_context"]


def test_div_is_the_one_division_and_fraction_node():
    # docs/contracts.md has Div only: x/2 gets the fraction roles, whatever it looked like
    root = build(op("Div", [X(), N(2, 4)], 0, 5), N(3, 8))
    left = root["children"][0]
    assert (left["type"], left["role"]) == ("Div", "left_side")
    assert [c["role"] for c in left["children"]] == ["variable", "denominator"]
    inner = build(op("Add", [op("Div", [X(), N(2, 4)], 0, 5), N(1, 8)], 0, 9), N(3, 12))
    div = inner["children"][0]["children"][0]
    assert (div["type"], div["role"], div["spoken_quick"]) == ("Div", "fraction", "Fraction")


# ---- 5. Explanation quality across the new nodes -----------------------------------


def test_all_new_roles_have_non_empty_three_depth_text():
    seen = set()
    for name in NEW_FIXTURES:
        for n in flat(tree(name)):
            seen.add(n["role"])
            for key in ("spoken_quick", "spoken_detailed", "spoken_context"):
                assert n[key].strip(), (name, n["id"], key)
    assert {"group", "group_multiplier", "power", "exponent", "fraction"} <= seen


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_no_math_symbols_or_placeholders_in_new_text(name):
    for n in flat(tree(name)):
        text = spoken(n)
        assert not any(ch in text for ch in SYMBOLS), (name, n["id"], text)
        assert "None" not in text and "{" not in text and "}" not in text


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_new_nodes_are_not_identical_in_context(name):
    contexts = [n["spoken_context"] for n in flat(tree(name)) if n["role"] != "equation"]
    # x and the like can legitimately repeat only when they are different nodes
    # with different parents; within one fixture no two contexts may be equal
    assert len(contexts) == len(set(contexts)), name


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_quick_text_stays_short(name):
    for n in flat(tree(name)):
        assert len(n["spoken_quick"].split()) <= 4, (name, n["spoken_quick"])


def test_quick_text_is_exact_for_every_new_role():
    quick = {}
    for name in ("2(x+3)=12", "x^2+3=7", "(x+1)/2=3"):
        for n in flat(tree(name)):
            quick.setdefault(n["role"], set()).add(n["spoken_quick"])
    assert quick["group"] == {"Group"}
    assert quick["group_multiplier"] == {"Multiplier 2"}
    assert quick["power"] == {"Power"}
    assert quick["exponent"] == {"Exponent 2"}
    assert quick["denominator"] == {"Denominator 2"}


def test_equation_text_reads_the_new_structures():
    assert tree("2(x+3)=12")["spoken_detailed"] == (
        "The whole equation. It says that the left side, 2 times the group x plus 3 "
        "end group, has the same value as the right side, 12."
    )
    assert tree("(x+1)/2=3")["spoken_detailed"] == (
        "The whole equation. It says that the left side, the fraction with numerator "
        "x plus 1 and denominator 2, has the same value as the right side, 3."
    )


def test_group_times_group_phrase_has_a_pause():
    assert "the group x plus 1 end group times the group x minus 2 end group" in (
        tree("(x+1)(x-2)=0")["spoken_detailed"]
    )


def test_group_in_the_denominator_and_numerator():
    # (x + 1)/(x - 2) style: Div(Group, Group)
    g1 = G(op("Add", [X(1), N(1, 5)], 1, 6), 0, 7)
    g2 = G(op("Sub", [X(9), N(2, 13)], 9, 14), 8, 15)
    root = build(Fr(g1, g2, 0, 15), N(3, 18))
    frac = root["children"][0]
    n, d = frac["children"]
    assert (n["role"], d["role"]) == ("group", "group")
    assert "It is the numerator of a fraction whose denominator is the group x minus 2." in (
        n["spoken_detailed"]
    )
    assert "It is the denominator of a fraction whose numerator is the group x plus 1." in (
        d["spoken_detailed"]
    )
    assert "the quantity" not in frac["spoken_detailed"]


# ---- 6. Malformed Group, Pow and Div ----------------------------------------


def test_group_with_no_children_rejected():
    with pytest.raises(ExplorerError, match=r"Group needs 1 child\(ren\), found 0"):
        build(G(x_plus_3()) | {"children": []}, N(5, 11))


def test_group_with_two_children_rejected():
    bad = G(x_plus_3()) | {"children": [x_plus_3(), N(1, 9)]}
    with pytest.raises(ExplorerError, match=r"Group needs 1 child\(ren\), found 2"):
        build(bad, N(5, 11))


def test_group_must_not_have_a_value():
    with pytest.raises(ExplorerError, match="Group must not have a 'value'"):
        build(G(x_plus_3()) | {"value": 3}, N(5, 11))


def test_group_bad_span_rejected():
    for span in ([3, 3], [-1, 4], [1], "ab"):
        with pytest.raises(ExplorerError, match="span"):
            build(G(x_plus_3()) | {"span": span}, N(5, 11))


def test_group_missing_keys_rejected():
    for missing in ("type", "children", "span"):
        bad = G(x_plus_3())
        del bad[missing]
        with pytest.raises(ExplorerError, match=f"missing '{missing}'"):
            build(bad, N(5, 11))


def test_group_child_must_be_a_node():
    with pytest.raises(ExplorerError, match=r"children\[0\]: node must be a dict"):
        build(G(x_plus_3()) | {"children": ["x + 3"]}, N(5, 11))


def test_group_cannot_contain_an_equation():
    inner = equation(X(), N(1, 4), 5)
    with pytest.raises(ExplorerError, match="an Equation can only be the root"):
        build(G(inner), N(5, 11))


def test_error_inside_a_group_reports_the_full_path():
    bad = G(op("Add", [X(2), {"type": "Sqrt", "children": [], "span": [5, 6]}], 2, 7))
    with pytest.raises(ExplorerError, match=r"ast\.children\[0\]\.children\[0\]\.children\[1\]"):
        build(bad, N(5, 11))


@pytest.mark.parametrize("n_children", [0, 1, 3])
def test_pow_needs_exactly_two_children(n_children):
    kids = [X(), N(2, 2), N(3, 4)][:n_children]
    with pytest.raises(ExplorerError, match=rf"Pow needs 2 child\(ren\), found {n_children}"):
        build(op("Pow", kids, 0, 5), N(4, 8))


def test_pow_must_not_have_a_value():
    bad = Pw(X(), N(2, 2)) | {"value": 2}
    with pytest.raises(ExplorerError, match="Pow must not have a 'value'"):
        build(bad, N(4, 8))


@pytest.mark.parametrize("n_children", [0, 1, 3])
def test_fraction_needs_exactly_two_children(n_children):
    kids = [N(1), N(2, 2), N(3, 4)][:n_children]
    with pytest.raises(ExplorerError, match=rf"Div needs 2 child\(ren\), found {n_children}"):
        build(Fr(N(1), N(2, 2)) | {"children": kids}, N(4, 8))


def test_fraction_must_not_have_a_value():
    with pytest.raises(ExplorerError, match="Div must not have a 'value'"):
        build(Fr(N(1), N(2, 2)) | {"value": 1}, N(4, 8))


def test_fraction_child_errors_report_the_path():
    bad = Fr(N(1), {"type": "Number", "value": "two", "children": [], "span": [2, 3]})
    with pytest.raises(ExplorerError, match=r"ast\.children\[0\]\.children\[1\]: Number 'value' 'two'"):
        build(bad, N(4, 8))


def test_fraction_with_a_missing_span_rejected():
    bad = Fr(N(1), N(2, 2))
    del bad["span"]
    with pytest.raises(ExplorerError, match="missing 'span'"):
        build(bad, N(4, 8))


def test_group_as_the_root_is_rejected():
    with pytest.raises(ExplorerError, match="the root must be an Equation, got Group"):
        build_explorer_tree(G(x_plus_3()))


def test_unsupported_nodes_next_to_new_ones_are_still_rejected():
    for bad_type in ("Sqrt", "Abs", "Paren"):
        bad = {"type": bad_type, "children": [N(1)], "span": [0, 3]}
        with pytest.raises(ExplorerError, match=f"unsupported node type '{bad_type}'"):
            build(op("Mul", [N(2), bad], 0, 4), N(4, 8))


# ---- 7. Spans, ids and purity on the new structures --------------------------------


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_new_fixtures_preserve_order_and_drop_spans(name):
    def check(ast, ex):
        assert "span" not in ex
        assert ex["type"] == ast["type"]
        assert len(ex["children"]) == len(ast["children"])
        for a, e in zip(ast["children"], ex["children"]):
            check(a, e)
    ast = FIXTURES[name][1]
    check(ast, tree(name))


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_new_fixtures_ids_are_unique_stable_and_path_based(name):
    ids = [n["id"] for n in flat(tree(name))]
    assert len(ids) == len(set(ids))
    assert ids == [n["id"] for n in flat(tree(name))]
    assert ids[0] == "n0"

    def check(node):
        for i, c in enumerate(node["children"]):
            assert c["id"] == f"{node['id']}.{i}"
            check(c)
    check(tree(name))


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_new_fixtures_are_not_modified_and_are_deterministic(name):
    ast = copy.deepcopy(FIXTURES[name][1])
    before = copy.deepcopy(ast)
    first = build_explorer_tree(ast)
    assert ast == before
    assert first == build_explorer_tree(ast)
    for n in flat(first):
        assert set(n) == EXPLORER_FIELDS


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_new_fixture_node_values_are_preserved(name):
    def values(ast):
        yield ast.get("value")
        for c in ast["children"]:
            yield from values(c)
    ast = FIXTURES[name][1]
    assert list(values(ast)) == [n["value"] for n in flat(tree(name))]


def test_spans_of_group_fixture_slice_to_the_expected_text():
    # AST fixtures only: spans are input and do not appear in the explorer output
    source, ast = FIXTURES["x^2+3=7"]
    pow_node = ast["children"][0]["children"][0]
    assert source[slice(*pow_node["span"])] == "x^2"
    assert source[slice(*pow_node["children"][1]["span"])] == "2"
    source, ast = FIXTURES["(x+1)/2=3"]
    frac = ast["children"][0]
    assert source[slice(*frac["span"])] == "(x + 1)/2"
    assert source[slice(*frac["children"][1]["span"])] == "2"


def test_nested_group_fixture_spans_nest():
    source, root = FIXTURES["2(3(x+1)+4)=20"]
    outer = root["children"][0]["children"][1]
    inner = outer["children"][0]["children"][0]["children"][1]
    assert source[slice(*outer["span"])] == "(3(x + 1) + 4)"
    assert source[slice(*inner["span"])] == "(x + 1)"
    assert outer["span"][0] < inner["span"][0] and inner["span"][1] < outer["span"][1]


# ---- 8. Phase 1 behaviour is unchanged -----------------------------------------------


def test_phase_1_trees_are_still_the_same():
    root = tree("3x+5=14")
    assert [(n["id"], n["role"], n["spoken_quick"]) for n in flat(root)] == [
        ("n0", "equation", "Equation"),
        ("n0.0", "left_side", "Left side"),
        ("n0.0.0", "operator", "Multiplication"),
        ("n0.0.0.0", "coefficient", "Coefficient 3"),
        ("n0.0.0.1", "variable", "Variable x"),
        ("n0.0.1", "constant", "Constant term 5"),
        ("n0.1", "right_side", "Right side"),
    ]
    assert root["children"][0]["children"][0]["children"][0]["spoken_context"] == (
        "The coefficient 3 belongs to the variable x: x is multiplied by 3. "
        "Together they form the term 3x."
    )


def test_phase_1_power_phrase_still_uses_to_the_power_of():
    # general sub-expression wording is unchanged; "squared" appears only in a
    # Power node's own explanation
    root = build(op("Add", [Pw(X(), N(2, 2)), N(3, 6)], 0, 7), N(7, 10))
    assert "x to the power of 2, plus 3" in root["children"][0]["spoken_detailed"]
    assert "squared" not in root["children"][0]["spoken_detailed"]


def test_subtracting_a_sum_and_multiplying_a_sum_without_group_nodes_still_say_quantity():
    root = build(op("Mul", [N(2), op("Add", [X(2), N(3, 6)], 2, 7)], 0, 8), N(12, 11))
    assert "2 times the quantity x plus 3" in root["children"][0]["spoken_detailed"]
    # and a plain number times an unwrapped sum is NOT given the group-multiplier role
    assert by_role(root, "group_multiplier") == []


# ===========================================================================
# Part 9: review hardening (depth, numbers, roles, nesting, fuzzing)
# ===========================================================================
# These tests were added after a full review of engine/explore.py. Tests marked
# xfail(strict=True) record a KNOWN weakness that needs a design decision; they
# turn into failures the moment the weakness is fixed, so the marker gets removed.

ALLOWED_ROLES = {
    "equation", "left_side", "right_side", "coefficient", "variable",
    "constant", "operator", "group", "group_multiplier", "power", "base",
    "exponent", "fraction", "numerator", "denominator", "number",
}
OPERATOR_TYPES = {"Add", "Sub", "Mul", "Div", "Neg"}
SPOKEN_KEYS = ("spoken_quick", "spoken_detailed", "spoken_context")
JS_PATH = Path(__file__).parent.parent / "static" / "explorer_keys.js"


def check_against_ast(ast, root):
    """Invariants that must hold for ANY accepted input: same shape, path ids,
    verbatim values (no span), non-empty spoken text with no symbols or
    leaked Python values."""
    seen = set()

    def visit(a, n, expected_id):
        assert set(n) == EXPLORER_FIELDS
        assert n["id"] == expected_id
        assert n["id"] not in seen
        seen.add(n["id"])
        assert (n["type"], n["value"]) == (a["type"], a.get("value"))
        assert "span" not in n
        assert n["role"] in ALLOWED_ROLES
        assert len(n["children"]) == len(a["children"])
        for key in SPOKEN_KEYS:
            text_ = n[key]
            assert isinstance(text_, str) and text_ and text_ == text_.strip(), (n["id"], key)
            assert not any(sym in text_ for sym in SYMBOLS), (n["id"], key, text_)
            assert not re.search(r"\b(None|nan|inf)\b|[{}\[\]]", text_), (n["id"], key, text_)
        for i, (ca, cn) in enumerate(zip(a["children"], n["children"])):
            visit(ca, cn, f"{expected_id}.{i}")

    visit(ast, root, "n0")


def is_variable_or_powered(node):
    """x, or x raised to a power (a number multiplying either is a coefficient)."""
    return node["type"] == "Variable" or (
        node["type"] == "Pow" and node["children"][0]["type"] == "Variable"
    )


def check_roles(root):
    """Role rules from plan 7.6 / guide A1-A6, checked on every node."""

    def top_of_negations(parent_chain):
        # the nearest ancestor that is not a Neg
        for anc in reversed(parent_chain):
            if anc["type"] != "Neg":
                return anc
        return None

    def visit(n, chain, index):
        parent = chain[-1] if chain else None
        other = None
        if parent is not None and len(parent["children"]) == 2:
            other = parent["children"][1 - index]
        t, role = n["type"], n["role"]
        if parent is None:
            assert role == "equation"
        elif parent["type"] == "Equation":
            assert role == ("left_side", "right_side")[index]
        elif t == "Variable":
            assert role == "variable"
        elif t == "Group":
            assert role == "group"
        elif t == "Pow":
            assert role == "power"
        elif t == "Div":
            assert role == "fraction"
        elif t in OPERATOR_TYPES:
            assert role == "operator"
        else:
            assert t == "Number"
            if parent["type"] == "Pow":
                assert role == ("base", "exponent")[index]
            elif parent["type"] == "Div":
                assert role == ("numerator", "denominator")[index]
            elif parent["type"] == "Mul" and is_variable_or_powered(other):
                assert role == "coefficient"
            elif parent["type"] == "Mul" and other["type"] == "Group":
                assert role == "group_multiplier"
            else:
                holder = top_of_negations(chain)
                in_sum = holder is not None and holder["type"] in ("Add", "Sub", "Equation")
                assert role == ("constant" if in_sum else "number")
        # the converse: the special roles appear nowhere else
        if role == "coefficient":
            assert t == "Number" and parent["type"] == "Mul" and is_variable_or_powered(other)
        if role == "group_multiplier":
            assert t == "Number" and parent["type"] == "Mul" and other["type"] == "Group"
        if role in ("base", "exponent"):
            assert t == "Number" and parent["type"] == "Pow"
        if role in ("numerator", "denominator"):
            assert t == "Number" and parent["type"] == "Div"
        if role in ("left_side", "right_side"):
            assert parent is not None and parent["type"] == "Equation"
        for i, c in enumerate(n["children"]):
            visit(c, chain + [n], i)

    visit(root, [], 0)


# ---- generators -------------------------------------------------------------


def _random_ast(rng, depth, counter):
    """A random well-formed expression using every supported node type."""

    def span():
        counter[0] += 1
        return [counter[0], counter[0] + 1]

    def leafnode():
        if rng.random() < 0.45:
            return {"type": "Variable", "value": "x", "children": [], "span": span()}
        value = rng.choice(["0", "1", "2", "3", "5", "12", "2.5", "0.5", "4.0", "007"])
        return {"type": "Number", "value": value, "children": [], "span": span()}

    if depth <= 0 or rng.random() < 0.25:
        return leafnode()
    kind = rng.choice(["Add", "Sub", "Mul", "Div", "Pow", "Neg", "Group", "Div"])
    n_children = 1 if kind in ("Neg", "Group") else 2
    kids = [_random_ast(rng, depth - 1, counter) for _ in range(n_children)]
    lo = min(k["span"][0] for k in kids)
    hi = max(k["span"][1] for k in kids)
    return {"type": kind, "children": kids, "span": [lo, hi]}


def random_equation(seed):
    rng = random.Random(seed)
    counter = [0]
    left = _random_ast(rng, 5, counter)
    right = _random_ast(rng, 3, counter)
    return {
        "type": "Equation",
        "children": [left, right],
        "span": [min(left["span"][0], right["span"][0]), counter[0] + 2],
    }


def chain_equation(levels, kind):
    """An equation whose explorer tree is exactly `levels` deep (Equation = 1)."""
    node = {"type": "Variable", "value": "x", "children": [], "span": [0, 1]}
    one = {"type": "Number", "value": "1", "children": [], "span": [0, 1]}
    # levels: Equation + `wraps` operators + the leaf
    for _ in range(levels - 2):
        if kind == "left":
            node = {"type": "Add", "children": [node, dict(one)], "span": [0, 1]}
        elif kind == "right":
            node = {"type": "Add", "children": [dict(one), node], "span": [0, 1]}
        elif kind == "group":
            node = {"type": "Group", "children": [node], "span": [0, 1]}
        else:
            node = {"type": "Pow", "children": [node, dict(one)], "span": [0, 1]}
    return {"type": "Equation", "children": [node, dict(one)], "span": [0, 1]}


def tree_depth(node):
    return 1 + max((tree_depth(c) for c in node["children"]), default=0)


# ---- 9.1 depth limit (matches the keyboard module) ---------------------------


def test_python_depth_limit_matches_the_keyboard_module():
    source = JS_PATH.read_text(encoding="utf-8")
    match = re.search(r"var MAX_DEPTH = (\d+);", source)
    assert match, "MAX_DEPTH not found in static/explorer_keys.js"
    assert MAX_DEPTH == int(match.group(1))


@pytest.mark.parametrize("kind", ["left", "right", "group", "pow"])
def test_tree_exactly_at_the_depth_limit_builds_with_full_text(kind):
    ast = chain_equation(MAX_DEPTH, kind)
    root = build_explorer_tree(ast)
    assert tree_depth(root) == MAX_DEPTH
    check_against_ast(ast, root)
    check_roles(root)


@pytest.mark.parametrize("kind", ["left", "right", "group", "pow"])
def test_tree_one_level_too_deep_is_an_explorer_error(kind):
    with pytest.raises(ExplorerError, match=f"more than {MAX_DEPTH} levels"):
        build_explorer_tree(chain_equation(MAX_DEPTH + 1, kind))


def test_very_deep_tree_is_an_explorer_error_not_a_recursion_error():
    with pytest.raises(ExplorerError):
        build_explorer_tree(chain_equation(3000, "left"))


def test_cyclic_ast_is_an_explorer_error_not_a_recursion_error():
    loop = {"type": "Add", "children": [], "span": [0, 1]}
    loop["children"] = [loop, {"type": "Number", "value": "1", "children": [], "span": [0, 1]}]
    ast = {"type": "Equation", "children": [loop, N(2)], "span": [0, 5]}
    with pytest.raises(ExplorerError, match="levels deep"):
        build_explorer_tree(ast)


def test_deep_error_reports_the_path_of_the_node_that_is_too_deep():
    with pytest.raises(ExplorerError, match=r"ast(\.children\[\d\])+: the tree is more than"):
        build_explorer_tree(chain_equation(MAX_DEPTH + 5, "left"))


# ---- 9.2 numeric edge cases ----------------------------------------------------


@pytest.mark.parametrize("bad", [
    float("nan"), float("inf"), float("-inf"),   # not strings
    "nan", "inf", "-inf", "Infinity", "NaN",     # strings, but not numbers
])
def test_non_finite_numbers_are_rejected(bad):
    for place in ("term", "exponent"):
        num = leaf("Number", 0, 1, bad)
        left = op("Add", [X(), num], 0, 4) if place == "term" else Pw(X(), num)
        with pytest.raises(ExplorerError, match="Number"):
            build_explorer_tree(eq(left, N(1, 8)))


@pytest.mark.parametrize("spelling", [
    "3", "14", "0", "007", "2.5", "2.50", "4.0", ".5", "5.", "123456789012345678901234567890",
])
def test_valid_number_spellings_are_kept_exactly(spelling):
    root = build(op("Add", [X(), N(spelling, 4)], 0, 8), N("1", 12))
    number = root["children"][0]["children"][1]
    assert number["value"] == spelling
    assert spelling in number["spoken_quick"]


@pytest.mark.parametrize("spelling", [
    "", " ", "3 ", " 3", "-3", "+3", "1e3", "1E3", "0x10", "1,000", "1_000", "1/2", "..5", ".",
    "1.2.3", "3x", "\u0663", "\uff13", "٣", "3\n", "\n3", "nan", "inf", "x",
])
def test_invalid_number_spellings_are_rejected(spelling):
    bad = {"type": "Number", "value": spelling, "children": [], "span": [0, 1]}
    with pytest.raises(ExplorerError, match=r"ast\.children\[0\]\.children\[1\]: Number"):
        build(op("Add", [X(), bad], 0, 4), N("1", 8))


def test_huge_integer_exponent_does_not_overflow():
    big = "9" * 5000  # longer than Python's int-to-string limit; kept as text
    root = build(Pw(X(), N(big, 2)), N(1, 8))
    power = root["children"][0]
    assert power["role"] == "left_side"
    assert power["children"][1]["role"] == "exponent"
    assert "factor" in power["spoken_detailed"]


@pytest.mark.parametrize("value, expect_factor_words", [
    ("0", False), ("1", False), ("2.0", False), ("4", True), ("4.0", True), ("7", True),
])
def test_exponent_wording_is_exact_for_small_integers(value, expect_factor_words):
    root = build(Pw(X(), N(value, 2)), N(1, 8))
    power = root["children"][0]
    detailed = power["spoken_detailed"]
    if value in ("2", "2.0"):
        assert "x squared means x is multiplied by itself" in detailed
    elif expect_factor_words:
        assert f"used as a factor {value} times" in detailed  # source spelling
    else:
        assert "multiplied by itself" not in detailed
        assert "factor" not in detailed
        assert f"x is raised to the power {value}" in detailed


def test_negated_base_is_marked_as_a_quantity():
    root = build(Pw(Ng(N(2, 1)), N(2, 4), 0, 5), N(4, 8))
    power = root["children"][0]
    assert power["children"][0]["role"] == "operator"  # a Neg node, not a bare number
    assert "The base is the quantity negative 2" in power["spoken_detailed"]
    # x - 2 and x + (-2) must not be spoken the same way
    sub = build(op("Sub", [X(), N(2, 4)], 0, 5), N(0, 8))["children"][0]["spoken_detailed"]
    add = build(op("Add", [X(), Ng(N(2, 5))], 0, 6), N(0, 9))["children"][0]["spoken_detailed"]
    assert "x minus 2" in sub and "x plus negative 2" in add


# ---- 9.3 roles: exact maps for the review fixtures ------------------------------

EXPECTED_ROLES = {
    "2(x+3)^2-(x-1)/4=5": {
        "n0": "equation", "n0.0": "left_side", "n0.0.0": "operator",
        "n0.0.0.1": "power", "n0.0.0.1.0": "group", "n0.0.0.1.0.0": "operator",
        "n0.0.0.1.0.0.0": "variable", "n0.0.0.1.0.0.1": "constant",
        "n0.0.0.1.1": "exponent", "n0.0.1": "fraction", "n0.0.1.0": "operator",
        "n0.0.1.0.0": "variable", "n0.0.1.0.1": "constant",
        "n0.0.1.1": "denominator", "n0.1": "right_side",
    },
    "((x+1)(x-2)+3)^2=16": {
        "n0.0": "left_side", "n0.0.0": "group", "n0.0.0.0": "operator",
        "n0.0.0.0.0": "operator",
        # two groups multiplied: neither is a multiplier (that needs a number)
        "n0.0.0.0.0.0": "group", "n0.0.0.0.0.0.0": "operator",
        "n0.0.0.0.0.0.0.0": "variable", "n0.0.0.0.0.0.0.1": "constant",
        "n0.0.0.0.0.1": "group", "n0.0.0.0.0.1.0": "operator",
        "n0.0.0.0.0.1.0.0": "variable", "n0.0.0.0.0.1.0.1": "constant",
        "n0.0.0.0.1": "constant", "n0.0.1": "exponent", "n0.1": "right_side",
    },
    "3x^2-2x+1=-(x-4)": {
        "n0.0": "left_side", "n0.0.0": "operator", "n0.0.0.0": "operator",
        "n0.0.0.0.1": "power", "n0.0.0.0.1.0": "variable",
        "n0.0.0.0.1.1": "exponent", "n0.0.0.1": "operator",
        "n0.0.0.1.0": "coefficient", "n0.0.0.1.1": "variable",
        "n0.0.1": "constant", "n0.1": "right_side", "n0.1.0": "group",
        "n0.1.0.0": "operator", "n0.1.0.0.0": "variable",
        "n0.1.0.0.1": "constant",
    },
    "(2x+1)/(x-3)=4": {
        # a Div that is a whole side takes the side role (guide A2)
        "n0.0": "left_side",
        # a non-number numerator/denominator keeps its own role (guide A6)
        "n0.0.0": "operator", "n0.0.0.0": "operator", "n0.0.0.0.0": "coefficient",
        "n0.0.0.0.1": "variable", "n0.0.0.1": "constant",
        "n0.0.1": "operator", "n0.0.1.0": "variable", "n0.0.1.1": "constant",
        "n0.1": "right_side",
    },
    "((x+1)/2+3)/4=1": {
        "n0.0": "left_side", "n0.0.0": "operator", "n0.0.0.0": "fraction",
        "n0.0.0.0.0": "operator", "n0.0.0.0.0.0": "variable",
        "n0.0.0.0.0.1": "constant", "n0.0.0.0.1": "denominator",
        "n0.0.0.1": "constant", "n0.0.1": "denominator", "n0.1": "right_side",
    },
    "2(x+1)+3(x-1)=10": {
        "n0.0": "left_side", "n0.0.0": "operator", "n0.0.0.0": "group_multiplier",
        "n0.0.0.1": "group", "n0.0.0.1.0": "operator",
        "n0.0.0.1.0.0": "variable", "n0.0.0.1.0.1": "constant",
        "n0.0.1": "operator", "n0.0.1.0": "group_multiplier", "n0.0.1.1": "group",
        "n0.0.1.1.0": "operator", "n0.0.1.1.0.0": "variable",
        "n0.0.1.1.0.1": "constant", "n0.1": "right_side",
    },
    "(x^2+1)^3=8": {
        "n0.0": "left_side", "n0.0.0": "group", "n0.0.0.0": "operator",
        "n0.0.0.0.0": "power", "n0.0.0.0.0.0": "variable",
        "n0.0.0.0.0.1": "exponent", "n0.0.0.0.1": "constant",
        "n0.0.1": "exponent", "n0.1": "right_side",
    },
}


@pytest.mark.parametrize("name", REVIEW_FIXTURES)
def test_review_fixture_roles_are_exactly_as_expected(name):
    root = build_explorer_tree(REVIEW_FIXTURES[name][1])
    actual = {n["id"]: n["role"] for n in flat(root)}
    expected = EXPECTED_ROLES[name]
    assert {i: actual[i] for i in expected} == expected


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_every_fixture_satisfies_the_general_invariants(name):
    ast = ALL_FIXTURES[name][1]
    root = build_explorer_tree(ast)
    check_against_ast(ast, root)
    check_roles(root)


@pytest.mark.parametrize("name", REVIEW_FIXTURES)
def test_review_fixture_shape_and_spans(name):
    source, ast = REVIEW_FIXTURES[name]
    assert ast["span"] == [0, len(source)]
    for node in (n for n in flat_ast(ast)):
        start, end = node["span"]
        assert 0 <= start < end <= len(source)
        assert node["type"] in FIXTURE_NODE_TYPES
        if node["type"] in {"Number", "Variable"}:
            assert node["children"] == [] and "value" in node
        else:
            assert node["children"] and "value" not in node
        starts = [c["span"][0] for c in node["children"]]
        assert starts == sorted(starts)
        for child in node["children"]:
            assert start <= child["span"][0] and child["span"][1] <= end


def flat_ast(node):
    yield node
    for c in node["children"]:
        yield from flat_ast(c)


def test_review_fixture_spans_slice_to_the_expected_text():
    src, ast = REVIEW_FIXTURES["2(x+3)^2-(x-1)/4=5"]
    left = ast["children"][0]
    mul, fraction = left["children"]
    assert src[slice(*mul["span"])] == "2(x + 3)^2"
    assert src[slice(*fraction["span"])] == "(x - 1)/4"
    assert src[slice(*fraction["children"][0]["span"])] == "x - 1"  # brackets excluded
    src, ast = REVIEW_FIXTURES["(2x+1)/(x-3)=4"]
    num, den = ast["children"][0]["children"]
    assert (src[slice(*num["span"])], src[slice(*den["span"])]) == ("2x + 1", "x - 3")


# ---- 9.4 roles and invariants on many random trees --------------------------------


@pytest.mark.parametrize("seed", range(150))
def test_random_trees_keep_roles_ids_spans_and_text_consistent(seed):
    ast = random_equation(seed)
    before = copy.deepcopy(ast)
    root = build_explorer_tree(ast)
    assert ast == before  # input untouched
    check_against_ast(ast, root)
    check_roles(root)
    assert build_explorer_tree(ast) == root  # deterministic


@pytest.mark.parametrize("seed", range(40))
def test_random_trees_never_say_the_same_context_twice_in_one_sibling_group(seed):
    root = build_explorer_tree(random_equation(seed + 1000))
    for node in flat(root):
        kids = node["children"]
        if len(kids) == 2 and kids[0]["type"] != kids[1]["type"]:
            assert kids[0]["spoken_context"] != kids[1]["spoken_context"]


# ---- 9.5 group multipliers, powers and fractions in many positions -------------------


def test_group_multiplier_on_the_right_side():
    group = G(x_plus_3())
    root = build(N(10, 0), op("Mul", [N(2, 4), group], 4, 12))
    right = root["children"][1]
    two, grp = right["children"]
    assert (right["role"], two["role"], grp["role"]) == ("right_side", "group_multiplier", "group")
    assert "It is part of the right side of the equation." in two["spoken_context"]
    assert "left side" not in two["spoken_context"]


def test_group_multiplier_after_a_subtraction():
    # x - 3(x + 1)
    product = op("Mul", [N(3, 4), G(op("Add", [X(6), N(1, 10)], 6, 11), 5, 12)], 4, 12)
    root = build(op("Sub", [X(), product], 0, 12), N(0, 15))
    mul = root["children"][0]["children"][1]
    three, grp = mul["children"]
    assert (three["role"], grp["role"]) == ("group_multiplier", "group")
    assert "is subtracted from the variable x" in mul["spoken_context"]
    assert "multiplies the entire group x plus 1" in three["spoken_context"]


def test_group_multiplier_inside_a_group_inside_a_power():
    # (2(x + 3))^2
    inner = op("Mul", [N(2, 1), G(x_plus_3(), 2, 9)], 1, 9)
    root = build(Pw(G(inner, 0, 10), N(2, 11), 0, 12), N(4, 15))
    multiplier = find(root, "Number", "group_multiplier")
    assert len(multiplier) == 1
    assert multiplier[0]["spoken_context"].startswith("The multiplier 2 multiplies the entire group x plus 3.")


def test_group_multiplier_in_a_fraction_numerator_and_group_holding_a_power():
    # 2(x + 3)/5 with a Div numerator Mul, and 2(x^2 + 1)
    numerator = op("Mul", [N(2, 1), G(x_plus_3(), 2, 9)], 1, 9)
    root = build(Fr(numerator, N(5, 11), 0, 12), N(1, 16))
    two = find(root, "Number", "group_multiplier")[0]
    assert two["id"] == "n0.0.0.0"
    squared = op("Add", [Pw(X(2), N(2, 4), 2, 5), N(1, 8)], 2, 9)
    root = build(op("Mul", [N(2), G(squared, 1, 10)], 0, 10), N(0, 14))
    assert find(root, "Number", "group_multiplier")[0]["spoken_context"].startswith(
        "The multiplier 2 multiplies the entire group x to the power of 2, plus 1."
    )


def test_two_group_multipliers_in_one_sum_each_name_their_own_group():
    root = build_explorer_tree(REVIEW_FIXTURES["2(x+1)+3(x-1)=10"][1])
    two, three = find(root, "Number", "group_multiplier")
    assert "the group x plus 1" in two["spoken_context"]
    assert "x minus 1" not in two["spoken_context"]
    assert "the group x minus 1" in three["spoken_context"]
    assert "x plus 1" not in three["spoken_context"]
    assert two["spoken_context"] != three["spoken_context"]


def test_nested_multipliers_each_belong_to_their_own_group():
    root = tree("2(3(x+1)+4)=20")
    outer, inner = find(root, "Number", "group_multiplier")
    assert outer["spoken_context"].startswith("The multiplier 2 multiplies the entire group 3 times")
    assert inner["spoken_context"].startswith("The multiplier 3 multiplies the entire group x plus 1.")


def test_power_inside_a_group_inside_a_power():
    root = build_explorer_tree(REVIEW_FIXTURES["(x^2+1)^3=8"][1])
    outer = root["children"][0]
    inner = root["children"][0]["children"][0]["children"][0]["children"][0]
    assert inner["role"] == "power" and outer["role"] == "left_side"
    assert "the group x to the power of 2, plus 1 end group to the power of 3" in root["spoken_detailed"]
    assert "cubed means" in outer["spoken_detailed"]
    assert "x squared means x is multiplied by itself" in inner["spoken_detailed"]
    assert "belongs to the base x" in inner["children"][1]["spoken_context"]
    # the 2 and the 3 are told apart
    exponents = find(root, "Number", "exponent")
    assert [e["spoken_quick"] for e in exponents] == ["Exponent 2", "Exponent 3"]
    assert exponents[0]["spoken_context"] != exponents[1]["spoken_context"]


def test_fraction_with_compound_numerator_and_denominator():
    root = build_explorer_tree(REVIEW_FIXTURES["(2x+1)/(x-3)=4"][1])
    assert "the fraction with numerator 2x plus 1 and denominator x minus 3" in root["spoken_detailed"]
    fraction = root["children"][0]
    assert "the fraction means the quantity 2x plus 1 divided by the quantity x minus 3" in (
        fraction["spoken_detailed"]
    )
    numerator, denominator = fraction["children"]
    assert "numerator of a fraction whose denominator is x minus 3" in numerator["spoken_detailed"]
    assert "denominator of a fraction whose numerator is 2x plus 1" in denominator["spoken_detailed"]


def test_fraction_nested_in_a_numerator_names_both_fractions():
    root = build_explorer_tree(REVIEW_FIXTURES["((x+1)/2+3)/4=1"][1])
    outer = root["children"][0]
    inner = find(root, "Div", "fraction")[0]
    assert inner["id"] == "n0.0.0.0"
    assert "x plus 1 as its numerator and 2 as its denominator" in inner["spoken_detailed"]
    assert "is added to the constant 3" in inner["spoken_context"]
    assert "as its numerator and 4 as its denominator" in outer["spoken_detailed"]
    assert inner["spoken_context"] != outer["spoken_context"]


def test_fraction_with_negated_denominator_and_negated_numerator():
    root = build(Fr(Ng(N(3, 1)), Ng(N(2, 4)), 0, 6), N(1, 10))
    num, den = root["children"][0]["children"]
    assert (num["spoken_quick"], den["spoken_quick"]) == ("Negation", "Negation")
    assert "the fraction with numerator negative 3 and denominator negative 2" in root["spoken_detailed"]


# ---- 9.6 subtraction, negatives, division: wording stays mathematically exact ---------


def test_subtraction_chain_and_nested_subtraction_read_differently():
    chain = build(op("Sub", [op("Sub", [X(), N(2, 4)], 0, 5), N(3, 8)], 0, 9), N(0, 12))
    nested = build(op("Sub", [X(), op("Sub", [N(2, 4), N(3, 8)], 4, 9)], 0, 9), N(0, 12))
    assert "x minus 2 minus 3," in chain["spoken_detailed"]
    assert "x minus the quantity 2 minus 3," in nested["spoken_detailed"]
    # direction: the second part is taken away from the first
    assert "takes the constant 3 away from the difference x minus 2" in chain["children"][0]["spoken_detailed"]
    assert "takes the difference 2 minus 3 away from the variable x" in nested["children"][0]["spoken_detailed"]


def test_subtracting_a_negation_is_not_adding():
    sub = build(op("Sub", [X(), Ng(N(3, 5))], 0, 6), N(0, 9))
    left = sub["children"][0]
    neg = left["children"][1]
    assert (neg["type"], neg["role"]) == ("Neg", "operator")
    assert neg["children"][0]["role"] == "constant"  # still a term of the difference
    assert "x minus negative 3" in sub["spoken_detailed"]
    assert "the negation of 3 away from the variable x" in left["spoken_detailed"]


def test_negated_variable_and_negated_group():
    root = build(op("Neg", [X(1)], 0, 2), N(4, 6))
    neg = root["children"][0]
    assert (neg["role"], neg["type"]) == ("left_side", "Neg")
    assert "It reads negative x. Negation. It changes the sign of the variable x." in neg["spoken_detailed"]
    assert neg["children"][0]["spoken_context"].startswith("The variable x has its sign changed.")
    root = build_explorer_tree(REVIEW_FIXTURES["3x^2-2x+1=-(x-4)"][1])
    right = root["children"][1]
    assert "negative the group x minus 4" in right["spoken_detailed"]
    assert right["children"][0]["role"] == "group"
    assert "The entire group has its sign changed." in right["children"][0]["spoken_detailed"]


def test_division_of_two_groups_keeps_direction():
    divided = op("Div", [G(x_plus_3(), 0, 7), G(op("Sub", [X(10), N(1, 14)], 10, 15), 9, 16)], 0, 16)
    root = build(divided, N(2, 20))
    top, bottom = root["children"][0]["children"]
    assert top["role"] == bottom["role"] == "group"
    assert (
        "the fraction with numerator the group x plus 3 end group and denominator "
        "the group x minus 1 end group"
    ) in root["spoken_detailed"]
    assert "numerator of a fraction whose denominator is the group x minus 1" in top["spoken_detailed"]
    assert "denominator of a fraction whose numerator is the group x plus 3" in bottom["spoken_detailed"]


def test_division_gets_the_fraction_roles():
    root = build(op("Div", [X(), N(2, 4)], 0, 5), N(3, 8))
    div = root["children"][0]
    assert div["children"][1]["role"] == "denominator"
    assert len(find(root, "Number", "denominator")) == 1


def test_like_terms_and_repeated_numbers_are_told_apart():
    # 2(x + 1) + 3(x - 1): the 1s and the x's appear twice, ids and text must differ
    root = build_explorer_tree(REVIEW_FIXTURES["2(x+1)+3(x-1)=10"][1])
    ones = [n for n in flat(root) if n["type"] == "Number" and n["value"] == "1"]
    assert len(ones) == 2
    assert ones[0]["spoken_detailed"] != ones[1]["spoken_detailed"]
    assert ones[0]["spoken_context"] != ones[1]["spoken_context"]


# ---- 9.7 many structures at once --------------------------------------------------------


def test_everything_combined_reads_in_the_right_order():
    root = build_explorer_tree(REVIEW_FIXTURES["2(x+3)^2-(x-1)/4=5"][1])
    assert root["spoken_detailed"] == (
        "The whole equation. It says that the left side, 2 times the group x plus 3 "
        "end group to the power of 2, minus the fraction with numerator x minus 1 and "
        "denominator 4, has the same value as the right side, 5."
    )
    fraction = find(root, "Div", "fraction")[0]
    assert fraction["spoken_context"].startswith(
        "The fraction with numerator x minus 1 and denominator 4 is subtracted from "
        "the product 2 times the group x plus 3, to the power of 2."
    )
    power = find(root, "Pow", "power")[0]
    assert "is multiplied by the number 2" in power["spoken_context"]


def test_nested_groups_inside_a_power_inside_an_equation():
    root = build_explorer_tree(REVIEW_FIXTURES["((x+1)(x-2)+3)^2=16"][1])
    groups = find(root, "Group", "group")
    assert [g["id"] for g in groups] == ["n0.0.0", "n0.0.0.0.0.0", "n0.0.0.0.0.1"]
    outer, first, second = groups
    assert "It is the base, raised to the power 2." in outer["spoken_detailed"]
    assert "The entire group is multiplied by the group x minus 2." in first["spoken_detailed"]
    assert "The entire group is multiplied by the group x plus 1." in second["spoken_detailed"]
    assert len({g["spoken_context"] for g in groups}) == 3
    assert find(root, "Number", "group_multiplier") == []


def test_deeply_nested_groups_inside_the_limit_stay_distinct():
    # ((((((x + 1)))))) = 3, six groups deep
    node = op("Add", [X(), N(1, 4)], 0, 5)
    for i in range(6):
        node = G(node, 0, 5 + i)
    root = build(node, N(3, 20))
    groups = find(root, "Group", "left_side") + find(root, "Group", "group")
    assert len(groups) == 6
    assert len({g["spoken_context"] for g in groups}) == 6
    assert len({g["spoken_detailed"] for g in groups}) == 6
    check_roles(root)


# ---- 9.8 malformed input -----------------------------------------------------------------


def _ast_with(path_to_fault, mutate):
    ast = copy.deepcopy(REVIEW_FIXTURES["2(x+1)+3(x-1)=10"][1])
    node = ast
    for index in path_to_fault:
        node = node["children"][index]
    mutate(node)
    return ast


@pytest.mark.parametrize("path, expected", [
    ((), "ast"),
    ((0,), r"ast\.children\[0\]"),
    ((0, 1), r"ast\.children\[0\]\.children\[1\]"),
    ((0, 1, 1, 0), r"ast\.children\[0\]\.children\[1\]\.children\[1\]\.children\[0\]"),
])
def test_missing_span_is_reported_at_the_right_depth(path, expected):
    ast = _ast_with(path, lambda n: n.pop("span"))
    with pytest.raises(ExplorerError, match=f"{expected}: node is missing 'span'"):
        build_explorer_tree(ast)


@pytest.mark.parametrize("children", [None, (), "ab", {}, 3])
def test_children_that_are_not_a_list_are_rejected(children):
    ast = _ast_with((0,), lambda n: n.__setitem__("children", children))
    with pytest.raises(ExplorerError, match="'children' must be a list"):
        build_explorer_tree(ast)


@pytest.mark.parametrize("bad_child", [None, 3, "x", [], ("Number",), object()])
def test_a_child_that_is_not_a_node_is_rejected_with_its_path(bad_child):
    ast = _ast_with((0,), lambda n: n["children"].__setitem__(1, bad_child))
    with pytest.raises(ExplorerError, match=r"ast\.children\[0\]\.children\[1\]: node must be a dict"):
        build_explorer_tree(ast)


@pytest.mark.parametrize("bad_type", [None, 5, ["Add"], b"Add", {"t": 1}])
def test_a_node_type_that_is_not_a_string_is_rejected(bad_type):
    ast = _ast_with((0, 0), lambda n: n.__setitem__("type", bad_type))
    with pytest.raises(ExplorerError, match="'type' must be a string"):
        build_explorer_tree(ast)


@pytest.mark.parametrize("span", [
    True, False, [True, 2], [0, True], [0.0, 1.0], [1, 1], [2, 1], [-3, -1],
    [None, 1], "01", {"start": 0, "end": 1}, [0, 1, 2], [], range(0, 2),
])
def test_invalid_spans_are_rejected_on_any_node(span):
    ast = _ast_with((0, 1, 1, 0), lambda n: n.__setitem__("span", span))
    with pytest.raises(ExplorerError, match=r"children\[0\]\.children\[1\]\.children\[1\]\.children\[0\]: 'span'"):
        build_explorer_tree(ast)


@pytest.mark.parametrize("node_type", [
    "Power", "Negate", "Paren", "Parenthesis", "Subtract", "Multiply", "Divide",
    "Frac", "Equals", "Eq", "Less", "Call", "Mod", "Log", "equation", "EQUATION",
    "Add ", " Add", "Group2", "Pos",
])
def test_names_other_than_the_agreed_node_types_are_rejected(node_type):
    ast = _ast_with((0, 1, 1), lambda n: n.__setitem__("type", node_type))
    with pytest.raises(ExplorerError, match=r"children\[1\]\.children\[1\]: unsupported node type"):
        build_explorer_tree(ast)


def test_unsupported_type_inside_group_fraction_and_pow_is_reported():
    sqrt = {"type": "Sqrt", "children": [N(4)], "span": [0, 3]}
    for wrapper in (G(sqrt), Fr(sqrt, N(2)), Pw(sqrt, N(2)), op("Neg", [sqrt], 0, 4)):
        with pytest.raises(ExplorerError, match="unsupported node type 'Sqrt'"):
            build_explorer_tree(eq(wrapper, N(1, 8)))


def test_value_on_equation_group_pow_fraction_neg_div_is_rejected():
    for node in (
        G(x_plus_3()), Pw(X(), N(2, 2)), Fr(X(), N(2, 3)), op("Neg", [X(1)], 0, 2),
        op("Div", [X(), N(2, 4)], 0, 5),
    ):
        node = dict(node, value=1)
        with pytest.raises(ExplorerError, match="must not have a 'value'"):
            build_explorer_tree(eq(node, N(1, 8)))
    with pytest.raises(ExplorerError, match="must not have a 'value'"):
        build_explorer_tree(dict(eq(X(), N(1, 8)), value=0))


@pytest.mark.parametrize("value", [3, 2.5, None, [3], ("3",), {"v": 3}, b"3", complex(1, 0), True])
def test_number_values_must_be_strings(value):
    # docs/contracts.md: Number.value is the source spelling, a string
    bad = {"type": "Number", "children": [], "span": [0, 1], "value": value}
    with pytest.raises(ExplorerError, match="source spelling as a string"):
        build_explorer_tree(eq(op("Add", [X(), bad], 0, 3), N(1, 8)))


def test_extra_unknown_keys_are_ignored_and_not_copied():
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    ast["children"][0]["children"][1]["note"] = "parser debug info"
    root = build_explorer_tree(ast)
    assert all(set(n) == EXPLORER_FIELDS for n in flat(root))


def test_tuple_spans_are_accepted():
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    ast["children"][1]["span"] = (9, 11)
    root = build_explorer_tree(ast)
    assert "span" not in root["children"][1]


@pytest.mark.parametrize("seed", range(300))
def test_random_corruption_gives_an_explorer_error_or_a_valid_tree(seed):
    rng = random.Random(seed)
    name = rng.choice(list(ALL_FIXTURES))
    ast = copy.deepcopy(ALL_FIXTURES[name][1])
    nodes = list(flat_ast(ast))
    weird = [None, 0, -1, "", "x", [], {}, [0, 1], (0, 1), 1.5, True, float("nan"),
             float("inf"), object(), 10**400, [[]], "Add", "Group", {"type": "Number"}]
    for _ in range(rng.randint(1, 3)):
        target = rng.choice(nodes)
        key = rng.choice(["type", "value", "children", "span"])
        if rng.random() < 0.35:
            target.pop(key, None)
        else:
            target[key] = rng.choice(weird)
    try:
        root = build_explorer_tree(ast)
    except ExplorerError:
        return
    # accepted: it must then be a fully consistent tree
    check_against_ast(ast, root)


# ---- 9.9 input immutability, stable ids and child order ----------------------------------------


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_input_is_untouched_and_output_shares_nothing_with_it(name):
    ast = copy.deepcopy(ALL_FIXTURES[name][1])
    snapshot = copy.deepcopy(ast)
    root = build_explorer_tree(ast)
    pristine = copy.deepcopy(root)
    assert ast == snapshot
    for node in list(flat(root)):  # scribble over the result
        node["children"].append("junk")
        node["children"].append("junk2")
        node["spoken_quick"] = "changed"
    assert ast == snapshot  # nothing in the input was shared with the output
    assert build_explorer_tree(ast) == pristine  # and the next call is unaffected


def test_a_shared_node_object_used_twice_is_converted_independently():
    shared = X(2)
    ast = eq(op("Add", [shared, shared], 0, 5), N(1, 8))
    root = build_explorer_tree(ast)
    a, b = root["children"][0]["children"]
    assert (a["id"], b["id"]) == ("n0.0.0", "n0.0.1")
    assert a is not b and a["children"] is not b["children"]
    assert ast["children"][0]["children"][0] is ast["children"][0]["children"][1]


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_ids_are_unique_path_based_and_follow_child_order(name):
    root = build_explorer_tree(ALL_FIXTURES[name][1])

    def visit(node, expected_id):
        assert node["id"] == expected_id
        for i, child in enumerate(node["children"]):
            visit(child, f"{expected_id}.{i}")

    visit(root, "n0")
    ids = [n["id"] for n in flat(root)]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"n0(\.\d+)*", i) for i in ids)


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_ids_do_not_depend_on_values_or_spans(name):
    ast = copy.deepcopy(ALL_FIXTURES[name][1])
    ids = [n["id"] for n in flat(build_explorer_tree(ast))]
    for node in flat_ast(ast):
        node["span"] = [node["span"][0] + 100, node["span"][1] + 200]
        if node["type"] == "Number":
            node["value"] = node["value"] + "7"
    assert [n["id"] for n in flat(build_explorer_tree(ast))] == ids


def test_children_keep_ast_order_even_when_spans_say_otherwise():
    # (spans are validated but never used to reorder, and never output)
    # the engine never re-sorts; the parser must supply children in reading order
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    left = ast["children"][0]
    left["children"][0]["span"], left["children"][1]["span"] = [5, 6], [0, 2]
    root = build_explorer_tree(ast)
    assert [c["type"] for c in root["children"][0]["children"]] == ["Mul", "Number"]
    assert all("span" not in c for c in root["children"][0]["children"])


def test_span_nesting_is_not_checked():
    # documented limit: only 0 <= start < end is validated, not containment
    ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
    ast["children"][0]["children"][1]["span"] = [500, 900]
    root = build_explorer_tree(ast)
    assert "span" not in root["children"][0]["children"][1]


# ---- 9.10 group boundaries (formerly strict xfail: fixed in the refinement round) -----------------


def test_nested_group_endings_are_distinguishable_in_the_whole_equation_reading():
    inner = G(op("Add", [X(), N(1)], 0, 3), 0, 4)
    three_times = op("Mul", [N(3), inner], 0, 4)
    closes_inside = op("Mul", [N(2), G(op("Add", [three_times, N(4)], 0, 5), 0, 6)], 0, 7)
    closes_before = op("Add", [op("Mul", [N(2), G(three_times, 0, 5)], 0, 6), N(4)], 0, 8)
    first = build(closes_inside, N(20))["spoken_detailed"]
    second = build(closes_before, N(20))["spoken_detailed"]
    assert first != second


def test_group_ending_inside_or_before_a_product_is_distinguishable():
    inside = G(op("Add", [N(2), op("Mul", [G(X()), N(2)], 0, 3)], 0, 4), 0, 5)
    before = op("Mul", [G(op("Add", [N(2), G(X())], 0, 4), 0, 5), N(2)], 0, 6)
    assert build(inside, N(1))["spoken_detailed"] != build(before, N(1))["spoken_detailed"]


# ===========================================================================
# Part 10: refinement round
#   Decision 1: coefficient of a powered variable (3x^2)
#   Decision 2: spoken group boundaries in whole-expression readings
#   plus sentence capitalisation and repeated long bases
# ===========================================================================


def powered(coef, exp=2, start=0):
    """coef * x^exp as Mul(Number, Pow(Variable, Number))"""
    return op("Mul", [N(coef, start), Pw(X(start + 1), N(exp, start + 3), start + 1, start + 5)],
              start, start + 5)


# ---- 10.1 coefficient of a powered variable -------------------------------------


@pytest.mark.parametrize("exp, phrase", [(2, "x to the power of 2"), (3, "x to the power of 3")])
def test_number_times_powered_variable_is_a_coefficient(exp, phrase):
    root = build(powered(3, exp), N(12, 12))
    mul = root["children"][0]
    three, power = mul["children"]
    base, exponent = power["children"]
    assert (three["role"], three["spoken_quick"]) == ("coefficient", "Coefficient 3")
    assert (power["role"], base["role"], exponent["role"]) == ("power", "variable", "exponent")
    assert exponent["spoken_quick"] == f"Exponent {exp}"
    assert three["spoken_detailed"] == (
        f"3 is the coefficient of {phrase}. It tells you {phrase} is multiplied by 3, "
        f"so the term means 3 times {phrase}. The exponent belongs to x alone, not to 3."
    )
    assert three["spoken_context"] == (
        f"The coefficient 3 belongs to {phrase}: it is multiplied by 3. "
        f"Together they form the term 3 times {phrase}."
    )
    # the other nodes now describe the same structure consistently
    assert "multiplied by the coefficient 3" in power["spoken_context"]
    assert "combines the coefficient 3 and the expression" in mul["spoken_detailed"]
    assert "The power is worked out first, then multiplied by 3." in mul["spoken_detailed"]
    assert "does not multiply x" not in spoken(three)
    assert "not a coefficient" not in spoken(three)


def test_exponent_keeps_its_own_role_and_wording_under_a_coefficient():
    root = build(powered(3, 2), N(12, 12))
    exponent = by_role(root, "exponent")[0]
    assert exponent["spoken_detailed"].startswith("2 is the exponent. It indicates that x is multiplied by itself.")
    assert "It is not a constant term or a coefficient" in exponent["spoken_detailed"]
    assert exponent["spoken_context"] == "The exponent 2 belongs to the base x. Together they form x to the power of 2."
    assert [n["value"] for n in by_role(root, "coefficient")] == ["3"]


def test_powered_variable_first_then_number():
    # x^2 * 3
    mul = op("Mul", [Pw(X(), N(2, 2), 0, 3), N(3, 6)], 0, 7)
    root = build(mul, N(12, 10))
    power, three = root["children"][0]["children"]
    assert (power["role"], three["role"]) == ("power", "coefficient")
    assert "coefficient of x to the power of 2" in three["spoken_detailed"]


@pytest.mark.parametrize("value, spoken_value", [("2.5", "2.5"), ("1", "1"), ("1.0", "1.0")])
def test_decimal_and_one_coefficients_of_a_power(value, spoken_value):
    root = build(powered(value), N(0, 12))
    coef = by_role(root, "coefficient")[0]
    assert coef["spoken_quick"] == f"Coefficient {spoken_value}"
    assert coef["spoken_detailed"].startswith(f"{spoken_value[0].upper() + spoken_value[1:]} is the coefficient of x to the power of 2.")


def test_number_times_group_holding_a_power_stays_a_group_multiplier():
    # 3(x^2 + 2) = 12
    inner = op("Add", [Pw(X(2), N(2, 4), 2, 5), N(2, 8)], 2, 9)
    root = build(op("Mul", [N(3), G(inner, 1, 10)], 0, 10), N(12, 13))
    three, group = root["children"][0]["children"]
    assert (three["role"], group["role"]) == ("group_multiplier", "group")
    assert by_role(root, "coefficient") == []
    assert "It is not a coefficient, because it multiplies a group" in three["spoken_detailed"]
    power = find(root, "Pow")[0]
    assert power["children"][1]["role"] == "exponent"
    assert "coefficient" not in spoken(power)


@pytest.mark.parametrize("build_other", [
    # 3(x+1)^2 : the power's base is a group
    lambda: Pw(G(op("Add", [X(2), N(1, 6)], 2, 7), 1, 8), N(2, 9), 1, 10),
    # 3 * 2^2 : the power's base is a number
    lambda: Pw(N(2, 1), N(2, 3), 1, 4),
    # 3(-x)^2 : negated variable is not a variable
    lambda: Pw(op("Neg", [X(2)], 1, 3), N(2, 5), 1, 6),
])
def test_other_powers_do_not_make_a_coefficient(build_other):
    root = build(op("Mul", [N(3), build_other()], 0, 10), N(0, 14))
    three = root["children"][0]["children"][0]
    assert three["role"] == "number"
    assert by_role(root, "coefficient") == []


def test_variable_times_powered_variable_has_no_coefficient():
    root = build(op("Mul", [X(), Pw(X(2), N(2, 4), 2, 5)], 0, 5), N(0, 9))
    assert by_role(root, "coefficient") == []
    assert root["children"][0]["children"][0]["role"] == "variable"


def test_powered_variable_inside_a_larger_product():
    # 2 * 3x^2 : only the 3 multiplies the powered variable
    inner = powered(3, 2, 2)
    root = build(op("Mul", [N(2), inner], 0, 8), N(0, 12))
    two, product = root["children"][0]["children"]
    three, power = product["children"]
    assert (two["role"], three["role"]) == ("number", "coefficient")
    assert [n["value"] for n in by_role(root, "coefficient")] == ["3"]
    assert "multiplied by the term 3 times x to the power of 2" in two["spoken_context"]
    assert "coefficient of x to the power of 2" in three["spoken_detailed"]


@pytest.mark.parametrize("side", ["left", "right"])
def test_powered_coefficient_on_either_side(side):
    term = op("Add", [powered(3, 2), N(1, 8)], 0, 9)
    root = build(term, N(5, 12)) if side == "left" else build(N(5, 0), term)
    coef = by_role(root, "coefficient")[0]
    assert coef["id"] == ("n0.0.0.0" if side == "left" else "n0.1.0.0")
    mul = root["children"][0 if side == "left" else 1]["children"][0]
    assert f"It is part of the {side} side of the equation." in mul["spoken_context"]
    assert "added to the constant 1" in mul["spoken_context"]
    assert "3 times x to the power of 2, plus 1" in root["spoken_detailed"]


def test_powered_coefficients_in_nested_groups():
    # 2(3(5x^2 + 1) + 4) = 20 : multipliers 2 and 3, coefficient 5
    five = powered(5, 2, 5)
    innermost = G(op("Add", [five, N(1, 12)], 5, 13), 4, 14)
    middle = G(op("Add", [op("Mul", [N(3, 3), innermost], 3, 14), N(4, 17)], 3, 18), 2, 19)
    root = build(op("Mul", [N(2, 0), middle], 0, 19), N(20, 22))
    assert [n["value"] for n in by_role(root, "group_multiplier")] == ["2", "3"]
    coef = by_role(root, "coefficient")
    assert [n["value"] for n in coef] == ["5"]
    assert "coefficient of x to the power of 2" in coef[0]["spoken_detailed"]
    assert len(find(root, "Group")) == 2
    ast = eq(op("Mul", [N(2, 0), middle], 0, 19), N(20, 22))
    check_against_ast(ast, root)
    check_roles(root)


def test_powered_coefficient_fixture_term_is_called_a_term():
    root = build_explorer_tree(REVIEW_FIXTURES["3x^2-2x+1=-(x-4)"][1])
    assert root["children"][0]["children"][0]["children"][0]["children"][0]["role"] == "coefficient"
    sub = root["children"][0]["children"][0]
    assert "takes the term 2x away from the term 3 times x to the power of 2" in sub["spoken_detailed"]


# ---- 10.2 spoken group boundaries ----------------------------------------------------


def reading(left, right=None):
    return build(left, right or N(0, 40))["spoken_detailed"]


def open_close_counts(text):
    return len(re.findall(r"\bthe group\b", text)), len(re.findall(r"\bend group\b", text))


def properly_nested(text):
    depth = 0
    for token in re.findall(r"\bthe group\b|\bend group\b", text):
        depth += 1 if token == "the group" else -1
        if depth < 0:
            return False
    return depth == 0


def test_one_group_is_opened_and_closed_aloud():
    assert reading(two_times_group(), N(12, 12)) == (
        "The whole equation. It says that the left side, 2 times the group x plus 3 "
        "end group, has the same value as the right side, 12."
    )


def test_a_group_that_is_a_whole_side_is_closed_aloud():
    root = build(G(x_plus_3(), 0, 7), N(5, 10))
    assert "the left side, the group x plus 3 end group, has" in root["spoken_detailed"]
    assert "It reads the group x plus 3 end group." in root["children"][0]["spoken_detailed"]


def test_two_nested_groups_close_in_the_right_order():
    inner = G(op("Add", [X(2), N(1, 6)], 2, 7), 1, 8)
    outer = G(op("Mul", [N(3, 1), inner], 1, 8), 0, 9)
    text = reading(outer)
    assert "the group 3 times the group x plus 1 end group end group" in text
    assert open_close_counts(text) == (2, 2) and properly_nested(text)


def test_adjacent_groups_each_close_before_the_next_opens():
    g1 = G(op("Add", [X(1), N(1, 5)], 1, 6), 0, 7)
    g2 = G(op("Sub", [X(9), N(2, 13)], 9, 14), 8, 15)
    text = reading(op("Mul", [g1, g2], 0, 15))
    assert "the group x plus 1 end group times the group x minus 2 end group," in text
    assert open_close_counts(text) == (2, 2) and properly_nested(text)
    assert tree("(x+1)(x-2)=0")["spoken_detailed"].count("end group") == 2


def test_group_inside_a_power_and_group_as_the_exponent():
    text = tree("(x+1)^2=9")["spoken_detailed"]
    assert "the group x plus 1 end group to the power of 2," in text
    # 2^(x + 1): the exponent group closes at the end of the power
    exp_group = G(op("Add", [X(3), N(1, 7)], 3, 8), 2, 9)
    text = reading(Pw(N(2), exp_group, 0, 9), N(8, 12))
    assert "2 to the power of the group x plus 1 end group," in text


def test_group_inside_a_fraction():
    g = G(op("Add", [X(1), N(1, 5)], 1, 6), 0, 7)
    text = reading(Fr(g, N(2, 9), 0, 10), N(3, 14))
    assert "the fraction with numerator the group x plus 1 end group and denominator 2" in text
    g2 = G(op("Sub", [X(9), N(2, 13)], 9, 14), 8, 15)
    text = reading(Fr(N(1, 0), g2, 0, 15), N(3, 20))
    assert "numerator 1 and denominator the group x minus 2 end group," in text
    assert open_close_counts(text) == (1, 1)


def _closes_inside_versus_before():
    inner = G(op("Add", [X(), N(1)], 0, 3), 0, 4)
    three_times = op("Mul", [N(3), inner], 0, 4)
    inside = op("Mul", [N(2), G(op("Add", [three_times, N(4)], 0, 5), 0, 6)], 0, 7)  # 2(3(x+1)+4)
    before = op("Add", [op("Mul", [N(2), G(three_times, 0, 5)], 0, 6), N(4)], 0, 8)  # 2(3(x+1))+4
    return inside, before


def test_nested_group_endings_are_distinguishable_in_the_whole_equation_reading():
    inside, before = _closes_inside_versus_before()
    first, second = reading(inside, N(20)), reading(before, N(20))
    assert first != second
    assert "2 times the group 3 times the group x plus 1 end group plus 4 end group," in first
    assert "2 times the group 3 times the group x plus 1 end group end group plus 4," in second


def test_group_ending_inside_or_before_a_product_is_distinguishable():
    inside = G(op("Add", [N(2), op("Mul", [G(X()), N(2)], 0, 3)], 0, 4), 0, 5)  # (2 + (x)2)
    before = op("Mul", [G(op("Add", [N(2), G(X())], 0, 4), 0, 5), N(2)], 0, 6)  # (2 + (x))2
    first, second = reading(inside, N(1)), reading(before, N(1))
    assert first != second
    assert "the group 2 plus the group x end group times 2 end group," in first
    assert "the group 2 plus the group x end group end group times 2," in second


def test_boundary_words_are_in_the_whole_reading_not_in_single_part_texts():
    root = tree("2(3(x+1)+4)=20")
    assert "end group" in root["spoken_detailed"]
    assert "end group" in root["children"][0]["spoken_detailed"]  # "It reads ..."
    for node in flat(root):
        for key in ("spoken_quick", "spoken_context"):
            assert "end group" not in node[key], (node["id"], key)
        if node["role"] not in ("equation", "left_side", "right_side"):
            assert "end group" not in node["spoken_detailed"], node["id"]


def test_quick_text_is_unchanged_and_short_for_groups():
    for name in ("2(x+3)=12", "(x+1)(x-2)=0", "2(3(x+1)+4)=20", "(x+1)^2=9"):
        for n in flat(tree(name)):
            assert len(n["spoken_quick"].split()) <= 4
            assert "end" not in n["spoken_quick"]


def test_boundaries_do_not_change_ids_spans_or_structure():
    for name, (source, ast) in ALL_FIXTURES.items():
        before = copy.deepcopy(ast)
        root = build_explorer_tree(ast)
        assert ast == before
        check_against_ast(ast, root)


@pytest.mark.parametrize("seed", range(150))
def test_random_readings_have_balanced_boundaries(seed):
    ast = random_equation(seed)
    root = build_explorer_tree(ast)
    groups = sum(1 for n in flat_ast(ast) if n["type"] == "Group")
    opened, closed = open_close_counts(root["spoken_detailed"])
    assert opened == closed == groups
    assert properly_nested(root["spoken_detailed"])
    for side in root["children"]:
        reads = re.search(r"It reads (.*?)\. [A-Z]", side["spoken_detailed"] + ". X")
        if reads and not side["type"] in ("Number", "Variable"):
            assert properly_nested(reads.group(1))


def _erase_groups(node):
    if node["type"] == "Group":
        return _erase_groups(node["children"][0])
    return (node["type"], node.get("value"), tuple(_erase_groups(c) for c in node["children"]))


def _small_trees(size, kinds):
    """Every tree with `size` nodes over the given node kinds; leaves x and 2."""
    if size == 1:
        return [
            {"type": "Variable", "value": "x", "children": [], "span": [0, 1]},
            {"type": "Number", "value": "2", "children": [], "span": [0, 1]},
        ]
    out = []
    for kind in kinds:
        if kind in ("Group", "Neg"):
            for sub in _small_trees(size - 1, kinds):
                out.append({"type": kind, "children": [sub], "span": [0, 1]})
        else:
            for k in range(1, size - 1):
                for left in _small_trees(k, kinds):
                    for right in _small_trees(size - 1 - k, kinds):
                        out.append({"type": kind, "children": [left, right], "span": [0, 1]})
    return out


@pytest.mark.parametrize("kinds", [
    ("Add", "Sub", "Mul", "Pow", "Group"),
    ("Add", "Sub", "Mul", "Div", "Pow", "Neg", "Div", "Group"),
])
def test_trees_that_differ_only_in_group_boundaries_are_read_differently(kinds):
    """Exhaustive: for every tree up to 7 nodes, two trees that are the same once
    the groups are removed but have their groups in different places must give
    different whole-equation readings."""
    seen = {}
    for size in range(1, 8):
        for tree_ in _small_trees(size, kinds):
            ast = {"type": "Equation", "span": [0, 5], "children": [
                tree_, {"type": "Number", "value": "0", "children": [], "span": [0, 1]}]}
            text = build_explorer_tree(ast)["spoken_detailed"]
            key = (_erase_groups(tree_), text)
            shape_ = repr(tree_)
            assert seen.setdefault(key, shape_) == shape_, (text, seen[key], shape_)


# ---- 10.3 capitalisation and repeated long bases --------------------------------------------------


def _sentence_starts(text):
    """The first word of every sentence (split on '. ')."""
    return [s.strip().split(" ")[0] for s in re.split(r"(?<=\.) ", text) if s.strip()]


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_no_sentence_starts_with_a_lower_case_word(name):
    for node in flat(build_explorer_tree(ALL_FIXTURES[name][1])):
        for key in SPOKEN_KEYS:
            for first in _sentence_starts(node[key]):
                # a lone letter is a variable name (x), written in lower case
                assert len(first) == 1 or not first[0].islower(), (node["id"], key, first)


def test_capitalised_starts_for_groups_and_negative_numbers():
    pow_node = tree("(x+1)^2=9")["children"][0]
    assert "The group x plus 1 squared means the group x plus 1 is multiplied by itself" in (
        pow_node["spoken_detailed"]
    )
    neg_base = build(Pw(Ng(N(2, 1)), N(2, 4), 0, 5), N(4, 8))["children"][0]
    assert "The quantity negative 2 squared means" in neg_base["spoken_detailed"]
    assert neg_base["children"][0]["spoken_detailed"].startswith("Negation. It changes the sign of the number 2.")
    # a variable base stays in lower case
    assert "x squared means x is multiplied by itself" in tree("x^2+3=7")["children"][0]["children"][0]["spoken_detailed"]


def test_long_base_is_named_once_then_called_the_base():
    root = build_explorer_tree(REVIEW_FIXTURES["((x+1)(x-2)+3)^2=16"][1])
    power = root["children"][0]
    detail = power["spoken_detailed"]
    base = "the group the group x plus 1, times the group x minus 2, plus 3"
    assert detail.count(base) == 1  # spelled out once, in "The base is ..."
    assert "The base squared means the base is multiplied by itself: the base times the base." in detail
    exponent = power["children"][1]
    assert exponent["spoken_detailed"].startswith("2 is the exponent. It indicates that the base is multiplied by itself.")
    assert exponent["spoken_context"].count(base) == 2  # context is read alone: unchanged


def test_short_bases_are_still_spelled_out():
    cubed = build(Pw(G(x_plus_3(), 0, 7), N(3, 8), 0, 9), N(8, 12))["children"][0]["spoken_detailed"]
    assert "The group x plus 3 cubed means the group x plus 3 is used as a factor three times: " in cubed
    higher = build(Pw(G(x_plus_3(), 0, 7), N(5, 8), 0, 9), N(8, 12))["children"][0]["spoken_detailed"]
    assert "It means the group x plus 3 is used as a factor 5 times." in higher


def test_long_base_with_another_exponent_uses_the_base_too():
    base = G(op("Add", [op("Mul", [N(2), G(x_plus_3(), 1, 8)], 0, 9), N(5, 12)], 0, 13), 0, 14)
    root = build(Pw(base, N(5, 15), 0, 16), N(8, 20))
    detail = root["children"][0]["spoken_detailed"]
    assert "It means the base is used as a factor 5 times." in detail


# ===========================================================================
# Part 10: docs/contracts.md compliance (the authoritative shared contract)
# ===========================================================================

CONTRACT_NODE_FIELDS = {
    "id", "type", "role", "value", "spoken_quick", "spoken_detailed",
    "spoken_context", "children",
}
CONTRACT_AST_TYPES = {
    "Number", "Variable", "Add", "Sub", "Mul", "Div", "Pow", "Neg", "Group", "Equation",
}


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_contract_explorer_node_schema_is_exact_on_every_node(name):
    for n in flat(build_explorer_tree(ALL_FIXTURES[name][1])):
        assert set(n) == CONTRACT_NODE_FIELDS
        assert isinstance(n["id"], str) and n["id"]
        assert n["type"] in CONTRACT_AST_TYPES
        assert isinstance(n["role"], str) and n["role"]
        assert n["value"] is None or isinstance(n["value"], str)
        for key in SPOKEN_KEYS:
            assert isinstance(n[key], str) and n[key].strip()
        assert isinstance(n["children"], list)


def test_contract_value_is_the_display_string_or_null():
    root = tree("3x+5=14")
    by_id = {n["id"]: n for n in flat(root)}
    assert by_id["n0.0.0.0"]["value"] == "3"        # Number: its source spelling
    assert by_id["n0.0.0.1"]["value"] == "x"        # Variable: its name
    assert by_id["n0.1"]["value"] == "14"           # a side that is a bare Number keeps it
    for node_id in ("n0", "n0.0", "n0.0.0"):        # Equation, Add, Mul: no payload
        assert by_id[node_id]["value"] is None


def test_contract_the_output_is_json_serialisable_with_string_values():
    import json

    for name in ALL_FIXTURES:
        restored = json.loads(json.dumps(build_explorer_tree(ALL_FIXTURES[name][1])))
        assert restored == build_explorer_tree(ALL_FIXTURES[name][1])


def test_contract_documents_example_ast_is_accepted():
    # the first example of docs/contracts.md (OwnAST node), verbatim
    import json

    example = json.loads(
        '{"type":"Equation","value":null,"children":[{"type":"Add","value":null,"children":'
        '[{"type":"Mul","value":null,"children":[{"type":"Number","value":"3","children":[],'
        '"span":[0,1]},{"type":"Variable","value":"x","children":[],"span":[1,2]}],"span":[0,2]},'
        '{"type":"Number","value":"5","children":[],"span":[5,6]}],"span":[0,6]},'
        '{"type":"Number","value":"14","children":[],"span":[9,11]}],"span":[0,11]}'
    )
    root = build_explorer_tree(example)
    assert [(n["id"], n["role"], n["value"]) for n in flat(root)] == [
        ("n0", "equation", None),
        ("n0.0", "left_side", None),
        ("n0.0.0", "operator", None),
        ("n0.0.0.0", "coefficient", "3"),
        ("n0.0.0.1", "variable", "x"),
        ("n0.0.1", "constant", "5"),
        ("n0.1", "right_side", "14"),
    ]
    assert root == tree("3x+5=14")  # same as the fixture the contract example mirrors


def test_contract_documents_other_examples_have_the_expected_shape():
    # "2(x + 3) = 10" -> Equation(Mul(Number("2"), Group(Add(Variable("x"), Number("3")))), Number("10"))
    root = build(op("Mul", [N("2"), G(x_plus_3())], 0, 8), N("10", 11))
    assert [(n["type"], n["role"]) for n in flat(root)][:4] == [
        ("Equation", "equation"), ("Mul", "left_side"), ("Number", "group_multiplier"),
        ("Group", "group"),
    ]
    # "x^2 - 4 = 0" -> Equation(Sub(Pow(Variable("x"), Number("2")), Number("4")), Number("0"))
    root = build(op("Sub", [Pw(X(), N("2", 2)), N("4", 6)], 0, 7), N("0", 10))
    pow_node, four = root["children"][0]["children"]
    assert [c["role"] for c in pow_node["children"]] == ["variable", "exponent"]
    assert (four["role"], four["value"]) == ("constant", "4")


def test_contract_value_key_may_be_absent_or_null_on_non_leaves():
    with_null = copy.deepcopy(FIXTURES["3x+5=14"][1])
    for node in flat_ast(with_null):
        if node["type"] not in ("Number", "Variable"):
            node["value"] = None
    assert build_explorer_tree(with_null) == tree("3x+5=14")


def test_contract_leaves_must_carry_a_value():
    for kind in ("Number", "Variable"):
        bad = {"type": kind, "children": [], "span": [0, 1]}
        with pytest.raises(ExplorerError, match=f"{kind}"):
            build(op("Add", [bad, N("1", 4)], 0, 5), N("1", 8))
        bad["value"] = None
        with pytest.raises(ExplorerError, match=f"{kind}"):
            build(op("Add", [bad, N("1", 4)], 0, 5), N("1", 8))


def test_contract_number_values_are_strings_and_a_python_number_is_not_accepted():
    for value in (3, 2.5):
        bad = {"type": "Number", "value": value, "children": [], "span": [0, 1]}
        with pytest.raises(ExplorerError, match="string"):
            build(op("Add", [X(), bad], 0, 3), N("1", 8))


def test_contract_fraction_is_not_an_ast_type():
    fraction = {"type": "Fraction", "children": [N("1"), N("2", 2)], "span": [0, 3]}
    with pytest.raises(ExplorerError, match="unsupported node type 'Fraction'"):
        build(fraction, N("1", 8))


def test_contract_the_set_of_accepted_types_is_exactly_the_contracts():
    for kind in sorted(CONTRACT_AST_TYPES - {"Equation", "Number", "Variable"}):
        n = 1 if kind in ("Neg", "Group") else 2
        kids = [X(0), N("2", 2)][:n]
        build(op(kind, kids, 0, 5), N("1", 8))  # does not raise
    for kind in ("Fraction", "Frac", "Power", "Paren", "Negate", "Sqrt", "Abs"):
        with pytest.raises(ExplorerError, match="unsupported node type"):
            build({"type": kind, "children": [X(0), N("2", 2)], "span": [0, 5]}, N("1", 8))


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_contract_span_is_not_in_the_public_output(name):
    ast = ALL_FIXTURES[name][1]
    assert all("span" in a for a in flat_ast(copy.deepcopy(ast)))  # still required on input
    assert all("span" not in n for n in flat(build_explorer_tree(ast)))


def test_contract_span_is_still_required_and_validated_on_input():
    for span in (None, [1], [2, 2], [3, 1], [-1, 2], [0.0, 1.0]):
        ast = copy.deepcopy(FIXTURES["3x+5=14"][1])
        ast["children"][1]["span"] = span
        with pytest.raises(ExplorerError, match="span"):
            build_explorer_tree(ast)


def test_contract_div_is_division_and_fraction_in_one_node():
    # the same Div tree whether it was typed x/2 or as a stacked fraction
    root = build(op("Div", [X(0), N("2", 2)], 0, 3), N("3", 6))
    div = root["children"][0]
    assert div["type"] == "Div" and div["role"] == "left_side"
    assert [c["role"] for c in div["children"]] == ["variable", "denominator"]
    assert "fraction with numerator x and denominator 2" in root["spoken_detailed"]
    deeper = build(op("Add", [op("Div", [N("1"), N("2", 2)], 0, 3), X(6)], 0, 7), N("5", 10))
    frac = deeper["children"][0]["children"][0]
    assert (frac["type"], frac["role"], frac["spoken_quick"]) == ("Div", "fraction", "Fraction")
    assert [c["role"] for c in frac["children"]] == ["numerator", "denominator"]


def test_contract_div_children_are_numerator_then_denominator_and_never_reordered():
    root = build(op("Div", [N("3"), X(2)], 0, 3), N("1", 6))
    num, den = root["children"][0]["children"]
    assert (num["value"], den["value"]) == ("3", "x")
    assert (num["role"], den["role"]) == ("numerator", "variable")
    assert "3 is the numerator of the fraction" in num["spoken_detailed"]


def test_contract_div_arity_and_value_are_enforced():
    for kids in ([], [N("1")], [N("1"), N("2", 2), N("3", 4)]):
        with pytest.raises(ExplorerError, match=r"Div needs 2 child\(ren\)"):
            build(op("Div", kids, 0, 5), N("1", 8))
    with pytest.raises(ExplorerError, match="Div must not have a 'value'"):
        build(dict(op("Div", [N("1"), N("2", 2)], 0, 3), value="1"), N("1", 8))


def test_contract_role_vocabulary_is_exactly_the_documented_one():
    seen = set()
    for name in ALL_FIXTURES:
        seen |= {n["role"] for n in flat(build_explorer_tree(ALL_FIXTURES[name][1]))}
    # the fixtures use every role except "base", "number" and "numerator"
    seen |= {n["role"] for n in flat(build(op("Div", [N("1"), N("2", 2)], 0, 3), N("3", 6)))}  # numerator
    seen |= {n["role"] for n in flat(build(Pw(N("2"), N("3", 2)), N("8", 6)))}  # base
    seen |= {n["role"] for n in flat(build(op("Mul", [N("2"), N("3", 2)], 0, 3), N("6", 6)))}  # number
    assert seen == ALLOWED_ROLES


def test_contract_constant_role_uses_the_contracts_name_not_constant_term():
    roles = {n["role"] for n in flat(tree("3x+5=14"))}
    assert "constant" in roles and "constant_term" not in roles
    five = tree("3x+5=14")["children"][0]["children"][1]
    assert five["spoken_quick"] == "Constant term 5"  # the spoken wording is unchanged


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_contract_ids_are_unique_deterministic_strings_in_one_tree(name):
    ast = ALL_FIXTURES[name][1]
    ids = [n["id"] for n in flat(build_explorer_tree(ast))]
    assert len(ids) == len(set(ids))
    assert ids == [n["id"] for n in flat(build_explorer_tree(copy.deepcopy(ast)))]
    assert all(re.fullmatch(r"n0(\.\d+)*", i) for i in ids)


def test_contract_display_values_keep_the_source_spelling_in_speech():
    root = build(op("Add", [term("3.50"), N("007", 6)], 0, 9), N("1.0", 12))
    assert [n["value"] for n in by_role(root, "coefficient")] == ["3.50"]
    texts = " ".join(spoken(n) for n in flat(root))
    for spelling in ("3.50", "007", "1.0"):
        assert spelling in texts


@pytest.mark.parametrize("depth", [MAX_DEPTH - 1, MAX_DEPTH])
def test_contract_trees_up_to_the_depth_limit_build_with_string_values(depth):
    node = N("1")
    for _ in range(depth - 2):
        node = op("Neg", [node], 0, 1)
    root = build_explorer_tree(equation(node, N("2", 3), 5))
    assert max(len(n["id"].split(".")) for n in flat(root)) <= depth
    assert all(n["value"] is None or isinstance(n["value"], str) for n in flat(root))


def test_contract_one_level_over_the_limit_and_malformed_nodes_are_explorer_errors():
    node = N("1")
    for _ in range(MAX_DEPTH - 1):
        node = op("Neg", [node], 0, 1)
    with pytest.raises(ExplorerError, match="more than"):
        build_explorer_tree(equation(node, N("2", 3), 5))
    for bad in (None, [], "3x", 3, {"type": "Equation"}, {"children": [], "span": [0, 1]}):
        with pytest.raises(ExplorerError):
            build_explorer_tree(bad)


def test_contract_the_python_and_javascript_depth_limits_still_match():
    source = JS_PATH.read_text(encoding="utf-8")
    assert int(re.search(r"var MAX_DEPTH = (\d+);", source).group(1)) == MAX_DEPTH == 100
