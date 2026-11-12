"""Mock OwnAST fixtures for explorer development (test-only).

Owner: Member 4
Shape follows docs/contracts.md (the authoritative shared contract):
    OwnAST = {type, value?, children[], span:[start, end]}

These are hand-written stand-ins until Member 1's parser (engine/parser.py)
lands, and they are NOT a statement of what the real parser outputs.
From docs/contracts.md:
  - span is [start, end) in characters of the source string (end exclusive)
  - Number.value is the SOURCE SPELLING, a string ("3", "14"); Variable.value is
    "x"; every other node omits `value` (the contract also allows null)
  - Equation.children is [left, right]; Group has one child; Div has two
  - node type names are exactly: Number, Variable, Add, Sub, Mul, Div, Pow,
    Neg, Group, Equation

Not stated in docs/contracts.md (Member 4 assumptions, to confirm with Member 1):
  - implicit multiplication (3x) is a Mul node whose span covers both factors
  - Group's span INCLUDES the brackets; the child's span excludes them
  - Pow children are [base, exponent]; the span of "x^2" covers "x^2"
  - a Group directly beside another node ("2(x + 3)") is a Mul of the two
  - Div is used for stacked fractions too: there is no Fraction node. Its span
    covers the whole "numerator/denominator" text; when the numerator was typed
    in brackets, e.g. "(x + 1)/2", the span includes the brackets and the
    numerator's own span excludes them (there is no Group node, the brackets
    only delimit it)
"""

from __future__ import annotations


def _num(value, start, end):
    """A Number leaf. `value` is the SOURCE SPELLING, a string (docs/contracts.md);
    an int is accepted here for brevity and spelled with str()."""
    return {"type": "Number", "value": str(value), "children": [], "span": [start, end]}


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

# "(x + 1)/2 = 3"     Div (a fraction) with a sum as numerator
#  0123456789ABC
SRC_FRACTION_X_PLUS_1_OVER_2 = "(x + 1)/2 = 3"
AST_FRACTION_X_PLUS_1_OVER_2 = _node(
    "Equation",
    [
        _node(
            "Div",
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
            "Div",
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
                    [_node("Div", [_var(1, 2), _num(2, 3, 4)], 1, 4)],
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

# ---------------------------------------------------------------------------
# Review fixtures: structures combined, repeated or nested. Same
# conventions as above (spans are [start, end) in the source string; a
# Div whose numerator/denominator was typed in brackets spans the brackets
# while its operand's own span does not).
# ---------------------------------------------------------------------------

# "2(x + 3)^2 - (x - 1)/4 = 5"     multiplier, group inside a power, fraction of a difference
#  0123456789ABCDEF0123456789   (indexes continue 10..25)
SRC_MULTIPLIED_SQUARED_GROUP_MINUS_FRACTION = "2(x + 3)^2 - (x - 1)/4 = 5"
AST_MULTIPLIED_SQUARED_GROUP_MINUS_FRACTION = _node(
    "Equation",
    [
        _node(
            "Sub",
            [
                _node(
                    "Mul",
                    [
                        _num(2, 0, 1),
                        _node(
                            "Pow",
                            [
                                _node("Group", [_node("Add", [_var(2, 3), _num(3, 6, 7)], 2, 7)], 1, 8),
                                _num(2, 9, 10),
                            ],
                            1,
                            10,
                        ),
                    ],
                    0,
                    10,
                ),
                _node(
                    "Div",
                    [_node("Sub", [_var(14, 15), _num(1, 18, 19)], 14, 19), _num(4, 21, 22)],
                    13,
                    22,
                ),
            ],
            0,
            22,
        ),
        _num(5, 25, 26),
    ],
    0,
    26,
)

# "((x + 1)(x - 2) + 3)^2 = 16"     groups nested in a group, the group squared
SRC_NESTED_PRODUCT_OF_GROUPS_SQUARED = "((x + 1)(x - 2) + 3)^2 = 16"
AST_NESTED_PRODUCT_OF_GROUPS_SQUARED = _node(
    "Equation",
    [
        _node(
            "Pow",
            [
                _node(
                    "Group",
                    [
                        _node(
                            "Add",
                            [
                                _node(
                                    "Mul",
                                    [
                                        _node("Group", [_node("Add", [_var(2, 3), _num(1, 6, 7)], 2, 7)], 1, 8),
                                        _node("Group", [_node("Sub", [_var(9, 10), _num(2, 13, 14)], 9, 14)], 8, 15),
                                    ],
                                    1,
                                    15,
                                ),
                                _num(3, 18, 19),
                            ],
                            1,
                            19,
                        )
                    ],
                    0,
                    20,
                ),
                _num(2, 21, 22),
            ],
            0,
            22,
        ),
        _num(16, 25, 27),
    ],
    0,
    27,
)

# "3x^2 - 2x + 1 = -(x - 4)"     quadratic with a negated group on the right
SRC_QUADRATIC_EQ_NEGATED_GROUP = "3x^2 - 2x + 1 = -(x - 4)"
AST_QUADRATIC_EQ_NEGATED_GROUP = _node(
    "Equation",
    [
        _node(
            "Add",
            [
                _node(
                    "Sub",
                    [
                        _node(
                            "Mul",
                            [_num(3, 0, 1), _node("Pow", [_var(1, 2), _num(2, 3, 4)], 1, 4)],
                            0,
                            4,
                        ),
                        _node("Mul", [_num(2, 7, 8), _var(8, 9)], 7, 9),
                    ],
                    0,
                    9,
                ),
                _num(1, 12, 13),
            ],
            0,
            13,
        ),
        _node(
            "Neg",
            [_node("Group", [_node("Sub", [_var(18, 19), _num(4, 22, 23)], 18, 23)], 17, 24)],
            16,
            24,
        ),
    ],
    0,
    24,
)

# "(2x + 1)/(x - 3) = 4"     fraction with a compound numerator and denominator
SRC_FRACTION_OF_SUM_OVER_DIFFERENCE = "(2x + 1)/(x - 3) = 4"
AST_FRACTION_OF_SUM_OVER_DIFFERENCE = _node(
    "Equation",
    [
        _node(
            "Div",
            [
                _node("Add", [_node("Mul", [_num(2, 1, 2), _var(2, 3)], 1, 3), _num(1, 6, 7)], 1, 7),
                _node("Sub", [_var(10, 11), _num(3, 14, 15)], 10, 15),
            ],
            0,
            16,
        ),
        _num(4, 19, 20),
    ],
    0,
    20,
)

# "((x + 1)/2 + 3)/4 = 1"     fraction inside a sum inside a fraction
SRC_NESTED_FRACTIONS = "((x + 1)/2 + 3)/4 = 1"
AST_NESTED_FRACTIONS = _node(
    "Equation",
    [
        _node(
            "Div",
            [
                _node(
                    "Add",
                    [
                        _node(
                            "Div",
                            [_node("Add", [_var(2, 3), _num(1, 6, 7)], 2, 7), _num(2, 9, 10)],
                            1,
                            10,
                        ),
                        _num(3, 13, 14),
                    ],
                    1,
                    14,
                ),
                _num(4, 16, 17),
            ],
            0,
            17,
        ),
        _num(1, 20, 21),
    ],
    0,
    21,
)

# "2(x + 1) + 3(x - 1) = 10"     two group multipliers in one sum
SRC_TWO_MULTIPLIED_GROUPS = "2(x + 1) + 3(x - 1) = 10"
AST_TWO_MULTIPLIED_GROUPS = _node(
    "Equation",
    [
        _node(
            "Add",
            [
                _node(
                    "Mul",
                    [
                        _num(2, 0, 1),
                        _node("Group", [_node("Add", [_var(2, 3), _num(1, 6, 7)], 2, 7)], 1, 8),
                    ],
                    0,
                    8,
                ),
                _node(
                    "Mul",
                    [
                        _num(3, 11, 12),
                        _node("Group", [_node("Sub", [_var(13, 14), _num(1, 17, 18)], 13, 18)], 12, 19),
                    ],
                    11,
                    19,
                ),
            ],
            0,
            19,
        ),
        _num(10, 22, 24),
    ],
    0,
    24,
)

# "(x^2 + 1)^3 = 8"     power inside a group inside a power
SRC_POWER_IN_GROUP_IN_POWER = "(x^2 + 1)^3 = 8"
AST_POWER_IN_GROUP_IN_POWER = _node(
    "Equation",
    [
        _node(
            "Pow",
            [
                _node(
                    "Group",
                    [_node("Add", [_node("Pow", [_var(1, 2), _num(2, 3, 4)], 1, 4), _num(1, 7, 8)], 1, 8)],
                    0,
                    9,
                ),
                _num(3, 10, 11),
            ],
            0,
            11,
        ),
        _num(8, 14, 15),
    ],
    0,
    15,
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

# Node types the fixtures use. Neg appears only in the quadratic review fixture.
FIXTURE_NODE_TYPES = {
    "Number", "Variable", "Add", "Sub", "Mul", "Pow", "Group", "Div", "Neg",
    "Equation",
}

# Review fixtures: kept apart from FIXTURES on purpose. Several older tests walk
# FIXTURES along first children and forbid a repeated sentence, while the context
# text of every node deliberately says on its own which side it is on (it is read
# alone with the C key). These fixtures put a Mul below a Sub, so parent and
# child both say "It is part of the left side of the equation."
REVIEW_FIXTURES = {
    "2(x+3)^2-(x-1)/4=5": (
        SRC_MULTIPLIED_SQUARED_GROUP_MINUS_FRACTION,
        AST_MULTIPLIED_SQUARED_GROUP_MINUS_FRACTION,
    ),
    "((x+1)(x-2)+3)^2=16": (
        SRC_NESTED_PRODUCT_OF_GROUPS_SQUARED,
        AST_NESTED_PRODUCT_OF_GROUPS_SQUARED,
    ),
    "3x^2-2x+1=-(x-4)": (SRC_QUADRATIC_EQ_NEGATED_GROUP, AST_QUADRATIC_EQ_NEGATED_GROUP),
    "(2x+1)/(x-3)=4": (SRC_FRACTION_OF_SUM_OVER_DIFFERENCE, AST_FRACTION_OF_SUM_OVER_DIFFERENCE),
    "((x+1)/2+3)/4=1": (SRC_NESTED_FRACTIONS, AST_NESTED_FRACTIONS),
    "2(x+1)+3(x-1)=10": (SRC_TWO_MULTIPLIED_GROUPS, AST_TWO_MULTIPLIED_GROUPS),
    "(x^2+1)^3=8": (SRC_POWER_IN_GROUP_IN_POWER, AST_POWER_IN_GROUP_IN_POWER),
}

ALL_FIXTURES = {**FIXTURES, **REVIEW_FIXTURES}
