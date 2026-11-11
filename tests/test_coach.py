from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from sql_error_coach.catalog import RULES
from sql_error_coach.cli import app
from sql_error_coach.coach import explain
from sql_error_coach.server import create_app

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def test_catalog_has_the_ten_errors():
    codes = [rule.code for rule in RULES]
    assert len(codes) == 10
    assert len(set(codes)) == 10


def test_every_example_matches_its_rule_and_dialect():
    for rule in RULES:
        assert rule.examples
        for example in rule.examples:
            result = explain(example.error, example.sql)
            assert result["matched"] is True
            assert result["code"] == rule.code
            assert result["dialect"] == example.dialect
            assert result["corrected_query"]
            assert result["plain"]
            assert result["steps"]


def test_mechanical_rewrites():
    form = explain(
        'ERROR:  syntax error at or near "FORM"\nLINE 1: SELECT * FORM orders;',
        "SELECT * FORM orders;",
    )
    assert form["correction_source"] == "yours"
    assert form["corrected_query"] == "SELECT * FROM orders;"

    comma = explain(
        "ERROR:  syntax error at or near \"FROM\"",
        "SELECT id, FROM orders;",
    )
    assert comma["corrected_query"] == "SELECT id FROM orders;"

    hinted = explain(
        'ERROR:  column "revenues" does not exist\n'
        'HINT:  Perhaps you meant to reference the column "orders.revenue".',
        "SELECT revenues FROM orders;",
    )
    assert hinted["plain"].startswith("There is no column named revenues")
    assert hinted["corrected_query"] == "SELECT orders.revenue FROM orders;"

    grouped = explain(
        'ERROR:  column "orders.customer_id" must appear in the GROUP BY clause or be used in an aggregate function',
        "SELECT customer_id, SUM(total) FROM orders;",
    )
    assert "GROUP BY customer_id" in grouped["corrected_query"]

    several = explain(
        "ERROR:  more than one row returned by a subquery used as an expression",
        "SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE country = 'IN');",
    )
    assert " IN (SELECT id FROM customers" in several["corrected_query"]

    quoted_number = explain(
        'ERROR:  invalid input syntax for type integer: "12"',
        "SELECT * FROM orders WHERE id = '12';",
    )
    assert quoted_number["corrected_query"] == "SELECT * FROM orders WHERE id = 12;"

    junk = explain(
        'ERROR:  invalid input syntax for type integer: "12a"',
        "SELECT * FROM orders WHERE id = '12a';",
    )
    assert junk["correction_source"] == "example"
    assert "12a" not in junk["corrected_query"]


def test_unknown_error_is_honest():
    result = explain("ERROR:  deadlock detected\nDETAIL:  Process 42 waits for ShareLock.")
    assert result["matched"] is False
    assert result["dialect"] == "postgres"
    assert result["corrected_query"] == ""


def test_cli_file_json_and_list(tmp_path: Path):
    error = tmp_path / "error.txt"
    query = tmp_path / "query.sql"
    report = tmp_path / "report.md"
    error.write_text(
        'ERROR:  column "revenues" does not exist\n'
        'HINT:  Perhaps you meant to reference the column "orders.revenue".\n',
        encoding="utf-8",
    )
    query.write_text("SELECT revenues FROM orders;\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["explain", "--file", str(error), "--sql", str(query), "--format", "json", "--output", str(report)],
    )
    assert result.exit_code == 0, result.output
    assert '"missing_column"' in result.output
    assert "orders.revenue" in report.read_text(encoding="utf-8")

    empty = runner.invoke(app, ["explain", ""])
    assert empty.exit_code == 1

    listed = runner.invoke(app, ["list"])
    assert listed.exit_code == 0
    assert "plain English" not in listed.output
    assert "That table is not in this database" in listed.output


def test_web_explain_and_health():
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200
    assert "SQL Error Coach" in page.text
    assert "That table is not in this database" in page.text

    response = client.post(
        "/api/explain",
        json={
            "error": "ERROR 1146 (42S02): Table 'shop.orders' doesn't exist",
            "sql": "SELECT * FROM orders;",
        },
    )
    assert response.status_code == 200
    body = response.json()["report"]
    assert body["code"] == "missing_relation"
    assert body["dialect"] == "mysql"
    assert "shop.orders" in body["plain"]

    empty = client.post("/api/explain", json={"error": "   "})
    assert empty.status_code == 400

    bad_dialect = client.post(
        "/api/explain",
        json={"error": "ERROR:  deadlock detected", "dialect": "oracle"},
    )
    assert bad_dialect.status_code == 400

    assert ROOT.joinpath("render.yaml").exists()
