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
    # Phase 2: the exponent has its own role, still not constant/coefficient
    assert left["children"][1]["role"] == "exponent"
    assert left["children"][1]["role"] not in ("constant_term", "coefficient", "number")
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


# ===========================================================================
# Part 4: Phase 2 mathematical structures (Group, multiplier, Power, Fraction)
# ===========================================================================
# Fraction is a PROVISIONAL node type (see engine/explore.py docstring and
# tests/explorer_fixtures.py); Group and Pow follow plan.md section 10.

SYMBOLS = "+*/^=()"
NEW_FIXTURES = [
    "2(x+3)=12", "(x+1)(x-2)=0", "2(3(x+1)+4)=20",
    "x^2+3=7", "(x+1)^2=9", "(x+1)/2=3", "x^2/3=4", "(x/2)^2=9",
]


def G(inner, start=1, end=8):
    return {"type": "Group", "children": [inner], "span": [start, end]}


def Fr(num, den, start=0, end=9):
    return {"type": "Fraction", "children": [num, den], "span": [start, end]}


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
    assert (two["role"], two["value"]) == ("group_multiplier", 2)
    assert (group["role"], group["type"]) == ("group", "Group")
    assert (add["role"], add["type"]) == ("operator", "Add")
    assert (x["role"], x["value"]) == ("variable", "x")
    assert (three["role"], three["value"]) == ("constant_term", 3)
    assert root["children"][1]["role"] == "right_side"


def test_group_keeps_child_structure_ids_and_spans():
    root = tree("2(x+3)=12")
    group = root["children"][0]["children"][1]
    assert group["id"] == "n0.0.1"
    assert group["span"] == [1, 8]
    assert len(group["children"]) == 1
    assert group["children"][0]["id"] == "n0.0.1.0"
    assert group["children"][0]["span"] == [2, 7]  # the brackets are not in the child's span
    source = FIXTURES["2(x+3)=12"][0]
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
    assert five["role"] == "constant_term"
    assert "added to the group x plus 3" in five["spoken_context"]


def test_nested_groups():
    root = tree("2(3(x+1)+4)=20")
    outer = root["children"][0]["children"][1]
    add = outer["children"][0]
    inner_mul, four = add["children"]
    three, inner = inner_mul["children"]
    assert [outer["role"], inner["role"]] == ["group", "group"]
    assert three["role"] == "group_multiplier"
    assert four["role"] == "constant_term"
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
    assert "the group x plus 3, times 2" in root["children"][0]["spoken_detailed"]


def test_multiplier_is_not_a_coefficient_and_a_coefficient_is_not_a_multiplier():
    # 2x + 2(x + 3) = 10 : two 2s, two different roles
    left = op("Add", [term(2), two_times_group()], 0, 12)
    root = build(left, N(10, 15))
    assert [n["value"] for n in by_role(root, "coefficient")] == [2]
    assert [n["value"] for n in by_role(root, "group_multiplier")] == [2]
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
    assert [n["value"] for n in by_role(root, "coefficient")] == [3]


def test_number_times_number_is_neither():
    root = build(op("Mul", [N(2), N(3, 2)], 0, 3), N(6, 6))
    assert {n["role"] for n in root["children"][0]["children"]} == {"number"}


def test_negative_multiplier():
    # a bare negative number multiplying a group
    group = G(x_plus_3(), 2, 9)
    root = build(op("Mul", [N(-2), group], 0, 9), N(4, 12))
    mult = root["children"][0]["children"][0]
    assert mult["role"] == "group_multiplier"
    assert mult["spoken_quick"] == "Multiplier negative 2"
    assert mult["spoken_detailed"].startswith("negative 2 is the multiplier of the group x plus 3.")
    assert "multiplied by negative 2" in mult["spoken_detailed"]
    assert "-" not in spoken(mult)


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


def test_multiplier_float_value_has_no_trailing_zero():
    root = build(op("Mul", [N(2.0), G(x_plus_3())], 0, 8), N(1, 11))
    assert root["children"][0]["children"][0]["spoken_quick"] == "Multiplier 2"


# ---- 3. Power -----------------------------------------------------------------


def test_power_fixture_roles():
    root = tree("x^2+3=7")
    pow_node = root["children"][0]["children"][0]
    x, two = pow_node["children"]
    assert (pow_node["role"], pow_node["type"]) == ("power", "Pow")
    assert (x["role"], x["value"]) == ("variable", "x")
    assert (two["role"], two["value"]) == ("exponent", 2)
    assert root["children"][0]["children"][1]["role"] == "constant_term"


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


def test_exponent_is_never_a_constant_term_or_coefficient():
    # x^2 + 2 = 6 : both numbers are 2, with different roles
    root = build(op("Add", [Pw(X(), N(2, 2)), N(2, 6)], 0, 7), N(6, 10))
    exp = root["children"][0]["children"][0]["children"][1]
    const = root["children"][0]["children"][1]
    assert exp["role"] == "exponent" and const["role"] == "constant_term"
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


@pytest.mark.parametrize("value", [0, 1, -2, 0.5])
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


def test_negative_exponent_is_spoken_as_negative():
    root = build(Pw(X(), N(-2, 2)), N(1, 8))
    pow_node = root["children"][0]
    assert "the exponent is negative 2" in pow_node["spoken_detailed"]
    assert pow_node["children"][1]["spoken_quick"] == "Exponent negative 2"


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
    assert "the group x plus 1 squared means the group x plus 1 is multiplied by itself" in (
        pow_node["spoken_detailed"]
    )
    assert "It is the base, raised to the power 2." in group["spoken_detailed"]
    assert "The entire group" not in group["spoken_detailed"]  # no double wording
    assert "belongs to the base the group x plus 1" in two["spoken_context"]


def test_group_base_is_separate_from_exponent_in_speech():
    # the comma stops "squared"/"to the power of" attaching to the wrong thing
    pow_node = tree("(x+1)^2=9")["children"][0]
    assert "the group x plus 1, to the power of 2" in tree("(x+1)^2=9")["spoken_detailed"]
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
    # 3x^2 = 12 as Mul(3, Pow(x, 2)): 3 multiplies a power, it is not "of x" directly
    root = build(op("Mul", [N(3), Pw(X(1), N(2, 3), 1, 4)], 0, 4), N(12, 7))
    three, pow_node = root["children"][0]["children"]
    assert three["role"] == "number"
    assert "coefficient" not in three["spoken_quick"]
    assert pow_node["role"] == "power"
    assert pow_node["children"][1]["role"] == "exponent"


# ---- 4. Fraction (provisional node type) -------------------------------------


def test_fraction_fixture_roles():
    root = tree("(x+1)/2=3")
    frac = root["children"][0]
    num, den = frac["children"]
    assert (frac["role"], frac["type"]) == ("left_side", "Fraction")
    assert (num["role"], num["type"]) == ("operator", "Add")
    assert (den["role"], den["value"]) == ("denominator", 2)


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


def test_fraction_with_negative_numerator():
    root = build(Fr(N(-1), N(2, 3), 0, 4), N(4, 7))
    num = root["children"][0]["children"][0]
    assert num["spoken_quick"] == "Numerator negative 1"
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
    # (1/2)/3 as Fraction(Fraction(1, 2), 3)
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
    # 1/(1/2) as Fraction(1, Fraction(1, 2))
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
    assert "2 times the group x plus 3, plus 5" in root["spoken_detailed"]
    five = root["children"][0]["children"][1]
    assert five["role"] == "constant_term"
    assert "added to the product 2 times the group x plus 3" in five["spoken_context"]


def test_div_node_is_unchanged_and_not_a_fraction():
    # inline division keeps its Phase 1 behaviour
    root = build(op("Div", [X(), N(2, 4)], 0, 5), N(3, 8))
    left = root["children"][0]
    assert (left["type"], left["role"]) == ("Div", "left_side")
    assert [c["role"] for c in left["children"]] == ["variable", "number"]
    inner = build(op("Add", [op("Div", [X(), N(2, 4)], 0, 5), N(1, 8)], 0, 9), N(3, 12))
    div = inner["children"][0]["children"][0]
    assert (div["role"], div["spoken_quick"]) == ("operator", "Division")


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
        "The whole equation. It says that the left side, 2 times the group x plus 3, "
        "has the same value as the right side, 12."
    )
    assert tree("(x+1)/2=3")["spoken_detailed"] == (
        "The whole equation. It says that the left side, the fraction with numerator "
        "x plus 1 and denominator 2, has the same value as the right side, 3."
    )


def test_group_times_group_phrase_has_a_pause():
    assert "the group x plus 1, times the group x minus 2" in tree("(x+1)(x-2)=0")["spoken_detailed"]


def test_group_in_the_denominator_and_numerator():
    # (x + 1)/(x - 2) style: Fraction(Group, Group)
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


# ---- 6. Malformed Group, Pow and Fraction ----------------------------------------


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
    with pytest.raises(ExplorerError, match=rf"Fraction needs 2 child\(ren\), found {n_children}"):
        build(Fr(N(1), N(2, 2)) | {"children": kids}, N(4, 8))


def test_fraction_must_not_have_a_value():
    with pytest.raises(ExplorerError, match="Fraction must not have a 'value'"):
        build(Fr(N(1), N(2, 2)) | {"value": 1}, N(4, 8))


def test_fraction_child_errors_report_the_path():
    bad = Fr(N(1), {"type": "Number", "value": "two", "children": [], "span": [2, 3]})
    with pytest.raises(ExplorerError, match=r"ast\.children\[0\]\.children\[1\]: Number needs"):
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
def test_new_fixtures_preserve_spans_and_order(name):
    def check(ast, ex):
        assert ex["span"] == ast["span"]
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
    source, ast = FIXTURES["x^2+3=7"]
    pow_node = tree("x^2+3=7")["children"][0]["children"][0]
    assert source[slice(*pow_node["span"])] == "x^2"
    assert source[slice(*pow_node["children"][1]["span"])] == "2"
    source, _ = FIXTURES["(x+1)/2=3"]
    frac = tree("(x+1)/2=3")["children"][0]
    assert source[slice(*frac["span"])] == "(x + 1)/2"
    assert source[slice(*frac["children"][1]["span"])] == "2"


def test_nested_group_fixture_spans_nest():
    root = tree("2(3(x+1)+4)=20")
    source = FIXTURES["2(3(x+1)+4)=20"][0]
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
        ("n0.0.1", "constant_term", "Constant term 5"),
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
