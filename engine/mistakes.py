"""Phase 1 operation mistakes. Call only after the verifier returns invalid."""
from __future__ import annotations

from typing import Any
import sympy as sp

from .infer import _sides, _same, _constant, infer_operation


def _fmt(value: sp.Expr) -> str:
    return str(sp.simplify(value))


def _try_difference(a: sp.Expr, b: sp.Expr) -> sp.Expr | None:
    d = sp.simplify(a - b)
    return d if _constant(d) and d != 0 else None


def _try_ratio(a: sp.Expr, b: sp.Expr) -> sp.Expr | None:
    if sp.simplify(b) == 0:
        return None
    r = sp.cancel(a / b)
    return r if _constant(r) and r not in (0, 1) else None


def detect_mistake(previous_equation: Any, current_equation: Any,
                    inference: dict[str, Any] | None = None,
                    verifier_result: Any = None) -> dict[str, str] | None:
    """Detect only one_side_only/arithmetic_error, and only for invalid steps.

    `verifier_result` must explicitly identify an invalid step. It may be the
    status string or a verifier result object/dict with a `status` or `valid`
    field. Omitted, valid, or unknown results never trigger mistake detection.
    """
    status = verifier_result
    if isinstance(status, dict):
        status = status.get("status", "invalid" if status.get("valid") is False else None)
    elif isinstance(status, str) or status is None:
        pass
    else:
        status = getattr(status, "status", None)
        if status is None and getattr(verifier_result, "valid", None) is False:
            status = "invalid"
    if status != "invalid":
        return None
    try:
        old, new = _sides(previous_equation), _sides(current_equation)
        inferred = inference if inference is not None else infer_operation(previous_equation, current_equation)

        # Evidence from exactly one side: reproduce that same operation on the
        # untouched other side, then require the current line to match exactly.
        for changed, other, loc in ((0, 1, "right_side"), (1, 0, "left_side")):
            # A pair of numeric constants always has some difference/ratio;
            # that alone is not evidence of the student's intended operation.
            if not (old[changed].free_symbols or new[changed].free_symbols):
                continue
            d = _try_difference(old[changed], new[changed])
            if d is not None and _same(old[other], new[other]):
                expected = sp.simplify(old[other] - d)
                if not _same(expected, new[other]):
                    return {"label": "one_side_only", "expected": _fmt(expected),
                            "got": _fmt(new[other]), "location": loc}
            k = _try_ratio(old[changed], new[changed]) if old[changed].free_symbols or new[changed].free_symbols else None
            if k is not None and _same(old[other], new[other]):
                expected = sp.simplify(old[other] / k)
                if not _same(expected, new[other]):
                    return {"label": "one_side_only", "expected": _fmt(expected),
                            "got": _fmt(new[other]), "location": loc}

        # The changed side identifies a supported operation; reapply it to the
        # other side and report only when the student's entered value differs.
        for changed, other, loc in ((0, 1, "right_side"), (1, 0, "left_side")):
            if not (old[changed].free_symbols or new[changed].free_symbols):
                continue
            d = _try_difference(old[changed], new[changed])
            if d is not None:
                expected = sp.simplify(old[other] - d)
                if not _same(expected, new[other]):
                    return {"label": "arithmetic_error", "expected": _fmt(expected),
                            "got": _fmt(new[other]), "location": loc}
            k = _try_ratio(old[changed], new[changed])
            if k is not None:
                expected = sp.simplify(old[other] / k)
                if not _same(expected, new[other]):
                    return {"label": "arithmetic_error", "expected": _fmt(expected),
                            "got": _fmt(new[other]), "location": loc}
        # Inference is accepted for interface compatibility, but never by itself
        # proves either supported label.
        _ = inferred
    except Exception:
        return None
    return None
