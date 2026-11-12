"""Explorer role and spoken-text tests.

Owner: Member 4
See plan.md §13

Part 1 checks the mock OwnAST fixtures (tests/explorer_fixtures.py).
Part 2 tests engine/explore.py (Phase 1) against those mocks. Both parts use
the provisional AST shape; revisit when engine/parser.py and docs/contracts.md
land.
"""

import copy

import pytest

from engine.explore import ExplorerError, build_explorer_tree
from tests.explorer_fixtures import FIXTURE_NODE_TYPES, FIXTURES


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
    source, ast = FIXTURES["3x+5=14"]
    left, right = ast["children"]
    mul, five = left["children"]
    three, x = mul["children"]

    def text(n):
        return source[n["span"][0] : n["span"][1]]

    assert text(left) == "3x + 5"
    assert text(mul) == "3x"
    assert (text(three), three["value"]) == ("3", 3)
    assert (text(x), x["value"]) == ("x", "x")
    assert (text(five), five["value"]) == ("5", 5)
    assert (text(right), right["value"]) == ("14", 14)


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

EXPLORER_FIELDS = {
    "id", "type", "role", "value", "spoken_quick", "spoken_detailed",
    "spoken_context", "span", "children",
}


def tree(name):
    return build_explorer_tree(FIXTURES[name][1])


def flat(node):
    yield node
    for c in node["children"]:
        yield from flat(c)


def leaf(type_, start, end, value=None):
    n = {"type": type_, "children": [], "span": [start, end]}
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
    assert (five["role"], five["type"]) == ("constant_term", "Number")
    three, x = mul["children"]
    assert (three["role"], three["value"]) == ("coefficient", 3)
    assert (x["role"], x["value"]) == ("variable", "x")


def test_2x_plus_3_eq_9_structure_and_roles():
    root = tree("2x+3=9")
    left, right = root["children"]
    mul, three = left["children"]
    two, x = mul["children"]
    assert [n["role"] for n in (root, left, right)] == ["equation", "left_side", "right_side"]
    assert (two["role"], two["value"]) == ("coefficient", 2)
    assert x["role"] == "variable"
    assert (three["role"], three["value"]) == ("constant_term", 3)
    assert right["value"] == 9


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
def test_spans_preserved(name):
    def check(ast, ex):
        assert ex["span"] == ast["span"]
        for a, e in zip(ast["children"], ex["children"]):
            check(a, e)
    ast = FIXTURES[name][1]
    check(ast, build_explorer_tree(ast))


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
    assert left["children"][1]["role"] == "number"
    assert left["children"][0]["role"] == "variable"


def test_subtraction_and_division_are_operators():
    # 3x - 5 = 4/2   (left side is Sub, right side is Div)
    mul = op("Mul", [leaf("Number", 0, 1, 3), leaf("Variable", 1, 2, "x")], 0, 2)
    sub = op("Sub", [mul, leaf("Number", 5, 6, 5)], 0, 6)
    div = op("Div", [leaf("Number", 9, 10, 4), leaf("Number", 11, 12, 2)], 9, 12)
    root = build_explorer_tree(equation(sub, div, 12))
    left, right = root["children"]
    assert left["children"][1]["role"] == "constant_term"
    assert right["role"] == "right_side" and right["type"] == "Div"
    assert [c["role"] for c in right["children"]] == ["number", "number"]


def test_nested_operations():
    # 3x + 2x + 5 = 14  ->  Add(Add(Mul, Mul), 5)
    m1 = op("Mul", [leaf("Number", 0, 1, 3), leaf("Variable", 1, 2, "x")], 0, 2)
    m2 = op("Mul", [leaf("Number", 5, 6, 2), leaf("Variable", 6, 7, "x")], 5, 7)
    inner = op("Add", [m1, m2], 0, 7)
    outer = op("Add", [inner, leaf("Number", 10, 11, 5)], 0, 11)
    root = build_explorer_tree(equation(outer, leaf("Number", 14, 16, 14), 16))
    left = root["children"][0]
    inner_ex, five = left["children"]
    assert inner_ex["role"] == "operator" and five["role"] == "constant_term"
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
    assert neg_ex["children"][0]["role"] == "constant_term"


def test_neg_of_coefficient_product():
    # -3x = 6 : Neg(Mul(3, x)); 3 still multiplies x
    mul = op("Mul", [leaf("Number", 1, 2, 3), leaf("Variable", 2, 3, "x")], 1, 3)
    neg = op("Neg", [mul], 0, 3)
    root = build_explorer_tree(equation(neg, leaf("Number", 6, 7, 6), 7))
    left = root["children"][0]
    assert left["role"] == "left_side"
    assert left["children"][0]["children"][0]["role"] == "coefficient"


def test_negative_number_value_is_spoken_as_negative():
    # a Number node with a negative value
    mul = op("Mul", [leaf("Number", 0, 2, -3), leaf("Variable", 2, 3, "x")], 0, 3)
    root = build_explorer_tree(equation(mul, leaf("Number", 6, 7, 6), 7))
    coef = root["children"][0]["children"][0]
    assert coef["spoken_quick"] == "Coefficient negative 3"


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
     ("Div", "Division"), ("Pow", "Power")],
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
    bad = {"type": "Number", "value": 1, "span": [0, 1], "children": [leaf("Number", 0, 1, 1)]}
    with pytest.raises(ExplorerError, match="needs 0"):
        build_explorer_tree(equation(bad, leaf("Number", 6, 7, 1), 7))


@pytest.mark.parametrize("bad", [
    {"type": "Number", "children": [], "span": [0, 1]},                # no value
    {"type": "Number", "value": "3", "children": [], "span": [0, 1]},   # string value
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


@pytest.mark.parametrize("node_type", ["Group", "Sqrt", "", "number"])
def test_unsupported_node_type_fails_clearly(node_type):
    bad = {"type": node_type, "children": [], "span": [0, 1]}
    with pytest.raises(ExplorerError, match="unsupported node type"):
        build_explorer_tree(equation(bad, leaf("Number", 6, 7, 1), 7))


def test_unsupported_node_deep_in_tree_reports_its_path():
    bad = {"type": "Group", "children": [leaf("Number", 0, 1, 1)], "span": [0, 3]}
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
    assert five["role"] == "constant_term"
    assert "The term 3x is subtracted from the constant term 5" not in five["spoken_context"]
    assert "has the term 3x subtracted from it" in five["spoken_context"]


def test_same_node_type_different_roles_get_different_explanations():
    # 3x + 5 = 5 : Number 5 is a constant term on the left, a plain right side
    root = build(op("Add", [term(3), N(5, 5)], 0, 6), N(5, 9))
    constant = root["children"][0]["children"][1]
    right = root["children"][1]
    assert constant["type"] == right["type"] == "Number"
    assert (constant["role"], right["role"]) == ("constant_term", "right_side")
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


def test_power_expression_uses_existing_support_only():
    # x^2 + 3 = 7 : Pow is accepted already; wording stays generic (Phase 2)
    root = build(op("Add", [op("Pow", [X(), N(2, 2)], 0, 3), N(3, 6)], 0, 7), N(7, 10))
    pow_node = root["children"][0]["children"][0]
    x, two = pow_node["children"]
    three = root["children"][0]["children"][1]
    assert "raises the variable x to the power 2" in pow_node["spoken_detailed"]
    assert two["role"] == "number"
    assert "not a coefficient" in two["spoken_detailed"]
    assert "x is raised to the power 2" in x["spoken_context"]
    assert "power that the variable x is raised to" in two["spoken_context"]
    assert "constant term 3 is added to the expression x to the power of 2" in three["spoken_context"]
    # no squared/base/exponent wording yet
    assert not any(w in spoken(n) for n in flat(root) for w in ("squared", "base", "exponent"))


def test_power_followed_by_more_terms_is_not_ambiguous():
    root = build(op("Add", [op("Pow", [X(), N(2, 2)], 0, 3), N(3, 6)], 0, 7), N(7, 10))
    # a pause separates the exponent from "plus 3"
    assert "x to the power of 2, plus 3" in root["children"][0]["spoken_detailed"]


def test_group_still_rejected_so_2_times_bracket_is_phase_2():
    # 2(x + 3) = 12 needs Group, which plan.md schedules for Phase 2.
    group = {"type": "Group", "children": [op("Add", [X(2), N(3, 6)], 2, 7)], "span": [1, 8]}
    with pytest.raises(ExplorerError, match="unsupported node type 'Group'"):
        build(op("Mul", [N(2), group], 0, 8), N(12, 11))


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


def test_negative_number_values_are_spoken_as_negative():
    root = build(op("Add", [op("Mul", [N(-3), X(2)], 0, 3), N(-5, 6)], 0, 8), N(-1, 11))
    coef = by_role(root, "coefficient")[0]
    const = by_role(root, "constant_term")[0]
    assert coef["spoken_quick"] == "Coefficient negative 3"
    assert "negative 3 is the coefficient of x" in coef["spoken_detailed"]
    assert "multiplied by negative 3" in coef["spoken_detailed"]
    assert "negative 3x" in coef["spoken_context"]
    assert "negative 5 is a constant term" in const["spoken_detailed"]
    assert "just the number negative 1" in root["children"][1]["spoken_detailed"]
    assert "-" not in " ".join(spoken(n) for n in flat(root))


def test_float_values_do_not_print_trailing_zero():
    root = build(op("Add", [term(2.0), N(1.5, 5)], 0, 8), N(4.0, 11))
    assert "term 2x" in root["children"][0]["children"][1]["spoken_context"]
    assert "constant term 1.5" in root["children"][0]["children"][1]["spoken_context"]
    assert "just the number 4." in root["children"][1]["spoken_detailed"]


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
        "constant_term": "Constant term 5",
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
    assert "divides the variable x by the number 2" in left["spoken_detailed"]
    assert "is divided by the number 2" in x["spoken_context"]
    assert "divides the variable x" in two["spoken_context"]
    assert "x divided by 2" in root["spoken_detailed"]


def test_spoken_text_has_no_math_symbols_anywhere():
    for name in FIXTURES:
        for n in flat(tree(name)):
            assert not any(ch in spoken(n) for ch in "+*/^=()")


def test_explanations_are_deterministic_and_do_not_change_structure():
    first, second = tree("3x+5=14"), tree("3x+5=14")
    assert first == second
    for n in flat(first):
        assert set(n) == EXPLORER_FIELDS
