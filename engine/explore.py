"""OwnAST -> explorer tree with roles and quick/detailed/context text.

Owner: Member 4
See plan.md §7.6

PROVISIONAL CONTRACT (Phase 1, standalone)
------------------------------------------
Member 1's parser and Member 2's docs/contracts.md do not exist yet, so this
module reads the mock AST shape used in tests/explorer_fixtures.py:

    OwnAST   = {type, value?, children[], span:[start, end]}   (end exclusive)
    types    = Number, Variable, Add, Sub, Mul, Div, Pow, Neg, Equation
               (Group and fraction/power wording arrive in Phase 2: Group is
               rejected with ExplorerError for now, never silently dropped)
    value    = number for Number, "x" for Variable, absent otherwise
    Equation = exactly two children, [left, right]

Output node (plan.md §10 ExplorerNode, plus one extra field, `span`):

    {id, type, role, value, spoken_quick, spoken_detailed, spoken_context,
     span, children[]}

`span` is NOT in the plan §10 ExplorerNode. It is kept because source
positions must be preserved; drop it if Member 2's contract leaves it out.

Everything that depends on the AST representation lives in the "reading the
AST" section. If the real contract differs, adapt `_read_node` only.
Operator-type nodes (Add, Sub, Mul, Div, Pow, Neg) take the "operator" role.
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
# Fallback for a number that is not (yet) one of the roles above, e.g. the
# exponent in x^2 or the 2 in 2*3. Chosen over mislabelling it as a constant.
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
    if node_type == EQUATION:
        return 2
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
    if node.type in _OPERATORS:
        return ROLE_OPERATOR
    # NUMBER from here on
    if ctx.parent is not None and ctx.parent.type == "Mul":
        if any(s.type == VARIABLE for i, s in enumerate(ctx.siblings) if i != ctx.index):
            return ROLE_COEFFICIENT
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
# Spoken text
# ---------------------------------------------------------------------------


def _say_value(node: _Ast) -> str:
    """Plain-word value of a Number/Variable. (speak.py is not available yet.)"""
    if node.type == VARIABLE:
        return str(node.value)
    value = node.value
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(abs(value)) if value < 0 else str(value)
    return f"negative {text}" if value < 0 else text


def _operator_name(node: _Ast) -> str:
    return _OPERATORS[node.type][1]


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
    return f"Number {_say_value(node)}"


def _spoken_detailed(node: _Ast, role: str) -> str:
    if role == ROLE_EQUATION:
        return "The whole equation. Its left side and right side have the same value."
    if role in (ROLE_LEFT, ROLE_RIGHT):
        side = "left" if role == ROLE_LEFT else "right"
        base = f"The {side} side of the equation, on the {side} of the equals sign."
        if node.type in _OPERATORS:
            return f"{base} {_operator_name(node)}. {_OPERATORS[node.type][2]}"
        return f"{base} It is {_say_value(node)}."
    if role == ROLE_COEFFICIENT:
        n = _say_value(node)
        return f"{n} is the coefficient. It tells you x is multiplied by {n}."
    if role == ROLE_VARIABLE:
        return f"{_say_value(node)} is the variable, the unknown number we want to find."
    if role == ROLE_CONSTANT:
        return f"{_say_value(node)} is a constant term, a number on its own that does not multiply x."
    if role == ROLE_OPERATOR:
        return f"{_operator_name(node)}. {_OPERATORS[node.type][2]}"
    return f"{_say_value(node)} is a number."


def _spoken_context(node: _Ast, ctx: _Ctx) -> str:
    """Basic position text. Richer wording ("added to 3x") is Phase 2."""
    if node.type == EQUATION:
        return "This is the whole equation."
    if ctx.is_side_root:
        return f"This is the {ctx.side} side of the equation."
    parent = ctx.parent
    return (
        f"This part is on the {ctx.side} side, inside the "
        f"{_operator_name(parent).lower()}."
    )


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _convert(node: _Ast, path: str, node_id: str, ctx: _Ctx) -> dict:
    """Convert an already-validated node (and, recursively, its children)."""
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
        "spoken_detailed": _spoken_detailed(node, role),
        "spoken_context": _spoken_context(node, ctx),
        "span": list(node.span),
        "children": children,
    }


def build_explorer_tree(ast: Any) -> dict:
    """Convert an OwnAST-like Equation into an ExplorerNode-like tree.

    Pure: the input is not modified. Raises ExplorerError (a ValueError) for a
    malformed tree, a non-Equation root, or an unsupported node type; nodes are
    never silently dropped.
    """
    return _convert(_read_node(ast, "ast"), "ast", _make_id(None, 0), _ROOT_CTX)
