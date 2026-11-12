"""Mock OwnAST fixtures for explorer development (test-only).

Owner: Member 4
Shape follows plan.md §10:  OwnAST = {type, value?, children[], span:[start,end]}

These are hand-written stand-ins until Member 1's parser (engine/parser.py)
lands, and they are NOT a statement of what the real parser outputs.
Assumptions for Member 1 / Member 2 to confirm:
  - span is [start, end) in characters of the source string (end exclusive)
  - `value` exists only on Number (a number) and Variable ("x"); other nodes omit it
  - implicit multiplication (3x) is a Mul node whose span covers both factors
  - Equation.children is [left, right]
  - node type names are exactly: Number, Variable, Add, Mul, Equation
"""

from __future__ import annotations


def _num(value, start, end):
    return {"type": "Number", "value": value, "children": [], "span": [start, end]}


def _var(start, end):
    return {"type": "Variable", "value": "x", "children": [], "span": [start, end]}


def _node(type_, children, start, end):
    return {"type": type_, "children": children, "span": [start, end]}


# "3x + 5 = 14"
#  0123456789A   (A = index 10)
SRC_3X_PLUS_5_EQ_14 = "3x + 5 = 14"
AST_3X_PLUS_5_EQ_14 = _node(
    "Equation",
    [
        _node(
            "Add",
            [
                _node("Mul", [_num(3, 0, 1), _var(1, 2)], 0, 2),
                _num(5, 5, 6),
            ],
            0,
            6,
        ),
        _num(14, 9, 11),
    ],
    0,
    11,
)

# "2x + 3 = 9"
#  0123456789
SRC_2X_PLUS_3_EQ_9 = "2x + 3 = 9"
AST_2X_PLUS_3_EQ_9 = _node(
    "Equation",
    [
        _node(
            "Add",
            [
                _node("Mul", [_num(2, 0, 1), _var(1, 2)], 0, 2),
                _num(3, 5, 6),
            ],
            0,
            6,
        ),
        _num(9, 9, 10),
    ],
    0,
    10,
)

# Every fixture as (source, ast)
FIXTURES = {
    "3x+5=14": (SRC_3X_PLUS_5_EQ_14, AST_3X_PLUS_5_EQ_14),
    "2x+3=9": (SRC_2X_PLUS_3_EQ_9, AST_2X_PLUS_3_EQ_9),
}

# Node types the fixtures use. Group, Pow, Div, Sub, Neg arrive in Phase 2.
FIXTURE_NODE_TYPES = {"Number", "Variable", "Add", "Mul", "Equation"}
