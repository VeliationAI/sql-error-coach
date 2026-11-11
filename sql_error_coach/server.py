"""FastAPI web UI for SQL Error Coach."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sql_error_coach import __version__
from sql_error_coach.catalog import DIALECT_LABELS, RULES

SHORT_LABELS = {
    "missing_relation": "Missing table",
    "missing_column": "Missing column",
    "ambiguous_column": "Ambiguous",
    "group_by": "GROUP BY",
    "not_null": "NOT NULL",
    "unique_violation": "Duplicate",
    "foreign_key": "Foreign key",
    "datatype_mismatch": "Wrong type",
    "subquery_cardinality": "Many rows",
    "syntax": "Syntax",
    "division_by_zero": "Divide by zero",
    "permission_denied": "Permission",
    "missing_database": "Missing database",
    "missing_function": "Missing function",
    "operator_mismatch": "Type mismatch",
    "insert_count": "INSERT count",
    "value_too_long": "Value too long",
    "aggregate_where": "WHERE aggregate",
    "undeclared_variable": "Variable",
    "transaction_aborted": "Aborted transaction",
    "deadlock": "Deadlock",
    "union_mismatch": "UNION width",
    "subquery_alias": "Subquery alias",
    "missing_from": "Missing FROM",
    "check_constraint": "CHECK",
    "dependent_objects": "Still in use",
}

FEATURED = (
    "syntax",
    "missing_relation",
    "missing_column",
    "ambiguous_column",
    "group_by",
    "not_null",
    "unique_violation",
    "foreign_key",
    "datatype_mismatch",
    "subquery_cardinality",
    "division_by_zero",
    "permission_denied",
    "missing_function",
    "deadlock",
)
from sql_error_coach.coach import explain

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="SQL Error Coach", version=__version__)
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        shown = [rule for rule in RULES if rule.code in FEATURED]
        samples = {
            rule.code: {
                "error": rule.examples[0].error,
                "sql": rule.examples[0].sql,
                "dialect": rule.examples[0].dialect,
            }
            for rule in shown
        }
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "version": __version__,
                "rule_count": len(RULES),
                "rules": [
                    {
                        "code": rule.code,
                        "title": rule.title,
                        "short": SHORT_LABELS.get(rule.code, rule.title),
                        "summary": rule.summary,
                        "dialect_label": DIALECT_LABELS[rule.examples[0].dialect],
                    }
                    for rule in shown
                ],
                "samples_json": json.dumps(samples).replace("<", "\\u003c"),
            },
        )

    @app.post("/api/explain")
    async def explain_error(request: Request) -> dict[str, object]:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Expected a JSON object.")
        try:
            result = explain(
                str(payload.get("error") or ""),
                str(payload.get("sql") or ""),
                str(payload.get("dialect") or "auto"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"report": result}

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    import os

    import uvicorn

    env_port = os.environ.get("PORT")
    if env_port:
        host = "0.0.0.0"
        port = int(env_port)
    uvicorn.run(create_app(), host=host, port=port)
