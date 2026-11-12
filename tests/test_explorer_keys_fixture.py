"""Keeps tests/js/explorer_trees.json in step with engine/explore.py.

Owner: Member 4
The JavaScript keyboard tests (tests/js/explorer_keys.test.js) run against real
explorer trees. They are stored as JSON so Node does not need Python. This test
fails when engine/explore.py output changes, so the JSON cannot go stale.

Regenerate with:  python -m tests.test_explorer_keys_fixture
"""

import json
from pathlib import Path

from engine.explore import build_explorer_tree
from tests.explorer_fixtures import FIXTURES

JSON_PATH = Path(__file__).parent / "js" / "explorer_trees.json"
USED = [
    "3x+5=14",
    "2x+3=9",
    "2(x+3)=12",
    "x^2+3=7",
    "(x+1)/2=3",
]


def _generate():
    return {name: build_explorer_tree(FIXTURES[name][1]) for name in USED}


def test_js_fixture_trees_match_explorer_output():
    stored = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert stored == _generate(), (
        "tests/js/explorer_trees.json is stale. "
        "Run: python -m tests.test_explorer_keys_fixture"
    )


if __name__ == "__main__":
    JSON_PATH.write_text(
        json.dumps(_generate(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote", JSON_PATH)
