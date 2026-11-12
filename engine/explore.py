"""OwnAST -> explorer tree with roles and quick/detailed/context text.

Owner: Member 4
See plan.md §7.6

PROVISIONAL CONTRACT (Phase 1, standalone)
------------------------------------------
Member 1's parser and Member 2's docs/contracts.md do not exist yet, so this
module reads the mock AST shape used in tests/explorer_fixtures.py:

    OwnAST   = {type, value?, children[], span:[start, end]}   (end exclusive)
    types    = Number, Variable, Add, Sub, Mul, Div, Pow, Neg, Group,
               Equation   (+ the provisional Fraction type, see below)
    value    = number for Number, "x" for Variable, absent otherwise
    Equation = exactly two children, [left, right]
    Group    = exactly one child: the expression inside the brackets
    Pow      = [base, exponent]

PROVISIONAL (Phase 2): Fraction
-------------------------------
plan.md section 7.6 lists a "Fraction" role for `a / b`, but the plan's OwnAST
type list has only Div and no Fraction node, and docs/contracts.md is still
empty. So:

  * Div keeps its Phase 1 meaning: inline division, role "operator", quick
    text "Division". Nothing about Div changed.
  * A separate, provisional node type `Fraction` = [numerator, denominator]
    gets the fraction roles. It is the stacked (a over b) reading of a
    division. If Member 1 / Member 2 decide the parser should emit Div for
    stacked fractions, the one-line fix is to map Div to Fraction in
    `_read_node`; no other code depends on this choice.

Output node (plan.md §10 ExplorerNode, plus one extra field, `span`):

    {id, type, role, value, spoken_quick, spoken_detailed, spoken_context,
     span, children[]}

`span` is NOT in the plan §10 ExplorerNode. It is kept because source
positions must be preserved; drop it if Member 2's contract leaves it out.

Everything that depends on the AST representation lives in the "reading the
AST" section. If the real contract differs, adapt `_read_node` only.
Operator-type nodes (Add, Sub, Mul, Div, Neg) take the "operator" role.
Phase 2 roles: Group -> "group"; Pow -> "power"; Fraction -> "fraction".
A bare Number in a special position gets a position role instead of the
"constant_term" / "coefficient" / "number" fallbacks:
    multiplying a Group      -> "group_multiplier"   (2 in 2(x + 3))
    base of a Pow            -> "base"               (2 in 2^3)
    exponent of a Pow        -> "exponent"           (2 in x^2)
    numerator / denominator  -> "numerator" / "denominator"
Anything else in those positions (a Variable, a Group, an operator...) keeps
its own role, and its position is stated in its detailed and context text.
The two children of an Equation take "left_side" / "right_side" instead, since
the side role wins for the top node of a side (docs/keyboard_guide.md A2).
"""

from __future__ import annotations

from typing import Any, NamedTuple, Optional

__all__ = ["ExplorerError", "build_explorer_tree"]


class ExplorerError(ValueError):
    """The AST is malformed or uses a structure Phase 1 does not support."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EQUATION = "Equation"
NUMBER = "Number"
VARIABLE = "Variable"
GROUP = "Group"
FRACTION = "Fraction"  # PROVISIONAL node type, see module docstring

# node type -> (number of children required, spoken name, detailed action)
_OPERATORS = {
    "Add": (2, "Addition", "It adds its two parts together."),
    "Sub": (2, "Subtraction", "It subtracts the second part from the first."),
    "Mul": (2, "Multiplication", "It multiplies its two parts together."),
    "Div": (2, "Division", "It divides the first part by the second."),
    "Pow": (2, "Power", "It raises the first part to the power of the second."),
    "Neg": (1, "Negation", "It changes the sign of the part inside it."),
}
_SUM_TYPES = {"Add", "Sub"}

# role identifiers
ROLE_EQUATION = "equation"
ROLE_LEFT = "left_side"
ROLE_RIGHT = "right_side"
ROLE_COEFFICIENT = "coefficient"
ROLE_VARIABLE = "variable"
ROLE_CONSTANT = "constant_term"
ROLE_OPERATOR = "operator"
ROLE_GROUP = "group"
ROLE_GROUP_MULTIPLIER = "group_multiplier"
ROLE_POWER = "power"
ROLE_BASE = "base"
ROLE_EXPONENT = "exponent"
ROLE_FRACTION = "fraction"
ROLE_NUMERATOR = "numerator"
ROLE_DENOMINATOR = "denominator"
# Fallback for a number that has none of the roles above, e.g. the 2 in 2*3.
# Chosen over mislabelling it as a constant.
ROLE_NUMBER = "number"


# ---------------------------------------------------------------------------
# Reading the AST (the only place that knows the AST representation)
# ---------------------------------------------------------------------------


class _Ast(NamedTuple):
    type: str
    value: Any
    children: list
    span: tuple


def _read_node(node: Any, path: str) -> _Ast:
    """Validate one AST node and return its fields. Raises ExplorerError."""
    if not isinstance(node, dict):
        raise ExplorerError(f"{path}: node must be a dict, got {type(node).__name__}")
    for key in ("type", "children", "span"):
        if key not in node:
            raise ExplorerError(f"{path}: node is missing '{key}'")

    node_type = node["type"]
    children = node["children"]
    if not isinstance(node_type, str):
        raise ExplorerError(f"{path}: 'type' must be a string")
    if not isinstance(children, list):
        raise ExplorerError(f"{path}: 'children' must be a list")

    span = node["span"]
    if (
        not isinstance(span, (list, tuple))
        or len(span) != 2
        or not all(isinstance(s, int) and not isinstance(s, bool) for s in span)
        or not 0 <= span[0] < span[1]
    ):
        raise ExplorerError(f"{path}: 'span' must be [start, end] with 0 <= start < end")

    value = node.get("value")
    if node_type == NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExplorerError(f"{path}: Number needs a numeric 'value'")
    elif node_type == VARIABLE:
        if not isinstance(value, str) or not value:
            raise ExplorerError(f"{path}: Variable needs a 'value' such as 'x'")
    elif value is not None:
        raise ExplorerError(f"{path}: {node_type} must not have a 'value'")

    expected = _expected_child_count(node_type, path)
    if expected is not None and len(children) != expected:
        raise ExplorerError(
            f"{path}: {node_type} needs {expected} child(ren), found {len(children)}"
        )
    return _Ast(node_type, value, children, (span[0], span[1]))


def _expected_child_count(node_type: str, path: str) -> Optional[int]:
    if node_type in (NUMBER, VARIABLE):
        return 0
    if node_type in (EQUATION, FRACTION):
        return 2
    if node_type == GROUP:
        return 1
    if node_type in _OPERATORS:
        return _OPERATORS[node_type][0]
    raise ExplorerError(f"{path}: unsupported node type '{node_type}'")


# ---------------------------------------------------------------------------
# Context passed down the recursion
# ---------------------------------------------------------------------------


class _Ctx(NamedTuple):
    parent: Optional[_Ast]
    siblings: tuple  # the parent's children, as _Ast, in order
    index: int  # position of this node among its siblings
    side: Optional[str]  # "left" / "right" once below the Equation
    is_side_root: bool  # top node of a side
    term_position: bool  # a standalone number here is a term of a sum / side


_ROOT_CTX = _Ctx(None, (), 0, None, False, False)


def _child_ctx(node: _Ast, siblings: tuple, index: int, ctx: _Ctx) -> _Ctx:
    if node.type == EQUATION:
        return _Ctx(node, siblings, index, ("left", "right")[index], True, True)
    term = node.type in _SUM_TYPES or (node.type == "Neg" and ctx.term_position)
    return _Ctx(node, siblings, index, ctx.side, False, term)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def _determine_role(node: _Ast, ctx: _Ctx) -> str:
    if node.type == EQUATION:
        return ROLE_EQUATION
    if ctx.is_side_root:
        return ROLE_LEFT if ctx.side == "left" else ROLE_RIGHT
    if node.type == VARIABLE:
        return ROLE_VARIABLE
    if node.type == GROUP:
        return ROLE_GROUP
    if node.type == FRACTION:
        return ROLE_FRACTION
    if node.type == "Pow":
        return ROLE_POWER
    if node.type in _OPERATORS:
        return ROLE_OPERATOR
    # NUMBER from here on
    parent = ctx.parent
    if parent is not None and parent.type == "Pow":
        return ROLE_BASE if ctx.index == 0 else ROLE_EXPONENT
    if parent is not None and parent.type == FRACTION:
        return ROLE_NUMERATOR if ctx.index == 0 else ROLE_DENOMINATOR
    if parent is not None and parent.type == "Mul":
        others = [s for i, s in enumerate(ctx.siblings) if i != ctx.index]
        if any(s.type == VARIABLE for s in others):
            return ROLE_COEFFICIENT
        if any(s.type == GROUP for s in others):
            return ROLE_GROUP_MULTIPLIER
    if ctx.term_position:
        return ROLE_CONSTANT
    return ROLE_NUMBER


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------


def _make_id(parent_id: Optional[str], index: int) -> str:
    """Path-based id: root is 'n0', its children 'n0.0', 'n0.1', ..."""
    return "n0" if parent_id is None else f"{parent_id}.{index}"


# ---------------------------------------------------------------------------
# Spoken text: building blocks
#
# Quick text depends only on the node itself, so it is written while the tree
# is built (bottom-up). Detailed and context text need the node's children,
# parent, sibling and side, so they are filled in by a second, top-down pass
# (`_annotate`) that works on the finished ExplorerNode dicts.
#
# TEMPORARY: number/expression wording lives here because engine/speak.py
# (Member 1) is not available yet. Numbers are spoken as digits ("negative 3"),
# and `_phrase` is a minimal stand-in for speak.py's maths-to-words. When
# speak.py lands, replace `_say` and `_phrase` and keep the rest.
# ---------------------------------------------------------------------------

_LEAVES = {NUMBER, VARIABLE}


def _say(type_: str, value: Any) -> str:
    """Plain-word value of a Number/Variable."""
    if type_ == VARIABLE:
        return str(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"negative {abs(value)}" if value < 0 else str(value)


def _say_value(node: _Ast) -> str:
    return _say(node.type, node.value)


def _operator_name(node: _Ast) -> str:
    return _OPERATORS[node.type][1]


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _is_number_times_variable(d: dict) -> bool:
    """Mul of a number and a variable in either order, e.g. 3x or x*3."""
    if d["type"] != "Mul":
        return False
    kinds = sorted(c["type"] for c in d["children"])
    return kinds == [NUMBER, VARIABLE]


def _needs_group(child: dict, parent_type: str, index: int) -> bool:
    """Would reading `child` inside `parent` without a marker be ambiguous?"""
    ct = child["type"]
    if ct in _LEAVES:
        return parent_type == "Pow" and index == 0 and ct == NUMBER and child["value"] < 0
    if ct in (GROUP, FRACTION):
        return False  # their own wording ("the group ...") already delimits them
    if parent_type in ("Neg", "Mul"):
        return ct in _SUM_TYPES
    if parent_type == "Sub":
        return index == 1 and ct in _SUM_TYPES
    if parent_type in ("Div", FRACTION):
        return ct in _SUM_TYPES or (index == 1 and ct in ("Mul", "Div"))
    if parent_type == "Pow":
        return index == 0 or ct in _SUM_TYPES | {"Mul", "Div"}
    return False


def _child_phrase(parent: dict, index: int) -> str:
    """Words for one child, marked as 'the quantity ...' when grouping matters."""
    text = _phrase(parent["children"][index])
    if _needs_group(parent["children"][index], parent["type"], index):
        return f"the quantity {text}"
    return text


def _ends_open(d: dict) -> bool:
    """Does the spoken form of `d` end with a group, fraction or power, so that
    whatever is read next could be mistaken for part of it?"""
    t = d["type"]
    if t in (GROUP, FRACTION, "Pow"):
        return True
    if t in _LEAVES:
        return False
    return _ends_open(d["children"][-1])


def _phrase(d: dict) -> str:
    """Spoken form of a whole sub-expression, e.g. '3x plus 5'."""
    t = d["type"]
    if t in _LEAVES:
        return _say(t, d["value"])
    if t == GROUP:
        return f"the group {_phrase(d['children'][0])}"
    if t == FRACTION:
        num, den = d["children"]
        # a comma keeps "and denominator" from being read as part of the numerator
        sep = "," if _ends_open(num) else ""
        return (
            f"the fraction with numerator {_phrase(num)}{sep} "
            f"and denominator {_phrase(den)}"
        )
    if t == "Neg":
        return f"negative {_child_phrase(d, 0)}"
    if t == "Mul":
        first, second = d["children"]
        if first["type"] == NUMBER and second["type"] == VARIABLE:
            return f"{_say(NUMBER, first['value'])}{second['value']}"
    joiner = {
        "Add": "plus",
        "Sub": "minus",
        "Mul": "times",
        "Div": "divided by",
        "Pow": "to the power of",
    }[t]
    left = _child_phrase(d, 0)
    first = d["children"][0]
    if _ends_open(first) and (t != "Pow" or first["type"] in (GROUP, FRACTION)):
        # "x to the power of 2, plus 3" / "the group x plus 3, times 2": the
        # pause stops what follows sounding like part of the first operand.
        left += ","
    return f"{left} {joiner} {_child_phrase(d, 1)}"


def _label(d: dict) -> str:
    """Noun phrase naming a node by its mathematical role, with its value."""
    t = d["type"]
    if t == NUMBER:
        word = {
            ROLE_COEFFICIENT: "coefficient",
            ROLE_CONSTANT: "constant",
            ROLE_GROUP_MULTIPLIER: "multiplier",
            ROLE_BASE: "base",
            ROLE_EXPONENT: "exponent",
            ROLE_NUMERATOR: "numerator",
            ROLE_DENOMINATOR: "denominator",
        }.get(d["role"], "number")
        return f"the {word} {_say(t, d['value'])}"
    if t == VARIABLE:
        return f"the variable {d['value']}"
    if t == "Neg":
        return f"the negation of {_child_phrase(d, 0)}"
    if t in (GROUP, FRACTION):
        return _phrase(d)  # already starts with "the group" / "the fraction"
    if t == "Mul" and _is_number_times_variable(d):
        return f"the term {_phrase(d)}"
    noun = {
        "Add": "sum", "Sub": "difference", "Mul": "product",
        "Div": "quotient", "Pow": "expression",
    }[t]
    return f"the {noun} {_phrase(d)}"


def _other_child(parent: dict, index: int) -> Optional[dict]:
    kids = parent["children"]
    return kids[1 - index] if len(kids) == 2 else None


def _placement(node: dict, parent: dict, index: int) -> str:
    """Verb phrase saying what `parent` does with `node` (no subject)."""
    ptype = parent["type"]
    if ptype == EQUATION:
        return f"forms the {('left', 'right')[index]} side of the equation"
    if ptype == "Neg":
        return "has its sign changed"
    if ptype == GROUP:
        return "is the content of the group, enclosed by its brackets"
    other = _other_child(parent, index)
    label = _label(other)
    if ptype == "Add":
        return f"is added to {label}"
    if ptype == "Sub":
        return f"has {label} subtracted from it" if index == 0 else f"is subtracted from {label}"
    if ptype == "Mul":
        return f"is multiplied by {label}"
    if ptype == "Div":
        return f"is divided by {label}" if index == 0 else f"divides {label}"
    if ptype == FRACTION:
        if index == 0:
            return f"is the numerator of a fraction whose denominator is {_phrase(other)}"
        return f"is the denominator of a fraction whose numerator is {_phrase(other)}"
    # Pow
    if index == 0:
        return f"is the base, raised to the power {_child_phrase(parent, 1)}"
    return f"is the exponent that {label} is raised to"


def _operation_sentence(node: dict) -> str:
    """'Addition. It combines ...' for an operator node."""
    t = node["type"]
    if t == GROUP:
        return _group_sentence(node)
    if t == FRACTION:
        return _fraction_sentence(node)
    if t == "Pow":
        return _power_sentence(node)
    name = _OPERATORS[t][1]
    kids = node["children"]
    a = _label(kids[0])
    if t == "Neg":
        return f"{name}. It changes the sign of {a}."
    b = _label(kids[1])
    if t == "Add":
        return f"{name}. It combines {a} and {b} by adding them."
    if t == "Sub":
        return f"{name}. It takes {b} away from {a}."
    if t == "Mul":
        text = f"{name}. It combines {a} and {b} by multiplying them."
        if kids[0]["type"] == NUMBER and kids[1]["type"] == VARIABLE:
            n = _say(NUMBER, kids[0]["value"])
            return f"{text} So {_phrase(node)} means {n} times {kids[1]['value']}."
        for g, other in ((1, 0), (0, 1)):
            if kids[g]["type"] == GROUP and kids[other]["type"] == NUMBER:
                m = _say(NUMBER, kids[other]["value"])
                return f"{text} So {m} multiplies the {_entire(kids[g])}."
        return text
    return f"{name}. It divides {a} by {b}."


def _entire(group: dict) -> str:
    """'entire group x plus 3' (a group's phrase already starts with 'the')."""
    return f"entire {_phrase(group)[len('the '):]}"


def _group_sentence(node: dict) -> str:
    inner = node["children"][0]
    return (
        f"Group. The group contains {_phrase(inner)}, which is treated as one "
        f"quantity. The group is the brackets as a whole, and {_label(inner)} is "
        "the expression inside it."
    )


def _power_sentence(node: dict) -> str:
    base, exp = node["children"]
    b = _child_phrase(node, 0)
    e = _child_phrase(node, 1)
    head = f"Power. The base is {b} and the exponent is {e}."
    if exp["type"] == NUMBER and float(exp["value"]).is_integer():
        n = int(exp["value"])
        if n == 2:
            return f"{head} {b} squared means {b} is multiplied by itself: {b} times {b}."
        if n == 3:
            return (
                f"{head} {b} cubed means {b} is used as a factor three times: "
                f"{b} times {b} times {b}."
            )
        if n > 3:
            return f"{head} It means {b} is used as a factor {n} times."
    return f"{head} It means {b} is raised to the power {e}."


def _fraction_sentence(node: dict) -> str:
    num, den = node["children"]
    return (
        f"Fraction. It has {_phrase(num)} as its numerator and {_phrase(den)} as its "
        f"denominator. The numerator is the top part and the denominator is the "
        f"bottom part, so the fraction means {_child_phrase(node, 0)} divided by "
        f"{_child_phrase(node, 1)}."
    )


# ---------------------------------------------------------------------------
# Spoken text: quick (node only)
# ---------------------------------------------------------------------------


def _spoken_quick(node: _Ast, role: str) -> str:
    if role == ROLE_EQUATION:
        return "Equation"
    if role == ROLE_LEFT:
        return "Left side"
    if role == ROLE_RIGHT:
        return "Right side"
    if role == ROLE_COEFFICIENT:
        return f"Coefficient {_say_value(node)}"
    if role == ROLE_VARIABLE:
        return f"Variable {_say_value(node)}"
    if role == ROLE_CONSTANT:
        return f"Constant term {_say_value(node)}"
    if role == ROLE_OPERATOR:
        return _operator_name(node)
    if role == ROLE_GROUP:
        return "Group"
    if role == ROLE_POWER:
        return "Power"
    if role == ROLE_FRACTION:
        return "Fraction"
    named = {
        ROLE_GROUP_MULTIPLIER: "Multiplier",
        ROLE_BASE: "Base",
        ROLE_EXPONENT: "Exponent",
        ROLE_NUMERATOR: "Numerator",
        ROLE_DENOMINATOR: "Denominator",
    }
    if role in named:
        return f"{named[role]} {_say_value(node)}"
    return f"Number {_say_value(node)}"


# ---------------------------------------------------------------------------
# Spoken text: detailed (what the node means)
# ---------------------------------------------------------------------------


_POSITION_NUMBER_ROLES = {
    ROLE_GROUP_MULTIPLIER, ROLE_BASE, ROLE_EXPONENT, ROLE_NUMERATOR, ROLE_DENOMINATOR,
}


def _where_it_sits(node: dict, index: int, parent: Optional[dict]) -> str:
    """Extra sentence for a node whose position matters: inside a power, a
    fraction or a group, or a group anywhere. Empty for plain Phase 1 cases."""
    if parent is None or parent["type"] == EQUATION:
        return ""
    if parent["type"] in ("Pow", FRACTION, GROUP):
        subject = "It"
    elif node["type"] == GROUP:
        subject = "The entire group"
    else:
        return ""
    return f" {subject} {_placement(node, parent, index)}."


def _position_number_detailed(node: dict, parent: Optional[dict]) -> str:
    """Detailed text for a bare number that is a multiplier, base, exponent,
    numerator or denominator."""
    role = node["role"]
    n = _say(NUMBER, node["value"])
    kids = parent["children"]
    if role == ROLE_GROUP_MULTIPLIER:
        group = next(k for k in kids if k["type"] == GROUP)
        return (
            f"{n} is the multiplier of {_phrase(group)}. It multiplies the "
            f"{_entire(group)}, so every part inside the brackets is multiplied by "
            f"{n}. It is not a coefficient, because it multiplies a group and "
            "not the variable."
        )
    if role == ROLE_BASE:
        return (
            f"{n} is the base of the power. It is the number that is multiplied "
            f"by itself, and the exponent {_child_phrase(parent, 1)} says how many times."
        )
    if role == ROLE_EXPONENT:
        b = _child_phrase(parent, 0)
        exp = node["value"]
        if isinstance(exp, float) and exp.is_integer():
            exp = int(exp)
        if exp == 2:
            meaning = f"It indicates that {b} is multiplied by itself."
        elif isinstance(exp, int) and exp > 2:
            meaning = f"It indicates that {b} is used as a factor {n} times."
        else:
            meaning = f"It is the power that {b} is raised to."
        return (
            f"{n} is the exponent. {meaning} It is not a constant term or a "
            "coefficient: it is not added to anything and does not multiply anything. "
            "It only says how many times the base is multiplied."
        )
    if role == ROLE_NUMERATOR:
        return (
            f"{n} is the numerator of the fraction: the top part, which is divided by "
            f"the denominator {_phrase(kids[1])}."
        )
    return (
        f"{n} is the denominator of the fraction: the bottom part, which the "
        f"numerator {_phrase(kids[0])} is divided by. A denominator cannot "
        "be zero."
    )


def _spoken_detailed(node: dict, index: int, parent: Optional[dict]) -> str:
    role, t = node["role"], node["type"]
    if role == ROLE_EQUATION:
        left, right = node["children"]
        return (
            "The whole equation. It says that the left side, "
            f"{_phrase(left)}, has the same value as the right side, {_phrase(right)}."
        )
    if role in (ROLE_LEFT, ROLE_RIGHT):
        side, where = ("left", "before") if role == ROLE_LEFT else ("right", "after")
        base = f"The {side} side of the equation, everything {where} the equals sign."
        if t in _OPERATORS or t in (GROUP, FRACTION):
            return f"{base} It reads {_phrase(node)}. {_operation_sentence(node)}"
        return f"{base} It is just {_label(node)}."
    if role in (ROLE_OPERATOR, ROLE_POWER, ROLE_GROUP, ROLE_FRACTION):
        return _operation_sentence(node) + _where_it_sits(node, index, parent)

    sibling = _other_child(parent, index) if parent is not None else None
    if role in _POSITION_NUMBER_ROLES:
        return _position_number_detailed(node, parent)
    if role == ROLE_COEFFICIENT:
        n = _say(NUMBER, node["value"])
        v = sibling["value"] if sibling else "x"
        return (
            f"{n} is the coefficient of {v}. It tells you {v} is multiplied by {n}, "
            f"so the term means {n} times {v}."
        )
    if role == ROLE_VARIABLE:
        text = f"{node['value']} is the variable. It stands for an unknown number, the value we want to find."
        if sibling is not None and sibling["role"] == ROLE_COEFFICIENT:
            text += f" Here it is multiplied by {_label(sibling)}."
        return text + _where_it_sits(node, index, parent)
    n = _say(NUMBER, node["value"])
    if role == ROLE_CONSTANT:
        text = f"{n} is a constant term: a plain number that does not multiply x."
        if parent is not None and parent["type"] != "Neg":
            text += f" It {_placement(node, parent, index)}."
        elif parent is not None:
            text += " The negation changes its sign."
        return text
    return (
        f"{n} is a plain number here. It is not a coefficient, because it does not "
        "multiply x, and not a constant term, because it is not added or subtracted."
    )


# ---------------------------------------------------------------------------
# Spoken text: context (how the node connects to what surrounds it)
# ---------------------------------------------------------------------------


def _spoken_context(node: dict, index: int, trail: list) -> str:
    role, t = node["role"], node["type"]
    if role == ROLE_EQUATION:
        return "This is the whole equation."
    if not trail:
        return "This part has no surrounding expression to describe."
    parent = trail[-1][0]

    if parent["type"] == EQUATION:
        side = "left" if index == 0 else "right"
        other = _phrase(parent["children"][1 - index])
        if t in _OPERATORS:
            subject = f"The {_OPERATORS[t][1].lower()} expression {_phrase(node)}"
        else:
            subject = _cap(_label(node))
        return (
            f"{subject} forms the {side} side of the equation. "
            f"The {'right' if index == 0 else 'left'} side is {other}."
        )

    side = "left" if trail[1][1] == 0 else "right"
    region = f"It is part of the {side} side of the equation."
    if parent["type"] in (GROUP, "Pow", FRACTION):
        # the enclosing group / power / fraction already says (or its own
        # parent did) which side it is on; don't repeat it down the path
        region = ""
    sibling = _other_child(parent, index)

    if role == ROLE_GROUP_MULTIPLIER:
        n = _say(NUMBER, node["value"])
        return (
            f"The multiplier {n} multiplies the {_entire(sibling)}. "
            f"Together they form the product {_phrase(parent)}. {region}"
        )
    if role == ROLE_BASE:
        n = _say(NUMBER, node["value"])
        return (
            f"The base {n} is raised to the exponent {_child_phrase(parent, 1)}. "
            f"Together they form {_phrase(parent)}. {region}"
        )
    if role == ROLE_EXPONENT:
        n = _say(NUMBER, node["value"])
        return (
            f"The exponent {n} belongs to the base {_child_phrase(parent, 0)}. "
            f"Together they form {_phrase(parent)}. {region}"
        )
    if role in (ROLE_NUMERATOR, ROLE_DENOMINATOR):
        n = _say(NUMBER, node["value"])
        if role == ROLE_NUMERATOR:
            relation = f"The numerator {n} is divided by the denominator {_phrase(sibling)}."
        else:
            relation = f"The denominator {n} divides the numerator {_phrase(sibling)}."
        return f"{relation} Together they form {_phrase(parent)}. {region}"
    if role == ROLE_GROUP:
        return (
            f"{_cap(_label(node))} {_placement(node, parent, index)}. "
            f"It is treated as one quantity. {region}"
        )
    if role == ROLE_COEFFICIENT:
        n, v = _say(NUMBER, node["value"]), sibling["value"]
        return (
            f"The coefficient {n} belongs to the variable {v}: {v} is multiplied by {n}. "
            f"Together they form the term {_phrase(parent)}."
        )
    if role == ROLE_VARIABLE and sibling is not None and sibling["role"] == ROLE_COEFFICIENT:
        return f"The variable {node['value']} is multiplied by {_label(sibling)}. {region}"
    if role == ROLE_CONSTANT:
        n = _say(NUMBER, node["value"])
        return f"The constant term {n} {_placement(node, parent, index)}. {region}"
    return f"{_cap(_label(node))} {_placement(node, parent, index)}. {region}"


def _annotate(node: dict, index: int, trail: list) -> None:
    """Fill spoken_detailed and spoken_context top-down. `trail` is the list of
    (ancestor, that ancestor's index in its own parent), root first."""
    parent = trail[-1][0] if trail else None
    node["spoken_detailed"] = _spoken_detailed(node, index, parent)
    node["spoken_context"] = _spoken_context(node, index, trail).strip()
    for i, child in enumerate(node["children"]):
        _annotate(child, i, trail + [(node, index)])


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _convert(node: _Ast, path: str, node_id: str, ctx: _Ctx) -> dict:
    """Convert an already-validated node (and, recursively, its children).

    spoken_detailed / spoken_context are placeholders here; `_annotate` fills
    them once the whole tree exists.
    """
    if ctx.parent is None and node.type != EQUATION:
        raise ExplorerError(f"{path}: the root must be an Equation, got {node.type}")
    if ctx.parent is not None and node.type == EQUATION:
        raise ExplorerError(f"{path}: an Equation can only be the root")

    role = _determine_role(node, ctx)

    # Read every child first so each one can see its siblings (coefficients).
    kids = tuple(
        _read_node(c, f"{path}.children[{i}]") for i, c in enumerate(node.children)
    )
    children = [
        _convert(kid, f"{path}.children[{i}]", _make_id(node_id, i), _child_ctx(node, kids, i, ctx))
        for i, kid in enumerate(kids)
    ]

    return {
        "id": node_id,
        "type": node.type,
        "role": role,
        "value": node.value,
        "spoken_quick": _spoken_quick(node, role),
        "spoken_detailed": "",
        "spoken_context": "",
        "span": list(node.span),
        "children": children,
    }


def build_explorer_tree(ast: Any) -> dict:
    """Convert an OwnAST-like Equation into an ExplorerNode-like tree.

    Pure: the input is not modified. Raises ExplorerError (a ValueError) for a
    malformed tree, a non-Equation root, or an unsupported node type; nodes are
    never silently dropped.
    """
    root = _convert(_read_node(ast, "ast"), "ast", _make_id(None, 0), _ROOT_CTX)
    _annotate(root, 0, [])
    return root
