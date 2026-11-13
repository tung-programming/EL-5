"""FastAPI application for the algebra step checker.

Owner: Member 5
See plan.md §7.7
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from engine.explain import explain_step
from engine.explore import build_explorer_tree
from engine.infer import infer_operation
from engine.mistakes import detect_mistake
from engine.parser import ParseError, parse
from engine.speak import to_words
from engine.verifier import verify_step


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


app = FastAPI(
	title="Audio-First Algebra Step Checker",
	description="Exact verification, inference, mistake detection, and explorer API for algebra steps.",
	version="1.0.0",
)


app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _add_group_quick_text(explorer_node: dict[str, Any], ast_node: Any) -> None:
	if ast_node.type == "Group":
		explorer_node["spoken_quick"] = f"Group containing {to_words(ast_node.children[0])}"
	for explorer_child, ast_child in zip(explorer_node["children"], ast_node.children):
		_add_group_quick_text(explorer_child, ast_child)


def _extract_text(payload: Any, *names: str) -> str:
	if not isinstance(payload, dict):
		raise ValueError("Request body must be a JSON object.")

	for name in names:
		value = payload.get(name)
		if value is not None:
			if isinstance(value, str):
				return value
			if isinstance(value, (list, tuple)) and len(value) == 2:
				return str(value[0]) + " = " + str(value[1])
	raise ValueError(f"Expected one of: {', '.join(names)}")


def _parse_equation_text(text: str, label: str) -> Any:
	if text is None or not isinstance(text, str):
		raise ValueError(f"The {label} equation must be a string.")

	expression = text.strip()
	if not expression:
		raise ValueError(f"The {label} equation cannot be blank.")

	try:
		return parse(expression)
	except ParseError as exc:  # pragma: no cover - the parser owns detailed parse errors.
		raise ValueError(f"The {label} equation is not valid algebra: {exc}") from exc


@app.get("/api/health")
def health() -> dict[str, str]:
	return {"status": "ok", "service": "algebra-step-checker", "version": app.version}


@app.get("/api/rules")
def rules() -> dict[str, Any]:
	return {
		"operations": ["add", "subtract", "multiply", "divide", "swap_sides", "rewrite", "unknown"],
		"mistake_labels": ["one_side_only", "arithmetic_error"],
		"status_values": ["valid", "invalid", "unknown"],
		"notes": "The verifier decides validity. Inference suggests the operation. Mistakes are only reported for invalid steps.",
	}


@app.post("/api/check-step")
async def check_step(request: Request) -> dict[str, Any]:
	payload = await request.json()

	try:
		previous_text = _extract_text(payload, "previous_equation", "previous", "previous_step")
		current_text = _extract_text(payload, "current_equation", "current", "current_step")
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc

	try:
		previous_ast = _parse_equation_text(previous_text, "previous")
		current_ast = _parse_equation_text(current_text, "current")
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc

	previous_expression = previous_ast.to_sympy()
	current_expression = current_ast.to_sympy()

	verification = verify_step(previous_expression, current_expression)
	inference = infer_operation(previous_expression, current_expression)
	mistake = detect_mistake(previous_expression, current_expression, inference, verification) if verification.status == "invalid" else None
	explanation = explain_step(verification, inference, mistake)

	result = {
		"status": verification.status,
		"inference": inference,
		"mistake": mistake,
		"explanation": explanation,
	}

	if verification.status == "valid" and inference is None:
		result["inference"] = {
			"operation": "unknown",
			"operand": None,
			"applied_to": "unknown",
			"expected": None,
			"got": None,
			"warnings": ["The verifier accepted the step, but no supported operation could be inferred."],
		}

	if inference is None and result["status"] != "valid":
		result["inference"] = None

	return result


@app.get("/api/parse-expression")
@app.post("/api/parse-expression")
async def parse_expression(request: Request) -> dict[str, Any]:
	try:
		if request.method == "GET":
			payload = dict(request.query_params)
		else:
			payload = await request.json()
	except Exception:
		payload = {}

	if not isinstance(payload, dict):
		payload = {}

	expression = (
		payload.get("expression")
		or payload.get("equation")
		or payload.get("text")
		or payload.get("expression_text")
	)

	if expression is None:
		raise HTTPException(status_code=400, detail="Request body must include an expression or equation string.")

	try:
		ast = _parse_equation_text(str(expression), "expression")
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc

	tree = build_explorer_tree(ast.to_dict())
	_add_group_quick_text(tree, ast)
	return tree


@app.get("/")
async def index() -> FileResponse:
	return FileResponse(STATIC_DIR / "index.html")


@app.get("/index.html")
async def index_html() -> FileResponse:
	return FileResponse(STATIC_DIR / "index.html")
