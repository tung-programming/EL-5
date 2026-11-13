"""Deterministic explanations for verified step outcomes (plan.md §7.5).

Every explanation has two levels:
    concise   what happened, with the numbers ("9 divided by 3 is 3, not 2")
    detailed  the concise text plus one teaching sentence, and the solutions
              or zero-divisor warnings when the verifier supplied them

Every number comes from the verified JSON (inference, mistake, verification);
nothing here does maths beyond reading those strings. When a field is missing
or not in the expected shape, the safe fallback sentence is used instead.
"""

import re
from fractions import Fraction


_VALID_FALLBACK = "Correct. Both equations have the same real solution set."
_INVALID_FALLBACK = (
    "This step is incorrect because the two equations have different real "
    "solution sets."
)
_UNKNOWN_FALLBACK = "I cannot determine whether this step is correct."
_INCORRECT = "This step is incorrect."
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:/\d+)?|\d+\.\d+)$")
# A number or a simple x-expression, as serialized by infer/mistakes ("3*x + 2").
_EXPRESSION = re.compile(r"^[0-9x+\-*/(). ]*[0-9x][0-9x+\-*/(). ]*$")

_OPERATION_NAMES = {
    "add": "add", "addition": "add",
    "subtract": "subtract", "subtraction": "subtract",
    "multiply": "multiply", "multiplication": "multiply",
    "divide": "divide", "division": "divide",
}

_BOTH_SIDES = {"both sides", "both_sides", "left and right sides", "both"}
_SIDE_NAMES = {"left_side": "left side", "right_side": "right side"}
_OTHER_SIDE = {"left_side": "right side", "right_side": "left side"}
_REWRITE_SIDES = {"left_side_only": "the left side", "right_side_only": "the right side",
                  "both_sides": "both sides"}
_REWRITES = {
    "expand": "You expanded the brackets on {side}.",
    "factor": "You factorised {side}.",
    "collect_like_terms": "You collected like terms on {side}.",
    "reorder": "You reordered the terms on {side}.",
    "simplify": "You simplified {side}.",
}

_BALANCED = ("Doing the same thing to both sides keeps the equation balanced, "
             "so the solution does not change.")


def build_explanation(status, verification=None, inference=None, mistake=None):
    """Build the shared ``{concise, detailed}`` explanation response.

    ``status`` may be a status string, a result object, or a dict. Inference is
    used only for valid steps it describes; a mistake is used only for invalid
    steps, and only when it carries its evidence (``expected`` and ``got``).
    """
    if not isinstance(status, str):
        if verification is None and _field(status, "status") is not None:
            verification = status
        status = _field(status, "status")

    normalized_status = str(status).strip().lower() if status is not None else ""
    if normalized_status == "valid":
        concise, detailed = _valid_explanation(verification, inference)
    elif normalized_status == "invalid":
        concise, detailed = _invalid_explanation(verification, mistake)
    else:
        concise = detailed = _UNKNOWN_FALLBACK

    if normalized_status in ("valid", "invalid"):
        detailed = _join(detailed, *_warnings(verification))
    return {"concise": concise, "detailed": detailed}


# ---- Valid ----------------------------------------------------------------

def _valid_explanation(verification, inference):
    fallback = (_VALID_FALLBACK, _VALID_FALLBACK)
    if inference is None:
        return fallback

    verified_status = _field(verification, "status")
    if verified_status is not None and str(verified_status).lower() != "valid":
        return fallback

    operation = _field(inference, "operation")
    applied_to = _field(inference, "applied_to")
    if operation is None or applied_to is None:
        return fallback
    operation_name = str(getattr(operation, "value", operation)).strip().lower()
    operation_name = operation_name.replace(" ", "_").replace("-", "_")
    applied_to_text = str(getattr(applied_to, "value", applied_to)).strip().lower()

    if operation_name == "swap_sides" and applied_to_text in _BOTH_SIDES:
        concise = "Correct. You swapped the two sides."
        return concise, _join(concise, "An equation says the same thing whichever way round it is written.")
    if operation_name == "rewrite":
        side = _REWRITE_SIDES.get(applied_to_text)
        kind = str(_field(inference, "kind") or "simplify")
        if side is None:
            return fallback
        concise = "Correct. " + _REWRITES.get(kind, _REWRITES["simplify"]).format(side=side)
        return concise, _join(concise, "Writing a side in a different but equal form does not change its value.")
    if operation_name == "combined" and applied_to_text in _BOTH_SIDES:
        concise = "Correct. You did the same steps to both sides."
        return concise, _join(concise, _BALANCED)

    operation_name = _OPERATION_NAMES.get(operation_name)
    operand_text = _safe_operand(_field(inference, "operand"))
    if operation_name is None or operand_text is None or applied_to_text not in _BOTH_SIDES:
        return fallback
    if operation_name in ("multiply", "divide") and not _is_nonzero_number(operand_text):
        return fallback

    concise = f"Correct. You {_did(operation_name, _math(operand_text), 'both sides')}."
    return concise, _join(concise, _BALANCED)


# ---- Invalid --------------------------------------------------------------

def _invalid_explanation(verification, mistake):
    solutions = _solutions_sentence(verification)
    named = _mistake_explanation(mistake)
    if named is not None:
        concise, tip = named
        # Lost/extra solution messages already list both solution sets.
        repeats = _field(mistake, "label") in ("lost_solution", "extra_solution")
        return concise, _join(concise, tip, solutions[1] if solutions and not repeats else None)
    if solutions is None:
        return _INVALID_FALLBACK, _INVALID_FALLBACK
    return solutions[0], solutions[0]


def _solutions_sentence(verification):
    """(fallback sentence, short sentence) about both solution sets, or None."""
    verified_status = _field(verification, "status")
    if verified_status is None or str(verified_status).lower() != "invalid":
        return None
    previous = _format_solution_set(_field(verification, "previous_solutions"))
    current = _format_solution_set(_field(verification, "current_solutions"))
    if previous is None or current is None:
        return None
    return (
        f"{_INVALID_FALLBACK} The previous equation {previous}; "
        f"the current equation {current}.",
        f"The previous equation {previous}; yours {current}.",
    )


def _mistake_explanation(mistake):
    """(concise, teaching tip) for a mistake with evidence, or None."""
    label = _field(mistake, "label")
    expected, got = _field(mistake, "expected"), _field(mistake, "got")
    if not isinstance(label, str) or not isinstance(expected, str) or not isinstance(got, str):
        return None
    builder = _MISTAKES.get(label)
    if builder is None:
        return None
    location = _field(mistake, "location")
    step = _Step(
        side=_SIDE_NAMES.get(location),
        other=_OTHER_SIDE.get(location),
        operation=_OPERATION_NAMES.get(str(_field(mistake, "operation") or "")),
        operand=_safe_operand(_field(mistake, "operand")),
        before=_safe_operand(_field(mistake, "before")),
        expected=expected,
        got=got,
    )
    return builder(step)


class _Step:
    def __init__(self, side, other, operation, operand, before, expected, got):
        self.side, self.other = side, other
        self.operation, self.operand, self.before = operation, operand, before
        self.expected, self.got = _math(expected), _math(got)

    @property
    def complete(self):
        """Enough evidence to say which operation and which numbers."""
        return None not in (self.side, self.other, self.operation, self.operand, self.before)

    def did(self, target):
        return _did(self.operation, _math(self.operand), target)

    def calculation(self):
        before = _math(self.before)
        if re.search(r".[+\-]", before):
            before = f"({before})"
        word = {"add": "plus", "subtract": "minus", "multiply": "times", "divide": "divided by"}
        return f"{before} {word[self.operation]} {_math(self.operand)}"

    def should_be(self, start="The"):
        """"The right side should be 14 minus 5, which is 9, not 10." """
        return (f"{start} {self.side} should be {self.calculation()}, which is "
                f"{self.expected}, not {self.got}.")

    def plain_should_be(self):
        side = f"The {self.side}" if self.side else "It"
        return f"{side} should be {self.expected}, not {self.got}."


def _one_side_only(s):
    tip = "Whatever you do to one side of an equation, you must do to the other side as well."
    if not s.complete:
        return f"{_INCORRECT} {s.plain_should_be()}", tip
    return f"{_INCORRECT} You {s.did('the ' + s.other)} but not the {s.side}. {s.should_be()}", tip


def _sign_error(s):
    if not s.complete:
        return (f"{_INCORRECT} Check the sign. {s.plain_should_be()}",
                "Both sides need the same operation, with the same sign.")
    opposite = {"subtract": "added", "add": "subtracted"}.get(s.operation)
    tip = "Both sides need the same operation, with the same sign."
    if opposite:
        tip = f"It looks like you {opposite} {_math(s.operand)} on the {s.side} instead. {tip}"
    return f"{_INCORRECT} Check the sign. You {s.did('the ' + s.other)}, so {s.should_be('the')}", tip


_CONFUSED = {"divide": ("subtract", "subtracted {n}"), "multiply": ("add", "added {n}"),
             "subtract": ("divide", "divided by {n}"), "add": ("multiply", "multiplied by {n}")}
_GERUND = {"add": "Adding", "subtract": "Subtracting", "multiply": "Multiplying", "divide": "Dividing"}


def _wrong_inverse_op(s):
    if not s.complete:
        return (f"{_INCORRECT} {s.plain_should_be()}",
                "Use the same operation on both sides of the equation.")
    confused, confused_text = _CONFUSED[s.operation]
    instead = confused_text.format(n=_math(s.operand))
    tip = (f"{_GERUND[s.operation]} and {_GERUND[confused].lower()} are different operations, "
           "even with the same number. Use the same one on both sides.")
    return (f"{_INCORRECT} You {s.did('the ' + s.other)}, but on the {s.side} you "
            f"{instead} instead. {s.should_be()}"), tip


def _arithmetic_error(s):
    if not s.complete:
        return (f"{_INCORRECT} Check your arithmetic. {s.plain_should_be()}",
                "Work out the numbers again carefully.")
    return (f"{_INCORRECT} You {s.did('both sides')}, which is the right idea, but "
            f"{s.calculation()} is {s.expected}, not {s.got}."), \
        f"Your method was right; only the calculation on the {s.side} needs fixing."


def _partial_distribution(s):
    return (f"{_INCORRECT} When you multiply out brackets, the number outside must "
            f"multiply every term inside. {s.plain_should_be()}",
            "For example, 2(x + 3) means 2 times x plus 2 times 3, which is 2x + 6.")


def _coefficient_error(s):
    return (f"{_INCORRECT} When you combine the x terms, add or subtract the numbers "
            f"in front of x. {s.plain_should_be()}",
            "For example, 2x + 3x is 5x, because 2 plus 3 is 5.")


def _exponent_error(s):
    return (f"{_INCORRECT} A power of a bracket is not the same as the power of each "
            f"term inside it. {s.plain_should_be()}",
            "For example, (x + 1) squared means (x + 1) times (x + 1), which is "
            "x squared + 2x + 1.")


def _divide_by_variable(s):
    lost = _set_difference(s.expected, s.got)
    divisor = _math(s.operand) if s.operand else "an expression containing x"
    loses = f"loses {lost}" if lost else "loses a solution"
    return (f"{_INCORRECT} You divided both sides by {divisor}, which could be zero, "
            f"so the step {loses}."), \
        ("Never divide both sides by something that could be zero. Instead, move "
         "everything to one side and factorise.")


def _lost_solution(s):
    return (f"{_INCORRECT} It loses a solution: the previous equation "
            f"{_solution_words(s.expected)}, but yours {_solution_words(s.got)}."), \
        ("Check for a step that throws a solution away, such as taking a square root "
         "and keeping only the positive answer.")


def _extra_solution(s):
    return (f"{_INCORRECT} It adds a solution: the previous equation "
            f"{_solution_words(s.expected)}, but yours {_solution_words(s.got)}."), \
        "Squaring both sides can add solutions that do not work in the original equation."


_MISTAKES = {
    "one_side_only": _one_side_only,
    "sign_error": _sign_error,
    "wrong_inverse_op": _wrong_inverse_op,
    "arithmetic_error": _arithmetic_error,
    "partial_distribution": _partial_distribution,
    "coefficient_error": _coefficient_error,
    "exponent_error": _exponent_error,
    "divide_by_variable": _divide_by_variable,
    "lost_solution": _lost_solution,
    "extra_solution": _extra_solution,
}


# ---- Formatting -----------------------------------------------------------

def _did(operation, operand, target):
    return {
        "add": f"added {operand} to {target}",
        "subtract": f"subtracted {operand} from {target}",
        "multiply": f"multiplied {target} by {operand}",
        "divide": f"divided {target} by {operand}",
    }[operation]


def _math(text):
    """SymPy text to readable, speakable maths: 2*x**2 -> 2x squared."""
    t = str(text).strip()
    t = re.sub(r"\*\*2(?!\d)", " squared", t)
    t = re.sub(r"\*\*3(?!\d)", " cubed", t)
    t = re.sub(r"\*\*\(?(-?\d+)\)?", r" to the power of \1", t)
    t = re.sub(r"sqrt\(([^()]*)\)", r"√\1", t)
    t = re.sub(r"(\d)\*(?=[x√(])", r"\1", t)
    return t.replace("*", " × ")


def _set_elements(text):
    """'{-2, 2}' -> ['-2', '2']; 'EmptySet' -> []; anything else -> None."""
    text = text.strip()
    if text in {"EmptySet", "EmptySet()", "{}"}:
        return []
    if not (text.startswith("{") and text.endswith("}")):
        return None
    elements = [e.strip() for e in text[1:-1].split(",") if e.strip()]
    return elements or None


def _solution_words(text):
    elements = _set_elements(text)
    if elements is None:
        return "has different solutions"
    if not elements:
        return "has no real solutions"
    words = " or ".join(f"x = {_math(e)}" for e in elements)
    return f"has solution {words}" if len(elements) == 1 else f"has solutions {words}"


def _set_difference(expected, got):
    """The solutions in `expected` that are missing from `got`, as words."""
    before, after = _set_elements(expected), _set_elements(got)
    if before is None or after is None:
        return None
    lost = [e for e in before if e not in after]
    return " and ".join(f"x = {_math(e)}" for e in lost) if lost else None


def _warnings(verification):
    warnings = _field(verification, "warnings")
    if not isinstance(warnings, (list, tuple)):
        return []
    return [f"Note: {w}" for w in warnings if isinstance(w, str) and w.strip()]


def _join(*parts):
    return " ".join(p for p in parts if p)


def _field(value, name):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _safe_operand(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if _NUMBER.fullmatch(text) or _EXPRESSION.fullmatch(text) else None


def _is_nonzero_number(text):
    try:
        return Fraction(text) != 0
    except (ValueError, ZeroDivisionError):
        return False


def _format_solution_set(value):
    """Format simple serialized SymPy sets without evaluating mathematics."""
    if not isinstance(value, str):
        return None

    text = value.strip()
    if text in {"Reals", "Interval(-oo, oo)"}:
        return "is true for every real x"
    if text in {"EmptySet", "EmptySet()"}:
        return "has no real solutions"
    if not (text.startswith("{") and text.endswith("}")):
        return None

    elements = [element.strip() for element in text[1:-1].split(",")]
    if not elements or any(not _NUMBER.fullmatch(element) for element in elements):
        return None
    solutions = " or ".join(f"x = {element}" for element in elements)
    return f"has solution {solutions}" if len(elements) == 1 else f"has solutions {solutions}"


def explain_step(verification, inference=None, mistake=None):
    """Adapt a VerificationResult or status dictionary to ``build_explanation``.

    Missing or unsupported verification data safely uses the unknown template.
    Explanation wording remains centralized in ``build_explanation``.
    """
    if isinstance(verification, str):
        status = verification
    else:
        status = _field(verification, "status")

    if not isinstance(status, str) or status.strip().lower() not in {
        "valid",
        "invalid",
        "unknown",
    }:
        return build_explanation("unknown")

    return build_explanation(status, verification, inference, mistake)
