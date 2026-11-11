# SQL Error Coach

Paste a SQL error. Get a plain-English explanation, the change to make, and a corrected query.

Stored fixes cover the errors learners hit most often on Postgres, MySQL, SQLite, and SQL Server: the original ten, plus division by zero, permission denied, a missing database or function, a type mismatch, an INSERT with the wrong number of values, a value that does not fit, an aggregate in WHERE, an undeclared variable, an aborted transaction, a deadlock, a UNION with unequal sides, a subquery with no alias, a missing FROM entry, a CHECK failure, and a drop blocked by another object.

Any other message is still read. The coach names the database, the vendor code, the line number, and the quoted object. It does not invent a rewritten query for wording it has not stored. Matching is deterministic. No LLM, no database connection, and the query is never executed.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

On macOS or Linux, activate with `source .venv/bin/activate`.

## Explain an error

```bash
sql-error-coach explain "ERROR 1146 (42S02): Table 'shop.orders' doesn't exist"
sql-error-coach explain --file error.txt --sql query.sql
sql-error-coach explain --format markdown --output report.md --file error.txt
sql-error-coach list
sql-error-coach serve
```

`serve` opens the web page at http://127.0.0.1:8000. Paste the error, optionally paste the query, and read the fix. Auto-detect covers the four dialects.

## Stored fixes learners hit first

| Error | What it usually means |
| --- | --- |
| Table does not exist | Typo, wrong database, or missing schema |
| Column does not exist | Typo, or the column is on another table |
| Ambiguous column | A JOIN has the same column name on both sides |
| GROUP BY | A plain column is mixed with SUM or COUNT |
| NOT NULL | A required column was left empty |
| Unique / primary key | That value is already stored |
| Foreign key | The parent row is missing, or children still exist |
| Wrong type | A number column received text, often because of quotes |
| Subquery returned many rows | `=` was used where `IN` or one row was needed |
| Syntax error | The token in quotes is where the database stopped |

When the query is pasted, a few of these are edited directly: `FORM` to `FROM`, a trailing comma, a Postgres column hint, a missing `GROUP BY`, `=` to `IN` for a multi-row subquery, and quotes removed from a whole number. Everything else is shown as a typical correction so a wrong guess is not presented as your query.

## Web service

Live app: https://sql-error-coach.onrender.com

The Render service uses the free Python plan in Oregon. It sleeps after 15 minutes without a request, then wakes on the next visit.

```bash
pip install -r requirements.txt && pip install -e .
uvicorn sql_error_coach.server:create_app --factory --host 0.0.0.0 --port $PORT
```

Health check: `/health`.

## License

MIT © Veliation AI
