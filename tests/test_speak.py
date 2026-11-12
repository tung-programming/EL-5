"""Tests for engine/speak.py (math -> spoken words).

Owner: Member 1
See plan.md §7.5 and docs/syntax.md ("Note for speech")
"""
import pytest

from engine.parser import ParseError, parse
from engine.speak import number_to_words, say, to_words


@pytest.mark.parametrize("text, words", [
    # basics
    ("3x + 5 = 14",    "three x plus five equals fourteen"),
    ("3*x = 6",        "three times x equals six"),
    ("x/2 = 3",        "x over two equals three"),
    ("2x/3 = 4",       "two x over three equals four"),
    ("2.5x = 5",       "two point five x equals five"),
    (".5x = 1",        "zero point five x equals one"),
    # brackets
    ("2(x+3) = 10",    "two times open bracket x plus three close bracket equals ten"),
    ("x(x+1) = 0",     "x times open bracket x plus one close bracket equals zero"),
    ("(x+1)(x-1) = 0", "open bracket x plus one close bracket times open bracket x minus one close bracket equals zero"),
    ("-(x+1) = 2",     "negative open bracket x plus one close bracket equals two"),
    # minus vs negative
    ("x - 3 = 1",      "x minus three equals one"),
    ("x = -3",         "x equals negative three"),
    ("2 - -3 = x",     "two minus negative three equals x"),
    ("2*-3 = x",       "two times negative three equals x"),
    ("-x = 3",         "negative x equals three"),
    # coefficients
    ("-3x = 6",        "negative three x equals six"),
    ("3x^2 = 12",      "three x squared equals twelve"),
    ("-3x^2 = 6",      "negative three x squared equals six"),
    # powers
    ("x^2 = 4",        "x squared equals four"),
    ("x^3 = 8",        "x cubed equals eight"),
    ("x^5 = 1",        "x to the power of five equals one"),
    ("x^-1 = 2",       "x to the power of negative one equals two"),
    ("2^-3 = x",       "two to the power of negative three equals x"),
    ("(x+1)^2 = 9",    "open bracket x plus one close bracket squared equals nine"),
    ("2^(1+2) = 8",    "two to the power of open bracket one plus two close bracket equals eight"),
    ("x/0 = 1",        "x over zero equals one"),
    ("2^3^2 = x",      "two to the power of three squared, end power equals x"),
    # negatives with powers: must sound different
    ("-x^2 = -4",      "negative of x squared equals negative four"),
    ("(-x)^2 = 4",     "open bracket negative x close bracket squared equals four"),
    ("-3^2 = -9",      "negative of three squared equals negative nine"),
    ("(-3)^2 = 9",     "open bracket negative three close bracket squared equals nine"),
])
def test_say(text, words):
    assert say(text) == words


def test_any_part_of_the_tree_can_be_spoken():
    left, right = parse("3x + 5 = 14").children
    assert to_words(left) == "three x plus five"
    assert to_words(left.children[0]) == "three x"
    assert to_words(right) == "fourteen"


def test_minus_x_squared_and_its_square_differ():
    assert say("-x^2 = 1") != say("(-x)^2 = 1")


@pytest.mark.parametrize("digits, words", [
    ("0", "zero"),
    ("7", "seven"),
    ("13", "thirteen"),
    ("20", "twenty"),
    ("21", "twenty one"),
    ("100", "one hundred"),
    ("105", "one hundred five"),
    ("115", "one hundred fifteen"),
    ("999", "nine hundred ninety nine"),
    ("1000", "one thousand"),
    ("1001", "one thousand one"),
    ("2026", "two thousand twenty six"),
    ("100000", "one hundred thousand"),
    ("1000000", "one million"),
    ("1234567", "one million two hundred thirty four thousand five hundred sixty seven"),
    ("1000000000000", "one zero zero zero zero zero zero zero zero zero zero zero zero"),
    ("007", "seven"),
    ("2.5", "two point five"),
    ("2.50", "two point five zero"),
    ("0.25", "zero point two five"),
    (".5", "zero point five"),
])
def test_number_to_words(digits, words):
    assert number_to_words(digits) == words


def test_no_and_in_numbers():
    # "and" could be confused with "plus"
    assert " and " not in number_to_words("115")


def test_say_rejects_bad_input():
    with pytest.raises(ParseError):
        say("3y = 6")
