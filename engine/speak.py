"""Math -> spoken words (x^2 -> 'x squared').

Owner: Member 1
See plan.md §7.5 and docs/syntax.md ("Note for speech").

Public API
    to_words(node)          -> words for any OwnAST node (a whole equation or one part)
    say(text)               -> parse(text) then to_words; raises ParseError on bad input
    number_to_words(digits) -> "14" -> "fourteen", "2.5" -> "two point five"

Rules
- The speech follows the student's own tree, including their brackets, so it is
  exactly as unambiguous as what they typed. Brackets are read as
  "open bracket ... close bracket".
- "minus" is subtraction and "negative" is a negative number: 2 - -3 is
  "two minus negative three".
- A coefficient joins its variable without "times": "three x", "negative three x squared".
- A complicated exponent ends with "end power", so 2^3^2 can't be heard as (2^3)^2.
- -x^2 is "negative of x squared", so it isn't confused with (-x)^2.
"""
from __future__ import annotations

from engine.parser import Node, parse

__all__ = ["to_words", "say", "number_to_words"]

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = [(10**9, "billion"), (10**6, "million"), (1000, "thousand")]


def _under_thousand(n: int) -> str:
    words = []
    if n >= 100:
        words.append(f"{_ONES[n // 100]} hundred")
        n %= 100
    if n >= 20:
        words.append(_TENS[n // 10] if n % 10 == 0 else f"{_TENS[n // 10]} {_ONES[n % 10]}")
    elif n > 0:
        words.append(_ONES[n])
    return " ".join(words)


def _integer_to_words(digits: str) -> str:
    n = int(digits)
    if n >= 10**12:                      # too big to say naturally: read digit by digit
        return " ".join(_ONES[int(d)] for d in digits.lstrip("0"))
    if n == 0:
        return "zero"
    words = []
    for scale, name in _SCALES:
        if n >= scale:
            words.append(f"{_under_thousand(n // scale)} {name}")
            n %= scale
    if n:
        words.append(_under_thousand(n))
    return " ".join(words)


def number_to_words(digits: str) -> str:
    """Digits as typed -> words. No "and" ("one hundred five"), so it is never
    confused with "plus"."""
    whole, _, fraction = digits.partition(".")
    words = _integer_to_words(whole or "0")
    if fraction:
        words += " point " + " ".join(_ONES[int(d)] for d in fraction)
    return words


def _is_closed(node: Node) -> bool:
    """Something whose end is obvious when spoken: a number, x, a bracketed group,
    or a negative of one of those. Used to decide whether an exponent needs "end power"."""
    if node.type == "Neg":
        node = node.children[0]
    return node.type in ("Number", "Variable", "Group")


def _is_number_like(node: Node) -> bool:
    """3 or -3: something that can be a coefficient."""
    return node.type == "Number" or (node.type == "Neg" and node.children[0].type == "Number")


def _is_x_term(node: Node) -> bool:
    """x, or a power of x: what a coefficient attaches to."""
    return node.type == "Variable" or (node.type == "Pow" and node.children[0].type == "Variable")


def _power(node: Node) -> str:
    base, exponent = node.children
    base_words = to_words(base)
    if exponent.type == "Number" and exponent.value == "2":
        return f"{base_words} squared"
    if exponent.type == "Number" and exponent.value == "3":
        return f"{base_words} cubed"
    words = f"{base_words} to the power of {to_words(exponent)}"
    return words if _is_closed(exponent) else f"{words}, end power"


def to_words(node: Node) -> str:
    t = node.type
    if t == "Equation":
        left, right = node.children
        return f"{to_words(left)} equals {to_words(right)}"
    if t == "Number":
        return number_to_words(node.value)
    if t == "Variable":
        return "x"
    if t == "Group":
        return f"open bracket {to_words(node.children[0])} close bracket"
    if t == "Neg":
        inner = node.children[0]
        if inner.type in ("Number", "Variable", "Group"):
            return f"negative {to_words(inner)}"
        return f"negative of {to_words(inner)}"
    if t == "Pow":
        return _power(node)

    left, right = node.children
    if t == "Add":
        return f"{to_words(left)} plus {to_words(right)}"
    if t == "Sub":
        return f"{to_words(left)} minus {to_words(right)}"
    if t == "Div":
        return f"{to_words(left)} over {to_words(right)}"
    if t == "Mul":
        if node.implicit and _is_number_like(left) and _is_x_term(right):
            return f"{to_words(left)} {to_words(right)}"
        return f"{to_words(left)} times {to_words(right)}"
    raise ValueError(f"unknown node type {t!r}")


def say(text: str) -> str:
    """Parse and speak in one step: say("3x + 5 = 14") -> "three x plus five equals fourteen"."""
    return to_words(parse(text))
