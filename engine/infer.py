"""Infer supported operations between two equations using exact SymPy algebra.

Checks, in order (plan.md §7.3):
    1. difference  L - L' == R - R'        add / subtract a number or an x-term
    2. ratio       L / L' == R / R'        multiply / divide by a nonzero number
    3. swap        L' == R and R' == L     swap_sides
    4. rewrite     L' == L and R' == R     rewrite (needs the parsed trees to see
                                           what changed; `kind` says how)
    5. generic     L'-R' == k (L-R)        combined: several steps at once

Every function accepts SymPy pairs/Equalities, or the parser's Equation nodes.
Only parser nodes keep the student's brackets, so rewrites need them.
"""
from __future__ import annotations

from typing import Any

import sympy as sp

X = sp.Symbol("x")


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


def _ast_of(equation: Any):
    """The parser's Equation node, or None for SymPy input."""
    children = getattr(equation, "children", None)
    if getattr(equation, "type", None) == "Equation" and isinstance(children, list) and len(children) == 2:
        return equation
    return None


def _polynomial(expr: sp.Expr) -> bool:
    """A polynomial in x with real coefficients (so never zero only at some x)."""
    if expr.has(sp.nan, sp.zoo, sp.oo, sp.Float):
        return False
    try:
        return all(c.is_real is True for c in sp.Poly(expr, X).all_coeffs())
    except (sp.PolynomialError, sp.GeneratorsNeeded, TypeError, ValueError):
        return False


def _difference_inference(old: tuple[sp.Expr, sp.Expr], new: tuple[sp.Expr, sp.Expr]):
    dl, dr = (sp.simplify(old[i] - new[i]) for i in (0, 1))
    if not _same(dl, dr) or dl == 0:
        return None
    if _constant(dl):
        return _result("subtract" if dl > 0 else "add", abs(dl))
    # An x-term moved across: 5x + 2 = 3x + 8 -> 2x = 6 subtracts 3x + 2 from both sides.
    if _polynomial(dl):
        dl = sp.expand(dl)
        if dl.could_extract_minus_sign():
            return _result("add", sp.expand(-dl))
        return _result("subtract", dl)
    return None


# ---- Rewrites (need the student's own trees) -------------------------------

def _signed_terms(node: Any, sign: int = 1) -> list[tuple[int, Any]]:
    """Top-level terms of one side, with their signs: 3x - (x + 2) -> +3x, -(x + 2).
    Brackets that only wrap a sum in the chain are see-through."""
    if node.type == "Add":
        return _signed_terms(node.children[0], sign) + _signed_terms(node.children[1], sign)
    if node.type == "Sub":
        return _signed_terms(node.children[0], sign) + _signed_terms(node.children[1], -sign)
    return [(sign, node)]


def _group_count(node: Any) -> int:
    from .parser import walk
    return sum(1 for n in walk(node) if n.type == "Group")


def _rewrite_kind(before: Any, after: Any) -> str:
    """How one side was rewritten: expand, factor, collect_like_terms, reorder or simplify."""
    from .parser import to_sympy
    groups_before, groups_after = _group_count(before), _group_count(after)
    if groups_after < groups_before:
        return "expand"
    if groups_after > groups_before:
        return "factor"
    terms_before, terms_after = _signed_terms(before), _signed_terms(after)
    if len(terms_after) < len(terms_before):
        return "collect_like_terms"
    if len(terms_after) == len(terms_before) >= 2:
        values = lambda terms: sorted(str(sp.expand(s * to_sympy(t, evaluate=True))) for s, t in terms)
        if values(terms_before) == values(terms_after):
            return "reorder"
    return "simplify"


def _rewrite_inference(previous_equation: Any, current_equation: Any):
    """Both sides keep their values: say which side was rewritten, and how."""
    from .parser import bracketed
    old_ast, new_ast = _ast_of(previous_equation), _ast_of(current_equation)
    if old_ast is None or new_ast is None:
        return None  # SymPy input has lost the student's form, so nothing to compare
    changed = tuple(i for i in (0, 1)
                    if bracketed(old_ast.children[i]) != bracketed(new_ast.children[i]))
    if not changed:
        return None
    kinds = {_rewrite_kind(old_ast.children[i], new_ast.children[i]) for i in changed}
    result = _result("rewrite", None)
    result["applied_to"] = {(0,): "left_side_only", (1,): "right_side_only"}.get(changed, "both_sides")
    result["kind"] = kinds.pop() if len(kinds) == 1 else "simplify"
    return result


def _generic_inference(old: tuple[sp.Expr, sp.Expr], new: tuple[sp.Expr, sp.Expr]):
    """(L' - R') == k (L - R) for a nonzero number k: the same steps were done to
    both sides, e.g. x + 2 = 5 -> 2x = 6 (multiply by 2, then subtract 4)."""
    before = sp.simplify(old[0] - old[1])
    after = sp.simplify(new[0] - new[1])
    if before == 0 or not before.free_symbols or before.has(sp.nan) or after.has(sp.nan):
        return None
    k = sp.cancel(after / before)
    if not _constant(k) or k == 0:
        return None
    # 2x = 0 -> x = 0: the ratio check skips zero sides, but each side is simply
    # multiplied by k, so name that operation.
    if _same(new[0], k * old[0]) and _same(new[1], k * old[1]):
        named = _ratio_result(sp.nsimplify(1 / k))
        if named is not None:
            return named
    return _result("combined", None)


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
    return _ratio_result(k)


def _ratio_result(k: sp.Expr):
    """The operation for previous/current == k on both sides."""
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

    The order is in the module docstring. A step that changes nothing is None.
    """
    try:
        old, new = _sides(previous_equation), _sides(current_equation)
        difference = _difference_inference(old, new)
        if difference is not None:
            return difference
        ratio = _ratio_inference(old, new)
        if ratio is not None:
            return ratio
        unchanged = _same(new[0], old[0]) and _same(new[1], old[1])
        # 0x = 0 -> 0 = 0 also "swaps" equal sides; that is a rewrite, not a swap.
        if not unchanged and _same(new[0], old[1]) and _same(new[1], old[0]):
            return _result("swap_sides", None)
        if unchanged:
            return _rewrite_inference(previous_equation, current_equation)
        return _generic_inference(old, new)
    except Exception:
        return None
