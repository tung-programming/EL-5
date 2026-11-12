# Audio-First Algebra Step Checker

The full plan and PRD are in [plan.md](plan.md).

## Layout and owners
| Path | What | Owner |
|---|---|---|
| `engine/parser.py`, `engine/speak.py` | Parser, math → words | Member 1 |
| `engine/infer.py`, `engine/mistakes.py` (operation checks), `cli.py` | Inference, operation mistakes, CLI | Member 2 |
| `engine/verifier.py`, `engine/mistakes.py` (solution checks), `engine/explain.py`, `tests/cases.csv` | Verification, explanations, test catalogue | Member 3 |
| `engine/explore.py`, `docs/keyboard_guide.md` | Expression explorer, accessibility | Member 4 |
| `app.py`, `static/`, `docs/api.md` | API, page, speech, integration | Member 5 |
| `tests/` | One test file per module, owned by that module's member | — |
| `docs/` | Each member's docs (see the owner line in each file) | — |
| `report/` | Final report + slides, each member writes their own part | everyone |

## Rules
- Shared data formats live in `docs/contracts.md`. Don't change them without telling the team.
- Everyone adds rows to `tests/cases.csv`.
- One other member reviews every pull request.
- Each member adds their own dependencies and setup steps here as they need them.
