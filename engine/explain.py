"""Deterministic Phase 1 explanations for verified step outcomes."""

import re
from fractions import Fraction


_VALID_FALLBACK = "Correct. Both equations have the same real solution set."
_INVALID_FALLBACK = (
    "This step is incorrect because the two equations have different real "
    "solution sets."
)
_UNKNOWN_FALLBACK = "I cannot determine whether this step is correct."
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:/\d+)?|\d+\.\d+)$")

_OPERATIONS = {
    "add": lambda value: f"Correct. You added {value} to both sides.",
    "addition": lambda value: f"Correct. You added {value} to both sides.",
    "subtract": lambda value: f"Correct. You subtracted {value} from both sides.",
    "subtraction": lambda value: f"Correct. You subtracted {value} from both sides.",
    "multiply": lambda value: f"Correct. You multiplied both sides by {value}.",
    "multiplication": lambda value: f"Correct. You multiplied both sides by {value}.",
    "divide": lambda value: f"Correct. You divided both sides by {value}.",
    "division": lambda value: f"Correct. You divided both sides by {value}.",
}

_BOTH_SIDES = {"both sides", "both_sides", "left and right sides", "both"}


def build_explanation(status, verification=None, inference=None, mistake=None):
    """Build the shared ``{concise, detailed}`` explanation response.

    ``status`` may be a status string, a result object, or a dict. Inference is
    used only for valid steps when it explicitly describes a supported
    operation on both sides. The ``mistake`` parameter is reserved for
    integration compatibility and is intentionally not rendered in Phase 1.
    """
    if not isinstance(status, str):
        if verification is None and _field(status, "status") is not None:
            verification = status
        status = _field(status, "status")

    normalized_status = str(status).strip().lower() if status is not None else ""
    if normalized_status == "valid":
        text = _valid_explanation(verification, inference)
    elif normalized_status == "invalid":
        text = _invalid_explanation(verification)
    else:
        text = _UNKNOWN_FALLBACK

    return {"concise": text, "detailed": text}


def _valid_explanation(verification, inference):
    if inference is None:
        return _VALID_FALLBACK

    verified_status = _field(verification, "status")
    if verified_status is not None and str(verified_status).lower() != "valid":
        return _VALID_FALLBACK

    operation = _field(inference, "operation")
    operand = _field(inference, "operand")
    applied_to = _field(inference, "applied_to")
    if operation is None or operand is None or applied_to is None:
        return _VALID_FALLBACK

    operation_name = str(getattr(operation, "value", operation)).strip().lower()
    operation_name = operation_name.replace(" ", "_").replace("-", "_")
    template = _OPERATIONS.get(operation_name)
    operand_text = _safe_operand(operand)
    applied_to_text = str(getattr(applied_to, "value", applied_to)).strip().lower()
    if template is None or operand_text is None or applied_to_text not in _BOTH_SIDES:
        return _VALID_FALLBACK
    if operation_name in {"multiply", "multiplication", "divide", "division"}:
        if not _is_nonzero_number(operand_text):
            return _VALID_FALLBACK

    return template(operand_text)


def _invalid_explanation(verification):
    verified_status = _field(verification, "status")
    if verified_status is None or str(verified_status).lower() != "invalid":
        return _INVALID_FALLBACK

    previous = _format_solution_set(_field(verification, "previous_solutions"))
    current = _format_solution_set(_field(verification, "current_solutions"))
    if previous is None or current is None:
        return _INVALID_FALLBACK

    return (
        f"{_INVALID_FALLBACK} The previous equation {previous}; "
        f"the current equation {current}."
    )


def _field(value, name):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _safe_operand(value):
    text = str(value).strip()
    return text if _NUMBER.fullmatch(text) else None


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
