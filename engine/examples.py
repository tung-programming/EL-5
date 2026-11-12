"""Writes docs/example_trees.json: real parser output for teammates to build against.

Owner: Member 1
Run from the project root:  python -m engine.examples
tests/test_parser.py fails if the file is out of date, so rerun this after changing the parser.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.parser import bracketed, parse, to_sympy
from engine.speak import to_words

EXAMPLES = ["3x + 5 = 14", "3x = 9", "2(x + 3) = 10", "x/2 = 3", "-3x + 5 = -4", "x^2 - 4 = 0", "2.5x = 5"]
OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "example_trees.json"


def build() -> dict:
    examples = []
    for text in EXAMPLES:
        tree = parse(text)
        left, right = to_sympy(tree, evaluate=True)
        examples.append({
            "input": text,
            "bracketed": bracketed(tree),
            "spoken": to_words(tree),
            "sympy": f"{left} = {right}",
            "tree": tree.to_dict(),
        })
    return {
        "_about": "Example OwnAST trees produced by engine/parser.py (Member 1), for Members 3 and 4 "
                  "to build against. Regenerate with: python -m engine.examples. Format: docs/contracts.md.",
        "examples": examples,
    }


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT}")
