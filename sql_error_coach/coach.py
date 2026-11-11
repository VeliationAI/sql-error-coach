"""Match an error message and explain it without calling a database or a model."""

from __future__ import annotations

import re

from sql_error_coach.catalog import DIALECT_LABELS, DIALECT_TIPS, DIALECTS, RULES, Rule

MAX_CHARS = 20_000
_AGGREGATE = re.compile(r"\b(?:sum|count|avg|min|max)\s*\(", re.IGNORECASE)


def explain(error: str, sql: str = "", dialect: str = "auto") -> dict[str, object]:
    if dialect not in {"auto", *DIALECTS}:
        raise ValueError("Dialect must be auto, postgres, mysql, sqlite, or sqlserver.")
    message = (error or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    query = (sql or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not message:
        raise ValueError("Paste the error message.")
    if len(message) > MAX_CHARS or len(query) > MAX_CHARS:
        raise ValueError("That text is too long.")

    found = detect_dialect(message, dialect)
    rule = _match_rule(message)
    if rule is None:
        return _unknown(message, query, found)

    identifiers = _identifiers(rule.code, message)
    steps = list(rule.steps)
    tip = DIALECT_TIPS.get((rule.code, found))
    if tip:
        steps.append(tip)

    corrected, source = _correction(rule, query, identifiers)
    if source == "yours":
        label = "Your query, corrected"
        note = "This is your query with one mechanical change. Read it before you run it."
    else:
        label = "A corrected query"
        note = (
            "This is a typical correction, not an edit of your query."
            if query
            else "A typical correction with simple names. Use your own table and column names."
        )

    return {
        "matched": True,
        "code": rule.code,
        "title": rule.title,
        "plain": _plain(rule, identifiers),
        "why": rule.why,
        "steps": steps,
        "dialect": found,
        "dialect_label": DIALECT_LABELS[found],
        "identifiers": identifiers,
        "sql": query,
        "example_before": rule.before,
        "example_after": rule.after,
        "corrected_query": corrected,
        "correction_source": source,
        "correction_label": label,
        "correction_note": note,
    }


def detect_dialect(text: str, override: str = "auto") -> str:
    if override and override != "auto":
        return override
    low = " ".join(text.lower().split())
    if re.search(r"\berror\s+\d{3,4}\s*\(", low):
        return "mysql"
    if re.search(r"\bmsg\s+\d+\s*,", low):
        return "sqlserver"
    if re.search(
        r"no such table|no such column|constraint failed|sub-select returns|"
        r"datatype mismatch|cannot store\s+\w+\s+value|ambiguous column name\s*:|"
        r"near\s+[\"'].+[\"']\s*:\s*syntax error",
        low,
    ):
        return "sqlite"
    if re.search(
        r"you have an error in your sql syntax|unknown column|doesn['’]t exist|"
        r"duplicate entry|cannot be null|foreign key constraint fails|"
        r"subquery returns more than|incorrect\s+(?:integer|double|decimal|datetime)\s+value|"
        r"in field list is ambiguous|not in group by clause",
        low,
    ):
        return "mysql"
    if re.search(
        r"incorrect syntax near|invalid object name|invalid column name|"
        r"ambiguous column name|not contained in either an aggregate|"
        r"cannot insert the value null|violation of unique key|"
        r"conflicted with the foreign key|conversion failed when converting|"
        r"subquery returned more than 1 value",
        low,
    ):
        return "sqlserver"
    if "error:" in low or "sqlstate" in low or low.startswith("error"):
        return "postgres"
    return "unknown"


def _match_rule(text: str) -> Rule | None:
    for rule in RULES:
        for pattern in rule.patterns:
            if pattern.search(text):
                return rule
    return None


def _identifiers(code: str, text: str) -> dict[str, str]:
    found: dict[str, str] = {}

    def take(key: str, pattern: str) -> None:
        if key in found:
            return
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found[key] = match.group(1).strip()

    if code == "syntax":
        take("token", r"""(?:at or near|syntax near|near)\s+["'`]([^"'`\n]+)["'`]""")
        if "token" in found:
            found["token"] = found["token"].split()[0].strip(",.;")
    elif code == "missing_relation":
        take("table", r"""relation\s+["'`]([^"'`]+)["'`]""")
        take("table", r"""table\s+["'`]([^"'`]+)["'`]""")
        take("table", r"""no such table:\s*["'`]?([A-Za-z_][\w.]*)""")
        take("table", r"""invalid object name\s+["'`]([^"'`]+)["'`]""")
    elif code == "missing_column":
        take("hint", r"""meant to reference the column\s+["'`]([^"'`]+)["'`]""")
        take("column", r"""column\s+["'`]([^"'`]+)["'`]""")
        take("column", r"""unknown column\s+["'`]([^"'`]+)["'`]""")
        take("column", r"""no such column:\s*["'`]?([A-Za-z_][\w.]*)""")
        take("column", r"""invalid column name\s+["'`]([^"'`]+)["'`]""")
    elif code == "ambiguous_column":
        take("column", r"""column reference\s+["'`]([^"'`]+)["'`]""")
        take("column", r"""column\s+["'`]([^"'`]+)["'`]\s+in field list""")
        take("column", r"""ambiguous column name:?\s*["'`]([^"'`\n]+)["'`]""")
        take("column", r"""ambiguous column name:\s*([A-Za-z_][\w.]*)""")
    elif code == "group_by":
        take("column", r"""nonaggregated column\s+["'`]([^"'`]+)["'`]""")
        take("column", r"""column\s+["'`]([^"'`]+)["'`]""")
    elif code == "not_null":
        take("column", r"""null value in column\s+["'`]([^"'`]+)["'`]""")
        take("column", r"""column\s+["'`]([^"'`]+)["'`]\s+cannot be null""")
        take("column", r"""not null constraint failed:\s*([A-Za-z_][\w.]*)""")
        take("column", r"""null into column\s+["'`]([^"'`]+)["'`]""")
    elif code == "unique_violation":
        match = re.search(r"""key\s+\(([^)]+)\)=\(([^)]+)\)""", text, re.IGNORECASE)
        if match:
            found["column"] = match.group(1).strip()
            found["value"] = match.group(2).strip()
        take("value", r"""duplicate entry\s+'([^']+)'""")
        take("column", r"""for key\s+'([^']+)'""")
        take("column", r"""unique constraint failed:\s*([A-Za-z_][\w.]*)""")
        take("value", r"""duplicate key value is \(([^)]+)\)""")
    elif code == "foreign_key":
        match = re.search(
            r"""key\s+\(([^)]+)\)=\(([^)]+)\)\s+is not present in table\s+["'`]([^"'`]+)["'`]""",
            text,
            re.IGNORECASE,
        )
        if match:
            found["column"] = match.group(1).strip()
            found["value"] = match.group(2).strip()
            found["parent"] = match.group(3).strip()
        take("parent", r"""references\s+[`"\[]([^`"\]]+)[`"\]]""")
    elif code == "datatype_mismatch":
        take("type_name", r"""invalid input syntax for type\s+([a-z][a-z0-9 ]*?)(?:\s*:|\s*$)""")
        take("type_name", r"""incorrect\s+([a-z0-9 ]+?)\s+value""")
        take("type_name", r"""to data type\s+([a-z0-9]+)""")
        take("type_name", r"""cannot store\s+[A-Za-z]+\s+value in\s+([A-Za-z]+)\s+column""")
        take("literal", r"""invalid input syntax for type\s+[a-z0-9 ]+?:\s*["'`]([^"'`]+)["'`]""")
        take("literal", r"""value:\s*["'`]([^"'`]+)["'`]""")
        take("literal", r"""varchar value\s+["'`]([^"'`]+)["'`]""")
        take("literal", r"""["'`]([^"'`]+)["'`]\s+for column""")
    return found


def _plain(rule: Rule, identifiers: dict[str, str]) -> str:
    column = identifiers.get("column", "")
    short = column.split(".")[-1] if column else ""
    table = identifiers.get("table", "")
    token = identifiers.get("token", "")
    if rule.code == "syntax" and token:
        return (
            f"The database stopped reading at {token}. "
            "The mistake is that word, or the word just before it."
        )
    if rule.code == "missing_relation" and table:
        return (
            f"There is no table named {table} on this connection. "
            "It is usually a typo, the wrong database, or a missing schema."
        )
    if rule.code == "missing_column" and short:
        hint = identifiers.get("hint")
        if hint:
            return f"There is no column named {short}. The message suggests {hint} instead."
        return f"There is no column named {short} on the table in this query."
    if rule.code == "ambiguous_column" and short:
        return f"{short} is on more than one table in this query. Write the table name in front of it."
    if rule.code == "group_by" and short:
        return (
            f"You selected {short} and also used an aggregate such as SUM or COUNT. "
            "Add a GROUP BY so the database knows which rows to collapse."
        )
    if rule.code == "not_null" and short:
        return f"{short} is required, and this statement tried to save NULL there."
    if rule.code == "unique_violation":
        value = identifiers.get("value")
        if value and short:
            return f"{value} is already stored in {short}. A second row with the same value was rejected."
        if short:
            return f"{short} already has this value. A second row with the same value was rejected."
    if rule.code == "foreign_key":
        parent = identifiers.get("parent")
        value = identifiers.get("value")
        if parent and value and short:
            return f"{short} {value} is not in {parent}, so this row cannot be saved."
    if rule.code == "datatype_mismatch":
        literal = identifiers.get("literal")
        type_name = identifiers.get("type_name")
        if literal and type_name:
            return f"{literal} is not a valid {type_name.strip()} value."
    if rule.code == "subquery_cardinality":
        return "This subquery is used where one value is required, and it returned more than one row."
    return rule.summary


def _correction(rule: Rule, sql: str, identifiers: dict[str, str]) -> tuple[str, str]:
    rewritten = _rewrite(rule.code, sql, identifiers) if sql else None
    if rewritten and rewritten.strip() != sql.strip():
        return rewritten.strip(), "yours"
    return rule.after, "example"


def _rewrite(code: str, sql: str, identifiers: dict[str, str]) -> str | None:
    if code == "syntax":
        return _fix_syntax(sql, identifiers.get("token", ""))
    if code == "missing_column":
        return _fix_hint(sql, identifiers.get("column"), identifiers.get("hint"))
    if code == "group_by":
        return _fix_group_by(sql)
    if code == "subquery_cardinality":
        return _fix_subquery(sql)
    if code == "datatype_mismatch":
        return _fix_datatype(sql, identifiers.get("literal"))
    return None


def _fix_syntax(sql: str, token: str) -> str | None:
    updated = sql
    if token.upper() == "FORM":
        updated = re.sub(r"\bFORM\b", "FROM", updated, flags=re.IGNORECASE)
    updated = re.sub(r",(\s*)(?=from\b)", r"\1", updated, count=1, flags=re.IGNORECASE)
    updated = re.sub(r",(\s*)\)", r"\1)", updated, count=1)
    return updated if updated != sql else None


def _fix_hint(sql: str, column: str | None, hint: str | None) -> str | None:
    if not column or not hint:
        return None
    short = column.split(".")[-1]
    updated, count = re.subn(rf"\b{re.escape(short)}\b", hint, sql, count=1)
    return updated if count else None


def _fix_group_by(sql: str) -> str | None:
    if re.search(r"\bgroup\s+by\b", sql, re.IGNORECASE):
        return None
    match = re.match(
        r"^\s*select\s+(.+?)\s+from\s+(.+?)\s*;?\s*$",
        sql.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    parts = _split_csv(match.group(1))
    grouped = [part for part in parts if not _AGGREGATE.search(part)]
    aggregates = [part for part in parts if _AGGREGATE.search(part)]
    if not grouped or not aggregates:
        return None
    rest = match.group(2).strip().rstrip(";").strip()
    return f"SELECT {', '.join(parts)} FROM {rest}\nGROUP BY {', '.join(grouped)};"


def _fix_subquery(sql: str) -> str | None:
    updated, count = re.subn(
        r"=\s*\(\s*(select\b)",
        r"IN (\1",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    return updated if count else None


def _fix_datatype(sql: str, literal: str | None) -> str | None:
    if not literal or not re.fullmatch(r"\d+", literal):
        return None
    updated = sql.replace(f"'{literal}'", literal).replace(f'"{literal}"', literal)
    return updated if updated != sql else None


def _split_csv(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _unknown(message: str, query: str, dialect: str) -> dict[str, object]:
    return {
        "matched": False,
        "code": "unknown",
        "title": "Not one of the 10 errors yet",
        "plain": "v0.1 explains the 10 errors learners hit most often. This message did not match them.",
        "why": "The coach matches the wording of those errors on Postgres, MySQL, SQLite, and SQL Server. It does not guess past that list.",
        "steps": [
            "Read the first line again. The word in quotes is the object the database refused.",
            "Check the line number, then the comma, quote, or keyword just before the failure.",
            "If the same message shows up often in class, it is a candidate for the next version.",
        ],
        "dialect": dialect,
        "dialect_label": DIALECT_LABELS.get(dialect, "Unknown dialect"),
        "identifiers": {},
        "sql": query,
        "example_before": "",
        "example_after": "",
        "corrected_query": "",
        "correction_source": "none",
        "correction_label": "",
        "correction_note": "",
        "raw": message,
    }
