"""Mistake checks (plan.md §7.4). Call only after the verifier returns invalid.

Each check either PROVES its mistake, by rebuilding the student's exact line from
the previous one, or stays silent. The first match wins; no match gives None.

Order:
    structural  (need the parser's trees, which keep the student's brackets)
        partial_distribution   a(b + c) -> ab + c
        exponent_error         (a + b)^2 -> a^2 + b^2
        coefficient_error      2x + 3x -> 6x
    operation   (one side shows a clear step; check what happened to the other)
        divide_by_variable     both sides divided by something containing x
        one_side_only          the other side was left unchanged
        sign_error             the other side got the opposite operation (+5 for -5)
        wrong_inverse_op       left divided by k, right had k subtracted (and similar)
        arithmetic_error       right operation, wrong number
    solution set
        lost_solution / extra_solution

An operation only counts as "clear" when it is a step a student would take: a
subtraction or addition must remove the constant term from the x side, and a
multiplication or division must be by a whole number (or 1/whole number). This
stops rewrites such as 2x + 6 -> 2(x + 6) being read as "added 6 to the left".

MistakeResult (docs/contracts.md):
    {label, expected, got, location, operation, operand, before}
    operation/operand/before describe the step on the other side ("subtract", "5",
    "14") so the explanation can say "14 minus 5 is 9"; they are None when unknown.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterator

import sympy as sp

from .infer import X, _ast_of, _constant, _same, _sides, _signed_terms, infer_operation

SIDES = ("left_side", "right_side")


# ---- Small helpers --------------------------------------------------------

def _fmt(value: sp.Expr) -> str:
    """Serialize a value: polynomials expanded (2*x + 6), anything else simplified."""
    try:
        sp.Poly(value, X)
        return str(sp.expand(value))
    except (sp.PolynomialError, sp.GeneratorsNeeded, TypeError, ValueError):
        return str(sp.simplify(value))


def _fmt_set(solutions: sp.Set) -> str:
    return str(solutions)


def _mistake(label: str, expected: sp.Expr | str, got: sp.Expr | str, location: str,
             operation: str | None = None, operand: sp.Expr | None = None,
             before: sp.Expr | None = None) -> dict[str, Any]:
    text = lambda v: v if isinstance(v, str) or v is None else _fmt(v)
    return {"label": label, "expected": text(expected), "got": text(got), "location": location,
            "operation": operation, "operand": text(operand), "before": text(before)}


def _value(node: Any) -> sp.Expr:
    from .parser import to_sympy
    return to_sympy(node, evaluate=True)


def _constant_term(expr: sp.Expr) -> sp.Expr | None:
    try:
        return sp.Poly(expr, X).coeff_monomial(1)
    except (sp.PolynomialError, sp.GeneratorsNeeded, TypeError, ValueError):
        return None


def _is_zero(expr: sp.Expr) -> bool:
    try:
        return sp.simplify(expr) == 0
    except (TypeError, ValueError):
        return False


def _status_of(verifier_result: Any) -> str | None:
    status = verifier_result
    if isinstance(status, dict):
        return status.get("status", "invalid" if status.get("valid") is False else None)
    if isinstance(status, str) or status is None:
        return status
    status = getattr(verifier_result, "status", None)
    if status is None and getattr(verifier_result, "valid", None) is False:
        return "invalid"
    return status


# ---- One clear step on one side ------------------------------------------

Step = tuple[str, sp.Expr, Callable[[sp.Expr], sp.Expr]]


def _side_step(before: sp.Expr, after: sp.Expr) -> Step | None:
    """The plausible single step that turns `before` into `after` on a side with x,
    as (operation, operand, apply-it-to-a-value), or None."""
    if not (before.free_symbols or after.free_symbols):
        return None  # two plain numbers always differ by something; that proves nothing
    d = sp.simplify(before - after)
    if _constant(d) and d != 0 and _constant_term(after) == 0:
        return ("subtract", d, lambda v: v - d) if d > 0 else ("add", -d, lambda v: v - d)
    if _is_zero(after):
        return None
    k = sp.cancel(before / after)
    if _constant(k) and k.is_Rational and k not in (0, 1) and (k.q == 1 or abs(k.p) == 1):
        if k.q == 1:
            return "divide", k, lambda v: v / k
        return "multiply", 1 / k, lambda v: v / k
    return None


def _steps(old, new) -> Iterator[tuple[int, int, Step]]:
    """(changed side, other side, step) for each side that shows a clear step."""
    for changed, other in ((0, 1), (1, 0)):
        step = _side_step(old[changed], new[changed])
        if step is not None:
            yield changed, other, step


def _with_step(label: str, other: int, step: Step, old, expected, got) -> dict[str, Any]:
    operation, operand, _ = step
    return _mistake(label, expected, got, SIDES[other], operation, operand, old[other])


def _one_side_only(old, new):
    for _, other, step in _steps(old, new):
        if _same(old[other], new[other]):
            expected = step[2](old[other])
            if not _same(expected, new[other]):
                return _with_step("one_side_only", other, step, old, expected, new[other])
    return None


def _sign_error(old, new):
    """x + 5 = 9 -> x = 14: the left lost 5, the right gained 5."""
    for changed, other, step in _steps(old, new):
        if step[0] in ("add", "subtract"):
            d = old[changed] - new[changed]
            expected = step[2](old[other])
            if _same(new[other], old[other] + d) and not _same(expected, new[other]):
                return _with_step("sign_error", other, step, old, expected, new[other])
    return None


# The operation a student confuses each step with, and what it does to the other side.
_CONFUSED = {
    "divide": ("subtract", lambda v, n: v - n),
    "multiply": ("add", lambda v, n: v + n),
    "subtract": ("divide", lambda v, n: v / n),
    "add": ("multiply", lambda v, n: v * n),
}


def _wrong_inverse_op(old, new):
    """2x = 8 -> x = 6: the left was divided by 2, but 2 was subtracted on the right."""
    for _, other, step in _steps(old, new):
        operation, operand, apply = step
        _, confused = _CONFUSED[operation]
        expected = apply(old[other])
        if _same(new[other], confused(old[other], operand)) and not _same(expected, new[other]):
            return _with_step("wrong_inverse_op", other, step, old, expected, new[other])
    return None


def _arithmetic_error(old, new):
    for _, other, step in _steps(old, new):
        expected = step[2](old[other])
        if _same(expected, new[other]):
            continue
        # -3x = 12 -> x = 4 has the right number but the wrong sign. That is not
        # an arithmetic slip the checks can name, so stay silent (cases.csv M3_011).
        if not _is_zero(expected) and _same(new[other], -expected):
            continue
        return _with_step("arithmetic_error", other, step, old, expected, new[other])
    return None


# ---- Solution-set checks --------------------------------------------------

def _finite_solutions(sides) -> sp.Set | None:
    expr = sides[0] - sides[1]
    if expr.has(sp.nan, sp.zoo):
        return None
    solutions = sp.solveset(expr, X, sp.S.Reals)
    if isinstance(solutions, sp.FiniteSet) or solutions == sp.S.EmptySet:
        return solutions
    return None


def _strictly_inside(small: sp.Set, big: sp.Set) -> bool:
    return small != big and small.is_subset(big) is True


def _divide_by_variable(old, new):
    """x^2 = x -> x = 1: both sides divided by x, which loses x = 0."""
    if any(_is_zero(side) for side in new):
        return None
    k = sp.cancel(old[0] / new[0])
    if not k.free_symbols or not _same(k, sp.cancel(old[1] / new[1])):
        return None
    before, after = _finite_solutions(old), _finite_solutions(new)
    if before is None or after is None or not _strictly_inside(after, before):
        return None
    return _mistake("divide_by_variable", _fmt_set(before), _fmt_set(after), "unknown",
                    "divide", k, None)


def _solution_change(old, new):
    before, after = _finite_solutions(old), _finite_solutions(new)
    if before is None or after is None:
        return None
    if _strictly_inside(after, before):
        return _mistake("lost_solution", _fmt_set(before), _fmt_set(after), "unknown")
    if _strictly_inside(before, after):
        return _mistake("extra_solution", _fmt_set(before), _fmt_set(after), "unknown")
    return None


# ---- Structural checks (parser trees only) --------------------------------

def _variants(node: Any, rewrite: Callable[[Any], list]) -> Iterator[tuple[Any, Any, Any]]:
    """Every way to apply `rewrite` to exactly one part of `node`:
    (original part, rewritten part, the whole node with that part replaced)."""
    for alternative in rewrite(node):
        yield node, alternative, alternative
    for i, child in enumerate(node.children):
        for original, alternative, new_child in _variants(child, rewrite):
            children = list(node.children)
            children[i] = new_child
            yield original, alternative, replace(node, children=children)


def _has_x(node: Any) -> bool:
    from .parser import walk
    return any(n.type == "Variable" for n in walk(node))


def _bracketed_sum(node: Any) -> bool:
    return node.type == "Group" and node.children[0].type in ("Add", "Sub")


def _partial_distributions(node: Any) -> list:
    """a(b + c) -> ab + c and b + ac. Also -a(b + c), with -a as the multiplier."""
    from .parser import Node
    negate = node.type == "Neg" and node.children[0].type == "Mul"
    product = node.children[0] if negate else node
    if product.type != "Mul":
        return []
    a, group = product.children
    if _bracketed_sum(a) and not _has_x(group):
        a, group = group, a
    if not _bracketed_sum(group) or _has_x(a):
        return []
    if negate:
        a = Node("Neg", [a])
    inner = group.children[0]
    b, c = inner.children
    return [Node(inner.type, [Node("Mul", [a, b]), c]),
            Node(inner.type, [b, Node("Mul", [a, c])])]


def _term_by_term_powers(node: Any) -> list:
    """(a + b)^n -> a^n + b^n (and a^n - b^n or a^n + b^n for a difference)."""
    from .parser import Node
    if node.type != "Pow" or not _bracketed_sum(node.children[0]):
        return []
    exponent = node.children[1]
    inner = node.children[0].children[0]
    a, b = inner.children
    powers = [Node("Pow", [a, exponent]), Node("Pow", [b, exponent])]
    out = [Node(inner.type, powers)]
    if inner.type == "Sub":
        out.append(Node("Add", powers))
    return out


def _rebuilt_by(label: str, rewrite: Callable[[Any], list]):
    def check(old, new, old_ast, new_ast):
        for side, other in ((0, 1), (1, 0)):
            if not _same(old[other], new[other]):
                continue
            for original, wrong, whole in _variants(old_ast.children[side], rewrite):
                if _same(_value(whole), new[side]):
                    return _mistake(label, _value(original), _value(wrong), SIDES[side])
        return None
    return check


_partial_distribution = _rebuilt_by("partial_distribution", _partial_distributions)
_exponent_error = _rebuilt_by("exponent_error", _term_by_term_powers)


def _x_term_count(node: Any) -> int:
    count = 0
    for sign, term in _signed_terms(node):
        value = _value(term)
        try:
            poly = sp.Poly(value, X)
        except (sp.PolynomialError, sp.GeneratorsNeeded, TypeError, ValueError):
            continue
        if poly.degree() == 1 and poly.coeff_monomial(1) == 0:
            count += 1
    return count


def _coefficient_error(old, new, old_ast, new_ast):
    """2x + 3x = 20 -> 6x = 20: like terms combined with the wrong number in front."""
    for side, other in ((0, 1), (1, 0)):
        if not _same(old[other], new[other]):
            continue
        if _x_term_count(old_ast.children[side]) < 2 or _x_term_count(new_ast.children[side]) != 1:
            continue
        try:
            before, after = sp.Poly(old[side], X), sp.Poly(new[side], X)
        except (sp.PolynomialError, sp.GeneratorsNeeded):
            continue
        if before.degree() != 1 or after.degree() != 1:
            continue
        same_constant = before.coeff_monomial(1) == after.coeff_monomial(1)
        if same_constant and before.coeff_monomial(X) != after.coeff_monomial(X):
            return _mistake("coefficient_error", old[side], new[side], SIDES[side])
    return None


# ---- Entry point ----------------------------------------------------------

def detect_mistake(previous_equation: Any, current_equation: Any,
                   inference: dict[str, Any] | None = None,
                   verifier_result: Any = None) -> dict[str, Any] | None:
    """Name the mistake in an invalid step, or return None if none is proven.

    `verifier_result` must explicitly identify an invalid step: the status string,
    or a verifier result object/dict with `status` or `valid`. Omitted, valid or
    unknown results never trigger detection. Equations may be SymPy pairs or
    Equalities, or parser Equation nodes; only nodes enable the structural checks.
    """
    if _status_of(verifier_result) != "invalid":
        return None
    try:
        old, new = _sides(previous_equation), _sides(current_equation)
        old_ast, new_ast = _ast_of(previous_equation), _ast_of(current_equation)
        if old_ast is not None and new_ast is not None:
            for structural in (_partial_distribution, _exponent_error, _coefficient_error):
                found = structural(old, new, old_ast, new_ast)
                if found:
                    return found
        for check in (_divide_by_variable, _one_side_only, _sign_error, _wrong_inverse_op,
                      _arithmetic_error, _solution_change):
            found = check(old, new)
            if found:
                return found
    except Exception:
        return None
    # The inference is accepted for interface compatibility; it never proves a label.
    _ = inference if inference is not None else infer_operation
    return None
