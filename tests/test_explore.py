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
    assert left["spoken_context"] == "This is the left side of the equation."
    assert five["spoken_context"] == "This part is on the left side, inside the addition."
    assert root["children"][1]["spoken_context"] == "This is the right side of the equation."


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
