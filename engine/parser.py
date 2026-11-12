"""Tokenizer + recursive-descent parser -> OwnAST; to_sympy().

Owner: Member 1
See plan.md §7.1, docs/syntax.md (grammar and rules) and docs/contracts.md (OwnAST JSON).

Public API
    parse(text)          -> Node (type "Equation"), or raises ParseError
    to_sympy(node, evaluate=False)
                         -> SymPy expression; for an Equation, a (left, right) tuple.
                            evaluate=False keeps the student's form (2 + 3 stays 2 + 3);
                            evaluate=True gives normal SymPy (use this for solving)
    bracketed(node)      -> fully bracketed string (used by tests and debugging)
    source_text(node, text) -> the part of the original input a node came from
    walk(node)           -> every node in the tree, parent before children
    Node.to_dict()       -> OwnAST JSON (docs/contracts.md)
    notes(tree)          -> things to tell the student even though the input was accepted
                            (a number was rounded; something is divided by zero)
    undefined_parts(tree)-> the Div nodes that divide by zero
    ParseError           -> .kind, .position, .message, .to_dict()
    X                    -> the shared SymPy symbol for x

Scope: linear equations for classes 1-5, so inputs are kept small (see the limits below).
Division by zero is NOT an error: the input is accepted, the SymPy value of that part
is sympy.nan ("undefined"), and notes() / undefined_parts() report it.

Never uses eval() or sympy.parse_expr(): student input is only ever read by the
tokenizer below.

Try it:  python -m engine.parser "3x + 5 = 14"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterator

import sympy

__all__ = [
    "X", "MAX_LENGTH", "MAX_DEPTH", "MAX_NUMBER", "MAX_DECIMALS", "MAX_EXPONENT",
    "NODE_TYPES", "ERROR_TEMPLATES",
    "Node", "Token", "ParseError",
    "tokenize", "parse", "to_sympy", "bracketed", "source_text", "walk",
    "notes", "undefined_parts",
]

X = sympy.Symbol("x")
"""The one variable. Every module must use this symbol so SymPy sees the same x."""

MAX_LENGTH = 200   # characters; stops huge inputs
MAX_DEPTH = 30     # brackets inside brackets; stops very deep recursion
# Limits for classes 1-5. Change these if the target grade changes.
MAX_NUMBER = 1_000_000  # biggest number a student can type
MAX_DECIMALS = 4        # more decimal places are rounded to 4 (5 rounds up), with a note
MAX_EXPONENT = 10       # powers must be whole numbers from -10 to 10, with no x in them

NODE_TYPES = ("Equation", "Number", "Variable", "Add", "Sub", "Mul", "Div", "Pow", "Neg", "Group")


# --------------------------------------------------------------------------- #
# Tree
# --------------------------------------------------------------------------- #
@dataclass
class Node:
    """One node of the student's equation tree (OwnAST).

    type      one of NODE_TYPES
    children  ordered as in the source: [left, right] for binary ops and Equation,
              [inner] for Neg and Group, [] for Number and Variable
    value     Number: the digits as typed ("3", "2.5", ".5"), or rounded to MAX_DECIMALS
              places if the student typed more; Variable: "x"; else None
    span      (start, end) character offsets in the original input, end exclusive
    implicit  True only for a Mul written without a sign ("3x", "2(x+1)"); False for
              "3*x" and for every other node type
    typed     Number only: what the student actually typed, when `value` was rounded
              (e.g. typed "3.14159", value "3.1416"); otherwise None
    """

    type: str
    children: list["Node"] = field(default_factory=list)
    value: str | None = None
    span: tuple[int, int] = (0, 0)
    implicit: bool = False
    typed: str | None = None

    def to_dict(self) -> dict:
        """OwnAST JSON exactly as described in docs/contracts.md."""
        return {
            "type": self.type,
            "value": self.value,
            "children": [child.to_dict() for child in self.children],
            "span": [self.span[0], self.span[1]],
            "implicit": self.implicit,
            "typed": self.typed,
        }


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
# One template per error kind. Messages are read aloud, so they quote the
# student's own text instead of giving character positions.
#   {before}  -> 'after "3x +"'  (text before the problem) or 'at the start'
#   {upto}    -> '"3x +"'        (text up to and including the problem)
ERROR_TEMPLATES: dict[str, str] = {
    "empty": "The box is empty. Type an equation, for example 3x + 5 = 14.",
    "too_long": "The equation is too long. Please keep it under {limit} characters.",
    "too_deep": "There are too many brackets inside brackets {before}. Please simplify the equation.",
    "number_too_large": "The number {number} is too big. Please use numbers up to {limit}.",
    "unsupported_exponent": "I can only use whole-number powers from -{limit} to {limit}, "
                            "and {upto} doesn't fit that.",
    "variable_exponent": "Powers with x in them, like in {upto}, aren't supported.",
    "power_too_large": "{upto} gets too big for me to check. Please use smaller numbers or powers.",
    "bad_symbol": 'I don\'t understand "{symbol}" {before}.{hint}',
    "bad_number": "The number {before} is not written correctly. Write decimals like 2.5.",
    "no_equals": "There is no equals sign. An equation needs exactly one.",
    "many_equals": "There is more than one equals sign. An equation needs exactly one.",
    "empty_side": "The {side} side of the equals sign is empty.",
    "missing_operand": "Something is missing after {upto}.",
    "double_sign": "There are two signs in a row in {upto}. For a double negative, use brackets, like -(-3).",
    "adjacent": "In {upto}, two things are next to each other with nothing between them. "
                "If you meant to multiply, put * between them.",
    "unclosed": "The bracket {before} is never closed.",
    "extra_close": "The closing bracket {before} has no opening bracket.",
    "empty_brackets": "The brackets {before} are empty.",
    "ambiguous_division": 'I\'m not sure what "{snippet}" means. Please add brackets: type {option_a} or {option_b}.',
    "ambiguous_exponent": 'I\'m not sure what "{snippet}" means. Please add brackets: type {option_a} or {option_b}.',
    "unexpected": "I didn't expect the {symbol} {before}.",
}

_SNIPPET_LIMIT = 20


def _quote_tail(text: str) -> str:
    text = text.strip()
    if len(text) > _SNIPPET_LIMIT:
        text = "…" + text[-_SNIPPET_LIMIT:].lstrip()
    return f'"{text}"'


class ParseError(ValueError):
    """Raised for any input the parser can't accept.

    kind      key of ERROR_TEMPLATES (stable; tests check this, not the wording)
    position  zero-based character offset of the problem in the original input
    message   student-friendly sentence, safe to show and read aloud
    """

    def __init__(self, kind: str, position: int, text: str = "", upto: int | None = None, **details):
        self.kind = kind
        self.position = position
        self.details = details
        upto = position if upto is None else upto
        before = text[:position].strip()
        fields = {
            "before": f"after {_quote_tail(before)}" if before else "at the start",
            "upto": _quote_tail(text[:upto]) if text[:upto].strip() else '"the start"',
            **details,
        }
        self.message = ERROR_TEMPLATES[kind].format(**fields)
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "position": self.position, "message": self.message}


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Token:
    kind: str    # "num", "x", "+", "-", "*", "/", "^", "(", ")", "=", "end"
    text: str    # as typed
    start: int
    end: int


_DIGITS = "0123456789"           # ASCII only; other scripts' digits are rejected
_SIMPLE = "+-*/^()="
_UNICODE_OPS = {
    "−": "-",   # − minus sign
    "–": "-",   # – en dash (speech-to-text often produces it)
    "×": "*",   # ×
    "·": "*",   # · middle dot
    "⋅": "*",   # ⋅ dot operator
    "∗": "*",   # ∗ asterisk operator
    "÷": "/",   # ÷
}
_SUPERSCRIPT_DIGITS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}
_SUPERSCRIPT_MINUS = "⁻"    # ⁻


def _hint_for(ch: str) -> str:
    if ch.isalpha():
        return " Only the letter x can be used as the variable."
    if ch in "[]{}":
        return " Use round brackets ( and )."
    if ch == ",":
        return " Write decimals with a point, like 2.5."
    return ""


def tokenize(text: str) -> list[Token]:
    """Split the input into tokens. Always ends with an "end" token."""
    tokens: list[Token] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        # numbers: 3  14  2.5  .5   (not "5." or "1.2.3")
        if ch in _DIGITS or (ch == "." and i + 1 < n and text[i + 1] in _DIGITS):
            j = i
            while j < n and text[j] in _DIGITS:
                j += 1
            if j < n and text[j] == ".":
                j += 1
                if j >= n or text[j] not in _DIGITS:
                    raise ParseError("bad_number", i, text)
                while j < n and text[j] in _DIGITS:
                    j += 1
            if j < n and text[j] == ".":
                raise ParseError("bad_number", i, text)
            tokens.append(Token("num", text[i:j], i, j))
            i = j
            continue
        if ch == ".":
            raise ParseError("bad_number", i, text)

        if ch == "*" and text.startswith("**", i):
            tokens.append(Token("^", "**", i, i + 2))
            i += 2
            continue
        if ch in _SIMPLE:
            tokens.append(Token(ch, ch, i, i + 1))
            i += 1
            continue
        if ch in "xX":
            tokens.append(Token("x", ch, i, i + 1))
            i += 1
            continue
        if ch in _UNICODE_OPS:
            tokens.append(Token(_UNICODE_OPS[ch], ch, i, i + 1))
            i += 1
            continue

        # superscript powers: x²  x³  x¹⁰  x⁻¹  ->  ^ [-] number
        if ch in _SUPERSCRIPT_DIGITS or ch == _SUPERSCRIPT_MINUS:
            j = i + 1 if ch == _SUPERSCRIPT_MINUS else i
            k = j
            while k < n and text[k] in _SUPERSCRIPT_DIGITS:
                k += 1
            if k == j:
                raise ParseError("bad_symbol", i, text, symbol=ch, hint=" Write powers with ^, like x^-1.")
            tokens.append(Token("^", text[i:k], i, k))
            if ch == _SUPERSCRIPT_MINUS:
                tokens.append(Token("-", ch, i, i + 1))
            digits = "".join(_SUPERSCRIPT_DIGITS[c] for c in text[j:k])
            tokens.append(Token("num", digits, j, k))
            i = k
            continue

        raise ParseError("bad_symbol", i, text, symbol=ch, hint=_hint_for(ch))

    tokens.append(Token("end", "", n, n))
    return tokens


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
#   equation := expr '=' expr
#   expr     := term (('+' | '-') term)*
#   term     := unary (('*' | '/') unary | <implicit> power)*
#   unary    := ('+' | '-') power | power          one sign at most
#   power    := primary ('^' unary)?               right-associative
#   primary  := NUMBER | 'x' | '(' expr ')'
#
# Each level calls the next, tighter level, so precedence is built into the
# shape of the tree. Loops give left-to-right grouping (8-3-2 = (8-3)-2);
# recursion in `power` gives right-to-left grouping (2^3^2 = 2^(3^2)).

_OPERATORS = ("+", "-", "*", "/", "^")
_OPERAND_CANNOT_START = ("end", "=", ")", "*", "/", "^")
_TOKEN_WORDS = {
    "+": "plus sign", "-": "minus sign", "*": "times sign", "/": "division sign",
    "^": "power sign", "=": "equals sign", "(": "opening bracket", ")": "closing bracket",
    "end": "end", "num": "number", "x": "x",
}


def _x_power(node: Node) -> int:
    """How high a power of x this part can reach through nested powers: (x^2)^5 -> 10."""
    if node.type == "Variable":
        return 1
    if node.type == "Pow":
        base_power = _x_power(node.children[0])
        exponent = to_sympy(node.children[1], evaluate=True)
        return base_power * int(abs(exponent)) if exponent.is_Integer else base_power
    return max((_x_power(child) for child in node.children), default=0)


def _round_number(digits: str) -> tuple[str, str | None]:
    """Round to MAX_DECIMALS places, school style (5 rounds up).
    Returns (value, typed): typed is the original text if rounding changed it, else None."""
    whole, _, fraction = digits.partition(".")
    if len(fraction) <= MAX_DECIMALS:
        return digits, None
    rounded = Decimal(digits).quantize(Decimal(1).scaleb(-MAX_DECIMALS), rounding=ROUND_HALF_UP)
    text = format(rounded.normalize(), "f")         # 2.99999 -> "3", 3.14159 -> "3.1416"
    return text, digits


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0
        self.depth = 0

    # helpers --------------------------------------------------------------
    def peek(self) -> Token:
        return self.tokens[self.i]

    def take(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def error(self, kind: str, position: int, upto: int | None = None, **details) -> ParseError:
        return ParseError(kind, position, self.text, upto, **details)

    def snippet(self, start: int, end: int) -> str:
        return self.text[start:end].strip()

    # grammar --------------------------------------------------------------
    def equation(self) -> Node:
        if self.peek().kind == "=":
            raise self.error("empty_side", self.peek().start, side="left")
        left = self.expr()

        tok = self.peek()
        if tok.kind == "end":
            raise self.error("no_equals", tok.start)
        if tok.kind == ")":
            raise self.error("extra_close", tok.start)
        if tok.kind != "=":
            raise self.error("unexpected", tok.start, symbol=_TOKEN_WORDS.get(tok.kind, tok.text))
        self.take()

        tok = self.peek()
        if tok.kind == "end":
            raise self.error("empty_side", tok.start, side="right")
        if tok.kind == "=":
            raise self.error("many_equals", tok.start)
        right = self.expr()

        tok = self.peek()
        if tok.kind == "=":
            raise self.error("many_equals", tok.start)
        if tok.kind == ")":
            raise self.error("extra_close", tok.start)
        if tok.kind != "end":
            raise self.error("unexpected", tok.start, symbol=_TOKEN_WORDS.get(tok.kind, tok.text))
        return Node("Equation", [left, right], span=(left.span[0], right.span[1]))

    def expr(self) -> Node:
        node = self.term()
        while self.peek().kind in ("+", "-"):
            op = self.take()
            right = self.term()
            node = Node("Add" if op.kind == "+" else "Sub", [node, right], span=(node.span[0], right.span[1]))
        return node

    def term(self) -> Node:
        node = self.unary()
        while True:
            tok = self.peek()
            if tok.kind in ("*", "/"):
                self.take()
                right = self.unary()
                if tok.kind == "/":
                    if self.peek().kind in ("x", "("):
                        self._ambiguous("ambiguous_division", "/", node, right)
                node = Node("Mul" if tok.kind == "*" else "Div", [node, right], span=(node.span[0], right.span[1]))
            elif tok.kind in ("x", "("):
                right = self.power()
                node = Node("Mul", [node, right], span=(node.span[0], right.span[1]), implicit=True)
            elif tok.kind == "num":
                raise self.error("adjacent", tok.start, upto=tok.end)
            else:
                return node

    def unary(self) -> Node:
        tok = self.peek()
        if tok.kind not in ("+", "-"):
            return self.power()
        self.take()
        nxt = self.peek()
        if nxt.kind in ("+", "-"):
            raise self.error("double_sign", nxt.start, upto=nxt.end)
        if nxt.kind in _OPERAND_CANNOT_START:
            raise self.error("missing_operand", tok.start, upto=tok.end)
        operand = self.power()
        if tok.kind == "+":
            return operand                      # unary plus changes nothing
        return Node("Neg", [operand], span=(tok.start, operand.span[1]))

    def power(self) -> Node:
        base = self.primary()
        if self.peek().kind != "^":
            return base
        caret = self.take()
        if self.peek().kind in _OPERAND_CANNOT_START:
            raise self.error("missing_operand", caret.start, upto=caret.end)
        exponent = self.unary()                 # allows 2^-3; recursion makes 2^3^2 = 2^(3^2)
        self._check_exponent_size(exponent)
        if self.peek().kind == "x":
            self._ambiguous("ambiguous_exponent", "^", base, exponent)
        node = Node("Pow", [base, exponent], span=(base.span[0], exponent.span[1]))
        self._check_power_result(node)
        return node

    def primary(self) -> Node:
        tok = self.take()
        if tok.kind == "num":
            value, typed = _round_number(tok.text)
            if Decimal(value) > MAX_NUMBER:
                raise self.error("number_too_large", tok.start, upto=tok.end,
                                 number=tok.text, limit=f"{MAX_NUMBER:,}")
            return Node("Number", value=value, span=(tok.start, tok.end), typed=typed)
        if tok.kind == "x":
            return Node("Variable", value="x", span=(tok.start, tok.end))
        if tok.kind == "(":
            if self.peek().kind == ")":
                raise self.error("empty_brackets", tok.start)
            self.depth += 1
            if self.depth > MAX_DEPTH:
                raise self.error("too_deep", tok.start)
            inner = self.expr()
            close = self.peek()
            if close.kind != ")":
                if close.kind in ("end", "="):
                    raise self.error("unclosed", tok.start)
                raise self.error("unexpected", close.start, symbol=_TOKEN_WORDS.get(close.kind, close.text))
            self.take()
            self.depth -= 1
            return Node("Group", [inner], span=(tok.start, close.end))

        # Not something that can start an operand.
        prev = self.tokens[self.i - 2] if self.i >= 2 else None
        if prev is not None and prev.kind in _OPERATORS:
            raise self.error("missing_operand", prev.start, upto=prev.end)
        if tok.kind == ")":
            raise self.error("extra_close", tok.start)
        raise self.error("unexpected", tok.start, symbol=_TOKEN_WORDS.get(tok.kind, tok.text))

    def _check_exponent_size(self, exponent: Node) -> None:
        """Powers must be whole numbers from -MAX_EXPONENT to MAX_EXPONENT, with no x.
        Inner powers were already checked when they were parsed, so evaluating is cheap."""
        span = exponent.span
        if any(n.type == "Variable" for n in walk(exponent)):
            raise self.error("variable_exponent", span[0], upto=span[1])
        value = to_sympy(exponent, evaluate=True)
        if value is sympy.nan:
            return                                  # divides by zero: undefined, reported by notes()
        if not (value.is_Integer and abs(value) <= MAX_EXPONENT):
            raise self.error("unsupported_exponent", span[0], upto=span[1], limit=MAX_EXPONENT)

    def _check_power_result(self, node: Node) -> None:
        """Stop powers of powers from blowing up: ((9^10)^10)^10 has billions of digits.
        Number-only powers must come out at most MAX_NUMBER in size; powers of x must
        stay at most x^MAX_EXPONENT, e.g. (x^2)^5 is fine but (x^2)^6 is x^12."""
        base = node.children[0]
        if any(n.type == "Variable" for n in walk(base)):
            if _x_power(node) > MAX_EXPONENT:
                raise self.error("power_too_large", node.span[0], upto=node.span[1])
            return
        value = to_sympy(node, evaluate=True)       # cheap: the base is already known to be small
        if value.is_finite and value.is_number and abs(value) > MAX_NUMBER:
            raise self.error("power_too_large", node.span[0], upto=node.span[1])

    def _ambiguous(self, kind: str, op: str, left: Node, right: Node) -> None:
        """Raise an 'ambiguous' error that offers both bracketed readings."""
        following = self.power()                # the factor that made it ambiguous
        a = self.snippet(*left.span)
        b = self.snippet(*right.span)
        c = self.snippet(*following.span)
        raise self.error(
            kind, left.span[0], upto=following.span[1],
            snippet=self.snippet(left.span[0], following.span[1]),
            option_a=f"{a}{op}({b}{c})",
            option_b=f"({a}{op}{b}){c}",
        )


def parse(text: str) -> Node:
    """Parse one equation. Returns the Equation node or raises ParseError."""
    if not isinstance(text, str):
        raise TypeError("parse() expects a string")
    if not text.strip():
        raise ParseError("empty", 0, text)
    if len(text) > MAX_LENGTH:
        raise ParseError("too_long", MAX_LENGTH, text, limit=MAX_LENGTH)
    return _Parser(text).equation()


# --------------------------------------------------------------------------- #
# Conversions and helpers
# --------------------------------------------------------------------------- #
def to_sympy(node: Node, evaluate: bool = False):
    """Convert to SymPy. Numbers become exact Rationals ("0.1" -> 1/10), never floats.
    For an Equation, returns (left, right).

    evaluate=False (default) keeps the student's form: 2 + 3 stays 2 + 3, so you
        can see what they wrote.
    evaluate=True gives ordinary SymPy expressions. Use this for solving and
        simplifying: SymPy's simplify() can crash on some unevaluated expressions
        (found by fuzzing), and evaluated ones are also faster.
        Anything divided by zero becomes sympy.nan ("undefined"), and so does any
        side containing it (x + nan is nan).
    """
    t = node.type
    if t == "Equation":
        return to_sympy(node.children[0], evaluate), to_sympy(node.children[1], evaluate)
    if t == "Number":
        return sympy.Rational(node.value)
    if t == "Variable":
        return X
    if t == "Group":
        return to_sympy(node.children[0], evaluate)
    if t == "Neg":
        inner = node.children[0]
        if inner.type == "Number":                       # -4 is just the number -4
            return -sympy.Rational(inner.value)
        return sympy.Mul(sympy.Integer(-1), to_sympy(inner, evaluate), evaluate=evaluate)

    a, b = (to_sympy(child, evaluate) for child in node.children)
    if evaluate:
        if t == "Div" and b.is_zero:
            return sympy.nan                        # dividing by zero is undefined
        if t == "Pow" and a.is_zero and b.is_negative:
            return sympy.nan                        # 0^-1 = 1/0, also undefined
        return {"Add": lambda: a + b, "Sub": lambda: a - b, "Mul": lambda: a * b,
                "Div": lambda: a / b, "Pow": lambda: a ** b}[t]()
    if t == "Add":
        return sympy.Add(a, b, evaluate=False)
    if t == "Sub":
        return sympy.Add(a, sympy.Mul(sympy.Integer(-1), b, evaluate=False), evaluate=False)
    if t == "Mul":
        return sympy.Mul(a, b, evaluate=False)
    if t == "Div":
        return sympy.Mul(a, sympy.Pow(b, sympy.Integer(-1), evaluate=False), evaluate=False)
    if t == "Pow":
        return sympy.Pow(a, b, evaluate=False)
    raise ValueError(f"unknown node type {t!r}")


_BRACKETED_OPS = {"Add": "+", "Sub": "-", "Div": "/", "Pow": "^"}


def bracketed(node: Node) -> str:
    """Fully bracketed form, used by tests: "(a + b)", "(a · b)" for implicit *,
    "(a * b)" for explicit *, "(-a)", "[a]" for the student's own brackets."""
    t = node.type
    if t in ("Number", "Variable"):
        return node.value
    if t == "Neg":
        return f"(-{bracketed(node.children[0])})"
    if t == "Group":
        return f"[{bracketed(node.children[0])}]"
    a, b = (bracketed(child) for child in node.children)
    if t == "Equation":
        return f"{a} = {b}"
    op = ("·" if node.implicit else "*") if t == "Mul" else _BRACKETED_OPS[t]
    return f"({a} {op} {b})"


def source_text(node: Node, text: str) -> str:
    """The part of the original input this node covers, e.g. "3x" or "(x + 3)"."""
    return text[node.span[0]:node.span[1]]


def walk(node: Node) -> Iterator[Node]:
    """Every node in the tree, parent first, then children left to right."""
    yield node
    for child in node.children:
        yield from walk(child)


def undefined_parts(tree: Node) -> list[Node]:
    """Parts that divide by zero: x/0, x/(2-2), x/(x-x), and powers like 0^-1."""
    found = []
    for n in walk(tree):
        if n.type == "Div" and to_sympy(n.children[1], evaluate=True).is_zero:
            found.append(n)
        elif n.type == "Pow":
            base, exponent = (to_sympy(c, evaluate=True) for c in n.children)
            if base.is_zero and exponent.is_negative:
                found.append(n)
    return found


def notes(tree: Node, text: str) -> list[str]:
    """Things to tell the student even though their input was accepted."""
    messages = []
    for n in walk(tree):
        if n.type == "Number" and n.typed is not None:
            messages.append(f"I rounded {n.typed} to {n.value}, because I use up to {MAX_DECIMALS} decimal places.")
    for n in undefined_parts(tree):
        messages.append(f"{source_text(n, text).strip()} divides by zero, which is undefined.")
    return messages


if __name__ == "__main__":
    import json
    import sys

    from engine.speak import to_words

    source = " ".join(sys.argv[1:]) or "3x + 5 = 14"
    try:
        tree = parse(source)
    except ParseError as err:
        print(f"ParseError [{err.kind}] at {err.position}: {err.message}")
        sys.exit(1)
    left, right = to_sympy(tree)
    print("input     :", source)
    print("bracketed :", bracketed(tree))
    print("sympy     :", left, "=", right)
    print("spoken    :", to_words(tree))
    print("json      :", json.dumps(tree.to_dict()))
