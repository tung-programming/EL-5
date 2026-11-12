"""Command-line demo using the shared math modules.

Integration contract: parser.parse_equation(text) (or parser.parse(text)) returns
an OwnAST with to_sympy(); verifier.verify_step(previous, current) (or the named
aliases below) returns a result carrying status valid/invalid/unknown. This CLI
intentionally reports unavailable dependencies instead of implementing them.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _call_first(module: Any, names: tuple[str, ...], *args: Any) -> Any:
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args)
    raise RuntimeError(f"{module.__name__} does not yet expose {', '.join(names)}")


def check(previous_text: str, current_text: str) -> dict[str, Any]:
    """Run a check using other modules' public interfaces; never reimplement them."""
    from engine import parser, verifier, infer, mistakes
    old = _call_first(parser, ("parse_equation", "parse"), previous_text)
    new = _call_first(parser, ("parse_equation", "parse"), current_text)
    old_expr = old.to_sympy() if callable(getattr(old, "to_sympy", None)) else old
    new_expr = new.to_sympy() if callable(getattr(new, "to_sympy", None)) else new
    verified = _call_first(verifier, ("verify_step", "verify_equations", "verify"), old_expr, new_expr)
    status = verified.get("status") if isinstance(verified, dict) else getattr(verified, "status", None)
    if status is None and isinstance(verified, dict) and isinstance(verified.get("valid"), bool):
        status = "valid" if verified["valid"] else "invalid"
    if status not in ("valid", "invalid", "unknown"):
        raise RuntimeError("verifier result must provide status valid, invalid, or unknown")
    inferred = infer.infer_operation(old_expr, new_expr)
    mistake = mistakes.detect_mistake(old_expr, new_expr, inferred, status) if status == "invalid" else None
    response = {"status": status, "inference": inferred, "mistake": mistake,
                "explanation": {"concise": "", "detailed": ""}}
    try:
        from engine import explain
        explain_fn = next((getattr(explain, n, None) for n in ("explain_step", "explain")
                           if callable(getattr(explain, n, None))), None)
        if explain_fn:
            text = explain_fn(verified, inferred, mistake)
            if isinstance(text, dict):
                response["explanation"] = {k: text.get(k, "") for k in ("concise", "detailed")}
    except ImportError:
        pass
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check one algebra step.")
    parser.add_argument("previous", nargs="?", help="previous equation")
    parser.add_argument("current", nargs="?", help="current equation")
    args = parser.parse_args(argv)
    if (args.previous is None) != (args.current is None):
        parser.error("provide both previous and current equations")
    if args.previous is None:
        try:
            args.previous = input("Previous equation: ")
            args.current = input("Current equation: ")
        except (EOFError, KeyboardInterrupt):
            print("Input cancelled.", file=sys.stderr)
            return 2
    try:
        result = check(args.previous, args.current)
    except (ValueError, TypeError, SyntaxError) as exc:
        print(f"Invalid or unsupported equation: {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"Step checker dependency unavailable: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Step checker dependency unavailable: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["explanation"]["concise"]:
        print(result["explanation"]["concise"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
