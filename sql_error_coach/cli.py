"""Command line: explain an error, or open the web UI."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Literal, Optional

import typer

from sql_error_coach import __version__
from sql_error_coach.catalog import DIALECT_LABELS, RULES
from sql_error_coach.coach import explain
from sql_error_coach.report import render_console, to_json, to_markdown

app = typer.Typer(
    help="Explain a SQL error in plain English and show a corrected query.",
    no_args_is_help=True,
    add_completion=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """SQL Error Coach."""


@app.command("explain")
def explain_cmd(
    message: Annotated[Optional[str], typer.Argument(help="The SQL error text")] = None,
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", exists=True, dir_okay=False, readable=True, help="Read the error from a file"),
    ] = None,
    query: Annotated[
        Optional[str],
        typer.Option("--query", "-q", help="The SQL that failed"),
    ] = None,
    sql_file: Annotated[
        Optional[Path],
        typer.Option("--sql", exists=True, dir_okay=False, readable=True, help="Read the SQL from a file"),
    ] = None,
    dialect: Annotated[
        str,
        typer.Option("--dialect", "-d", help="auto, postgres, mysql, sqlite, or sqlserver"),
    ] = "auto",
    fmt: Annotated[
        Literal["text", "markdown", "json"],
        typer.Option("--format", help="text (terminal), markdown, or json"),
    ] = "text",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write the report to this file"),
    ] = None,
) -> None:
    """Explain one error and print the fix."""
    try:
        error_text = _read_error(message, file)
        sql_text = _read_sql(query, sql_file)
        result = explain(error_text, sql_text, dialect)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    payload = to_json(result) if fmt == "json" else to_markdown(result)
    if output:
        output.write_text(payload if fmt == "json" else to_markdown(result), encoding="utf-8")
    if fmt == "json":
        _emit(payload)
    elif fmt == "markdown":
        _emit(to_markdown(result))
    else:
        render_console(result)
        if output:
            typer.echo(f"Wrote {output}")


@app.command("list")
def list_cmd() -> None:
    """List the 10 errors this version explains."""
    for index, rule in enumerate(RULES, start=1):
        dialects = ", ".join(DIALECT_LABELS[example.dialect] for example in rule.examples)
        typer.echo(f"{index}. {rule.title}")
        typer.echo(f"   {rule.summary}")
        typer.echo(f"   {dialects}")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port")] = 8000,
) -> None:
    """Open the web UI. On Render, the start command binds 0.0.0.0:$PORT directly."""
    import uvicorn

    env_port = os.environ.get("PORT")
    if env_port:
        host = "0.0.0.0"
        port = int(env_port)
    uvicorn.run("sql_error_coach.server:create_app", factory=True, host=host, port=port)


def _read_error(message: str | None, file: Path | None) -> str:
    if file:
        return file.read_text(encoding="utf-8")
    if message:
        return message
    if sys.stdin.isatty():
        raise ValueError("Paste an error message, or pass --file.")
    return sys.stdin.read()


def _read_sql(query: str | None, sql_file: Path | None) -> str:
    if sql_file:
        return sql_file.read_text(encoding="utf-8")
    return query or ""


def _emit(text: str) -> None:
    try:
        typer.echo(text, nl=False)
    except UnicodeEncodeError:
        typer.echo(text.encode("ascii", "backslashreplace").decode("ascii"), nl=False)
