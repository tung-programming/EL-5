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
  - node type names are exactly: Number, Variable, Add, Sub, Mul, Pow, Group,
    Equation (Phase 2 adds Sub, Pow, Group; plus the provisional Fraction)

Phase 2 assumptions (all provisional, isolated here):
  - Group has exactly one child (the expression inside the brackets) and its
    span INCLUDES the brackets; the child's span excludes them
  - Pow children are [base, exponent]; the span of "x^2" covers "x^2"
  - a Group directly beside another node ("2(x + 3)") is a Mul of the two
  - Fraction is NOT in plan.md's OwnAST type list. It is a provisional node
    {type: "Fraction", children: [numerator, denominator]} so the explorer has
    something to attach the fraction roles to. Its span covers the whole
    "numerator/denominator" text; when the numerator was typed in brackets,
    e.g. "(x + 1)/2", the span includes the brackets and the numerator's own
    span excludes them (there is no Group node, the brackets only delimit it)
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

# ---------------------------------------------------------------------------
# Phase 2 fixtures: groups, powers, fractions
# ---------------------------------------------------------------------------

# "2(x + 3) = 12"     group multiplied by a number
#  0123456789ABC
SRC_2_GROUP_X_PLUS_3_EQ_12 = "2(x + 3) = 12"
AST_2_GROUP_X_PLUS_3_EQ_12 = _node(
    "Equation",
    [
        _node(
            "Mul",
            [
                _num(2, 0, 1),
                _node(
                    "Group",
                    [_node("Add", [_var(2, 3), _num(3, 6, 7)], 2, 7)],
                    1,
                    8,
                ),
            ],
            0,
            8,
        ),
        _num(12, 11, 13),
    ],
    0,
    13,
)

# "(x + 1)(x - 2) = 0"     two groups multiplied
#  0123456789ABCDEFGHI
SRC_GROUP_TIMES_GROUP = "(x + 1)(x - 2) = 0"
AST_GROUP_TIMES_GROUP = _node(
    "Equation",
    [
        _node(
            "Mul",
            [
                _node("Group", [_node("Add", [_var(1, 2), _num(1, 5, 6)], 1, 6)], 0, 7),
                _node("Group", [_node("Sub", [_var(8, 9), _num(2, 12, 13)], 8, 13)], 7, 14),
            ],
            0,
            14,
        ),
        _num(0, 17, 18),
    ],
    0,
    18,
)

# "2(3(x + 1) + 4) = 20"     group nested inside a group
#  0123456789ABCDEFGHIJ
SRC_NESTED_GROUPS = "2(3(x + 1) + 4) = 20"
AST_NESTED_GROUPS = _node(
    "Equation",
    [
        _node(
            "Mul",
            [
                _num(2, 0, 1),
                _node(
                    "Group",
                    [
                        _node(
                            "Add",
                            [
                                _node(
                                    "Mul",
                                    [
                                        _num(3, 2, 3),
                                        _node(
                                            "Group",
                                            [_node("Add", [_var(4, 5), _num(1, 8, 9)], 4, 9)],
                                            3,
                                            10,
                                        ),
                                    ],
                                    2,
                                    10,
                                ),
                                _num(4, 13, 14),
                            ],
                            2,
                            14,
                        )
                    ],
                    1,
                    15,
                ),
            ],
            0,
            15,
        ),
        _num(20, 18, 20),
    ],
    0,
    20,
)

# "x^2 + 3 = 7"     power inside a sum
#  0123456789A
SRC_X_SQUARED_PLUS_3_EQ_7 = "x^2 + 3 = 7"
AST_X_SQUARED_PLUS_3_EQ_7 = _node(
    "Equation",
    [
        _node(
            "Add",
            [_node("Pow", [_var(0, 1), _num(2, 2, 3)], 0, 3), _num(3, 6, 7)],
            0,
            7,
        ),
        _num(7, 10, 11),
    ],
    0,
    11,
)

# "(x + 1)^2 = 9"     power whose base is a group
#  0123456789ABC
SRC_GROUP_SQUARED = "(x + 1)^2 = 9"
AST_GROUP_SQUARED = _node(
    "Equation",
    [
        _node(
            "Pow",
            [
                _node("Group", [_node("Add", [_var(1, 2), _num(1, 5, 6)], 1, 6)], 0, 7),
                _num(2, 8, 9),
            ],
            0,
            9,
        ),
        _num(9, 12, 13),
    ],
    0,
    13,
)

# "(x + 1)/2 = 3"     provisional Fraction with a sum as numerator
#  0123456789ABC
SRC_FRACTION_X_PLUS_1_OVER_2 = "(x + 1)/2 = 3"
AST_FRACTION_X_PLUS_1_OVER_2 = _node(
    "Equation",
    [
        _node(
            "Fraction",
            [_node("Add", [_var(1, 2), _num(1, 5, 6)], 1, 6), _num(2, 8, 9)],
            0,
            9,
        ),
        _num(3, 12, 13),
    ],
    0,
    13,
)

# "x^2/3 = 4"     fraction whose numerator is a power
#  012345678
SRC_FRACTION_OF_POWER = "x^2/3 = 4"
AST_FRACTION_OF_POWER = _node(
    "Equation",
    [
        _node(
            "Fraction",
            [_node("Pow", [_var(0, 1), _num(2, 2, 3)], 0, 3), _num(3, 4, 5)],
            0,
            5,
        ),
        _num(4, 8, 9),
    ],
    0,
    9,
)

# "(x/2)^2 = 9"     power of a group that holds a fraction
#  0123456789A
SRC_GROUPED_FRACTION_SQUARED = "(x/2)^2 = 9"
AST_GROUPED_FRACTION_SQUARED = _node(
    "Equation",
    [
        _node(
            "Pow",
            [
                _node(
                    "Group",
                    [_node("Fraction", [_var(1, 2), _num(2, 3, 4)], 1, 4)],
                    0,
                    5,
                ),
                _num(2, 6, 7),
            ],
            0,
            7,
        ),
        _num(9, 10, 11),
    ],
    0,
    11,
)

# Every fixture as (source, ast)
FIXTURES = {
    "3x+5=14": (SRC_3X_PLUS_5_EQ_14, AST_3X_PLUS_5_EQ_14),
    "2x+3=9": (SRC_2X_PLUS_3_EQ_9, AST_2X_PLUS_3_EQ_9),
    "2(x+3)=12": (SRC_2_GROUP_X_PLUS_3_EQ_12, AST_2_GROUP_X_PLUS_3_EQ_12),
    "(x+1)(x-2)=0": (SRC_GROUP_TIMES_GROUP, AST_GROUP_TIMES_GROUP),
    "2(3(x+1)+4)=20": (SRC_NESTED_GROUPS, AST_NESTED_GROUPS),
    "x^2+3=7": (SRC_X_SQUARED_PLUS_3_EQ_7, AST_X_SQUARED_PLUS_3_EQ_7),
    "(x+1)^2=9": (SRC_GROUP_SQUARED, AST_GROUP_SQUARED),
    "(x+1)/2=3": (SRC_FRACTION_X_PLUS_1_OVER_2, AST_FRACTION_X_PLUS_1_OVER_2),
    "x^2/3=4": (SRC_FRACTION_OF_POWER, AST_FRACTION_OF_POWER),
    "(x/2)^2=9": (SRC_GROUPED_FRACTION_SQUARED, AST_GROUPED_FRACTION_SQUARED),
}

# Node types the fixtures use. Div and Neg are not used by any fixture (the
# tests build those inline).
FIXTURE_NODE_TYPES = {
    "Number", "Variable", "Add", "Sub", "Mul", "Pow", "Group", "Fraction", "Equation",
}
