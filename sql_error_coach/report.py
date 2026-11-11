"""Terminal, Markdown, and JSON reports."""

from __future__ import annotations

import json

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel


def to_json(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2) + "\n"


def to_markdown(result: dict[str, object]) -> str:
    lines = [
        "# SQL Error Coach",
        "",
        f"**{result['dialect_label']} · {result['title']}**",
        "",
        str(result["plain"]),
        "",
        "## Why",
        "",
        str(result["why"]),
        "",
        "## Do this",
        "",
    ]
    steps = result["steps"]
    assert isinstance(steps, list)
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. {step}")
    corrected = str(result.get("corrected_query") or "")
    if corrected:
        lines.extend(
            [
                "",
                f"## {result['correction_label']}",
                "",
                str(result["correction_note"]),
                "",
                "```sql",
                corrected,
                "```",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_console(result: dict[str, object]) -> None:
    console = Console()
    title = f"{result['dialect_label']}  ·  {result['title']}"
    border = "green" if result["matched"] else "yellow"
    console.print(Panel(escape(str(result["plain"])), title=escape(title), border_style=border))
    console.print(escape(str(result["why"])))
    console.print()
    steps = result["steps"]
    assert isinstance(steps, list)
    for index, step in enumerate(steps, start=1):
        console.print(f"[bold]{index}.[/bold] {escape(str(step))}")
    corrected = str(result.get("corrected_query") or "")
    if corrected:
        console.print()
        console.print(
            Panel(
                escape(corrected),
                title=escape(str(result["correction_label"])),
                subtitle=escape(str(result["correction_note"])),
                border_style="green",
            )
        )
