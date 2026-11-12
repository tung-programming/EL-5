"""Infer supported operations between two equations using exact SymPy algebra."""
from __future__ import annotations

from typing import Any

import sympy as sp


def _sides(equation: Any) -> tuple[sp.Expr, sp.Expr]:
    """Accept SymPy Equality, a two-item pair, or an AST-backed Equation."""
    if isinstance(equation, sp.Equality):
        return sp.sympify(equation.lhs), sp.sympify(equation.rhs)
    if isinstance(equation, (tuple, list)) and len(equation) == 2:
        return sp.sympify(equation[0]), sp.sympify(equation[1])
    converter = getattr(equation, "to_sympy", None)
    if callable(converter):
        return _sides(converter())
    if isinstance(equation, dict) and equation.get("type") == "Equation":
        children = equation.get("children", [])
        if len(children) == 2:
            return _sides(tuple(_ast_expr(c) for c in children))
    raise TypeError("expected a SymPy Equality or a pair of expressions")


def _ast_expr(node: dict[str, Any]) -> sp.Expr:
    """Convert the documented OwnAST shape to SymPy when no parser method exists."""
    typ, val = node.get("type"), node.get("value")
    children = [_ast_expr(c) for c in node.get("children", [])]
    if typ == "Number": return sp.Rational(val)
    if typ == "Variable": return sp.Symbol(str(val))
    if typ == "Group": return children[0]
    if typ == "Neg": return -children[0]
    if typ == "Add": return children[0] + children[1]
    if typ == "Sub": return children[0] - children[1]
    if typ == "Mul": return children[0] * children[1]
    if typ == "Div": return children[0] / children[1]
    if typ == "Pow": return children[0] ** children[1]
    raise ValueError(f"unsupported OwnAST node type: {typ}")


def _constant(expr: sp.Expr) -> bool:
    return not expr.free_symbols and expr.is_number and expr.is_real is True and expr.is_finite is True


def _same(a: sp.Expr, b: sp.Expr) -> bool:
    try:
        return sp.simplify(a - b) == 0
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def _result(operation: str, operand: sp.Expr | None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {"operation": operation, "operand": None if operand is None else str(operand),
            "applied_to": "both_sides", "expected": None, "got": None,
            "warnings": warnings or []}


def _difference_inference(old: tuple[sp.Expr, sp.Expr], new: tuple[sp.Expr, sp.Expr]):
    dl, dr = (sp.simplify(old[i] - new[i]) for i in (0, 1))
    if _same(dl, dr) and _constant(dl):
        if dl == 0: return None
        return _result("subtract" if dl > 0 else "add", abs(dl))
    return None


def _ratio_inference(old: tuple[sp.Expr, sp.Expr], new: tuple[sp.Expr, sp.Expr]):
    # Check before forming ratios: a zero side gives 0/0 or division by zero.
    try:
        if any(sp.simplify(v) == 0 for v in new):
            return None
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    ratios = []
    for before, after in zip(old, new):
        try:
            ratio = sp.cancel(before / after)
        except (ZeroDivisionError, TypeError, ValueError):
            return None
        ratios.append(ratio)
    k = ratios[0]
    if not _same(k, ratios[1]) or not _constant(k) or k == 0:
        return None
    if k == 1:
        return None
    # previous/current > 1 means division by k; a fraction means multiplication by 1/k.
    try:
        if k.is_positive is True:
            if k > 1:
                return _result("divide", k)
            return _result("multiply", sp.simplify(1 / k))
        if k.is_negative is True:
            return _result("divide", k, ["The common multiplier is negative; the equivalent operation is division by a negative constant."])
    except TypeError:
        pass
    return None


def infer_operation(previous_equation: Any, current_equation: Any) -> dict[str, Any] | None:
    """Return an InferenceResult-compatible dictionary, or None if unsupported.

    Supported in Phase 1: a common constant difference and a common nonzero
    constant ratio. Swapping sides is a small early Phase 2 check.
    """
    try:
        old, new = _sides(previous_equation), _sides(current_equation)
        difference = _difference_inference(old, new)
        if difference is not None:
            return difference
        ratio = _ratio_inference(old, new)
        if ratio is not None:
            return ratio
        if _same(new[0], old[1]) and _same(new[1], old[0]):
            return _result("swap_sides", None)
    except Exception:
        return None
    return None
