"""The ten SQL errors v0.1 knows, matched from the message text."""

from __future__ import annotations

import re
from dataclasses import dataclass

DIALECTS = ("postgres", "mysql", "sqlite", "sqlserver")

DIALECT_LABELS = {
    "postgres": "Postgres",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "sqlserver": "SQL Server",
    "unknown": "Unknown dialect",
    "auto": "Auto",
}


@dataclass(frozen=True)
class Example:
    dialect: str
    error: str
    sql: str = ""


@dataclass(frozen=True)
class Rule:
    code: str
    title: str
    summary: str
    why: str
    steps: tuple[str, ...]
    before: str
    after: str
    patterns: tuple[re.Pattern[str], ...]
    examples: tuple[Example, ...]


def _p(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.IGNORECASE)


_CORE: tuple[Rule, ...] = (
    Rule(
        code="missing_relation",
        title="That table is not in this database",
        summary="The query names a table this connection cannot see.",
        why="The table may be misspelled, stored in another schema, or sitting in a different database than the one you connected to.",
        steps=(
            "Compare the name in the message, letter by letter, with the real table list.",
            "Confirm you are connected to the database you think you are.",
            "If the table lives in a schema, write schema.table, for example sales.orders.",
        ),
        before="SELECT * FROM order;",
        after="SELECT * FROM orders;",
        patterns=(
            _p(
                r"""relation\s+\S+\s+does not exist""",
                r"""table\s+["'`][^"'`\n]+["'`]\s+doesn['’]?t exist""",
                r"""no such table\b""",
                r"""invalid object name\b""",
                r"""\bERROR\s+1146\b""",
                r"""\bMsg\s+208\b""",
                r"""\bSQLSTATE[:\s]+42P01\b""",
            ),
        ),
        examples=(
            Example(
                "mysql",
                "ERROR 1146 (42S02): Table 'shop.orders' doesn't exist",
                "SELECT * FROM orders;",
            ),
            Example(
                "postgres",
                'ERROR:  relation "orders" does not exist\nLINE 1: SELECT * FROM orders;\n                      ^',
                "SELECT * FROM orders;",
            ),
            Example("sqlite", "Error: no such table: orders", "SELECT * FROM orders;"),
            Example(
                "sqlserver",
                "Msg 208, Level 16, State 1, Line 1\nInvalid object name 'orders'.",
                "SELECT * FROM orders;",
            ),
        ),
    ),
    Rule(
        code="missing_column",
        title="That column is not on this table",
        summary="The table exists, but this column name does not.",
        why="One wrong letter, or a column that actually lives on another table in the join, produces this error.",
        steps=(
            "Read the column name in the message.",
            "If the message suggests another column, use that spelling.",
            "List the real columns and copy the name from there. Do not retype it.",
        ),
        before="SELECT revenues FROM orders;",
        after="SELECT revenue FROM orders;",
        patterns=(
            _p(
                r"""column\s+\S+\s+does not exist""",
                r"""unknown column\b""",
                r"""no such column\b""",
                r"""invalid column name\b""",
                r"""\bERROR\s+1054\b""",
                r"""\bMsg\s+207\b""",
                r"""\bSQLSTATE[:\s]+42703\b""",
            ),
        ),
        examples=(
            Example(
                "sqlite",
                "Error: no such column: revenues",
                "SELECT revenues FROM orders;",
            ),
            Example(
                "postgres",
                'ERROR:  column "revenues" does not exist\n'
                "LINE 1: SELECT revenues FROM orders;\n"
                "               ^\n"
                'HINT:  Perhaps you meant to reference the column "orders.revenue".',
                "SELECT revenues FROM orders;",
            ),
            Example(
                "mysql",
                "ERROR 1054 (42S22): Unknown column 'revenues' in 'field list'",
                "SELECT revenues FROM orders;",
            ),
            Example(
                "sqlserver",
                "Msg 207, Level 16, State 1, Line 1\nInvalid column name 'revenues'.",
                "SELECT revenues FROM orders;",
            ),
        ),
    ),
    Rule(
        code="ambiguous_column",
        title="That column name exists on more than one table",
        summary="A JOIN made this name point at two columns.",
        why="Both tables have this column. An unqualified name could mean either one, and the database will not guess.",
        steps=(
            "Prefix the column with its table or alias, such as orders.id.",
            "Do that for every column that exists on both sides of the JOIN.",
            "Keep the aliases short and use the same ones all the way through the query.",
        ),
        before="SELECT id\nFROM orders\nJOIN customers ON orders.customer_id = customers.id;",
        after="SELECT orders.id\nFROM orders\nJOIN customers ON orders.customer_id = customers.id;",
        patterns=(
            _p(
                r"""\bis ambiguous\b""",
                r"""ambiguous column name\b""",
                r"""\bERROR\s+1052\b""",
                r"""\bMsg\s+209\b""",
                r"""\bSQLSTATE[:\s]+42702\b""",
            ),
        ),
        examples=(
            Example(
                "sqlserver",
                "Msg 209, Level 16, State 1, Line 1\nAmbiguous column name 'id'.",
                "SELECT id FROM orders JOIN customers ON orders.customer_id = customers.id;",
            ),
            Example(
                "postgres",
                'ERROR:  column reference "id" is ambiguous\nLINE 1: SELECT id FROM orders JOIN customers USING (id);',
                "SELECT id FROM orders JOIN customers ON orders.customer_id = customers.id;",
            ),
            Example(
                "mysql",
                "ERROR 1052 (23000): Column 'id' in field list is ambiguous",
                "SELECT id FROM orders JOIN customers ON orders.customer_id = customers.id;",
            ),
            Example(
                "sqlite",
                "Error: ambiguous column name: id",
                "SELECT id FROM orders JOIN customers ON orders.customer_id = customers.id;",
            ),
        ),
    ),
    Rule(
        code="group_by",
        title="Mix a plain column with an aggregate, and say how to group",
        summary="SELECT asks for a detail column and a SUM or COUNT at the same time.",
        why="An aggregate compresses many rows into one number. A plain column still has many values, so the database needs the GROUP BY list to know which rows collapse together.",
        steps=(
            "Put every selected column that is not inside SUM, COUNT, AVG, MIN, or MAX into the GROUP BY.",
            "Or wrap that column in an aggregate if you do not need one row per value.",
            "Do not put the aggregate expression itself in the GROUP BY.",
        ),
        before="SELECT customer_id, SUM(total)\nFROM orders;",
        after="SELECT customer_id, SUM(total)\nFROM orders\nGROUP BY customer_id;",
        patterns=(
            _p(
                r"""must appear in the group by""",
                r"""not in group by clause""",
                r"""not contained in either an aggregate function or the group by""",
                r"""\bERROR\s+1055\b""",
                r"""\bMsg\s+8120\b""",
                r"""\bSQLSTATE[:\s]+42803\b""",
            ),
        ),
        examples=(
            Example(
                "postgres",
                'ERROR:  column "orders.customer_id" must appear in the GROUP BY clause '
                "or be used in an aggregate function",
                "SELECT customer_id, SUM(total) FROM orders;",
            ),
            Example(
                "mysql",
                "ERROR 1055 (42000): Expression #1 of SELECT list is not in GROUP BY clause and "
                "contains nonaggregated column 'shop.orders.customer_id' which is not functionally "
                "dependent on columns in GROUP BY clause; this is incompatible with "
                "sql_mode=only_full_group_by",
                "SELECT customer_id, SUM(total) FROM orders;",
            ),
            Example(
                "sqlserver",
                "Msg 8120, Level 16, State 1, Line 1\n"
                "Column 'orders.customer_id' is invalid in the select list because it is not "
                "contained in either an aggregate function or the GROUP BY clause.",
                "SELECT customer_id, SUM(total) FROM orders;",
            ),
        ),
    ),
    Rule(
        code="not_null",
        title="A required column was left empty",
        summary="The statement tried to save NULL in a NOT NULL column.",
        why="The column is required. An INSERT that skips it, or an UPDATE that sets it to NULL, is rejected.",
        steps=(
            "Add the column to the INSERT list and give it a value.",
            "If the value is supposed to be optional, that is a schema change, not a query typo.",
            "On a CSV load, an empty field arrives as NULL. Fill it, or give the column a default.",
        ),
        before="INSERT INTO users (id, name)\nVALUES (1, 'Ada');",
        after="INSERT INTO users (id, name, email)\nVALUES (1, 'Ada', 'ada@example.com');",
        patterns=(
            _p(
                r"""not-null constraint""",
                r"""not null constraint failed""",
                r"""cannot be null""",
                r"""does not allow nulls""",
                r"""cannot insert the value null""",
                r"""\bERROR\s+1048\b""",
                r"""\bMsg\s+515\b""",
                r"""\bSQLSTATE[:\s]+23502\b""",
            ),
        ),
        examples=(
            Example(
                "mysql",
                "ERROR 1048 (23000): Column 'email' cannot be null",
                "INSERT INTO users (id, name) VALUES (1, 'Ada');",
            ),
            Example(
                "postgres",
                'ERROR:  null value in column "email" of relation "users" violates not-null constraint\n'
                "DETAIL:  Failing row contains (1, null, Ada).",
                "INSERT INTO users (id, name) VALUES (1, 'Ada');",
            ),
            Example(
                "sqlite",
                "Error: NOT NULL constraint failed: users.email",
                "INSERT INTO users (id, name) VALUES (1, 'Ada');",
            ),
            Example(
                "sqlserver",
                "Msg 515, Level 16, State 2, Line 1\n"
                "Cannot insert the value NULL into column 'email', table 'shop.dbo.users'; "
                "column does not allow nulls. INSERT fails.",
                "INSERT INTO users (id, name) VALUES (1, 'Ada');",
            ),
        ),
    ),
    Rule(
        code="unique_violation",
        title="That value is already in the table",
        summary="A UNIQUE or PRIMARY KEY column already has this value.",
        why="The constraint allows the value once. A second insert with the same key, or a retry of the same insert, is rejected.",
        steps=(
            "If you meant to change the existing row, UPDATE it instead of inserting another.",
            "If this is a new row, use a different value for the key named in the message.",
            "Check that a retry did not run the same INSERT twice.",
        ),
        before="INSERT INTO users (email)\nVALUES ('ada@example.com');",
        after="UPDATE users\nSET name = 'Ada Lovelace'\nWHERE email = 'ada@example.com';",
        patterns=(
            _p(
                r"""duplicate key value violates unique""",
                r"""violates unique constraint""",
                r"""unique constraint failed""",
                r"""duplicate entry\b""",
                r"""unique key constraint""",
                r"""\bERROR\s+1062\b""",
                r"""\bMsg\s+2627\b""",
                r"""\bMsg\s+2601\b""",
                r"""\bSQLSTATE[:\s]+23505\b""",
            ),
        ),
        examples=(
            Example(
                "sqlite",
                "Error: UNIQUE constraint failed: users.email",
                "INSERT INTO users (email) VALUES ('ada@example.com');",
            ),
            Example(
                "postgres",
                'ERROR:  duplicate key value violates unique constraint "users_email_key"\n'
                "DETAIL:  Key (email)=(ada@example.com) already exists.",
                "INSERT INTO users (email) VALUES ('ada@example.com');",
            ),
            Example(
                "mysql",
                "ERROR 1062 (23000): Duplicate entry 'ada@example.com' for key 'users.email'",
                "INSERT INTO users (email) VALUES ('ada@example.com');",
            ),
            Example(
                "sqlserver",
                "Msg 2627, Level 14, State 1, Line 1\n"
                "Violation of UNIQUE KEY constraint 'users_email_key'. Cannot insert duplicate key "
                "in object 'dbo.users'. The duplicate key value is (ada@example.com).",
                "INSERT INTO users (email) VALUES ('ada@example.com');",
            ),
        ),
    ),
    Rule(
        code="foreign_key",
        title="This row points at a parent that is not there",
        summary="A foreign key blocked the change.",
        why="Every child value has to already exist on the parent table. Inserting a missing id, or deleting a parent that still has children, is rejected.",
        steps=(
            "Insert the parent row first, then the child.",
            "Or change the child value to an id that already exists.",
            "When deleting, remove the child rows first, then the parent.",
        ),
        before="INSERT INTO orders (id, customer_id)\nVALUES (1, 99);",
        after=(
            "INSERT INTO customers (id, name)\nVALUES (99, 'Ada');\n\n"
            "INSERT INTO orders (id, customer_id)\nVALUES (1, 99);"
        ),
        patterns=(
            _p(
                r"""foreign key constraint""",
                r"""\bERROR\s+1452\b""",
                r"""\bMsg\s+547\b""",
                r"""\bSQLSTATE[:\s]+23503\b""",
            ),
        ),
        examples=(
            Example(
                "sqlserver",
                "Msg 547, Level 16, State 0, Line 1\n"
                'The INSERT statement conflicted with the FOREIGN KEY constraint "orders_customer_id_fkey". '
                'The conflict occurred in database "shop", table "dbo.customers", column \'id\'.',
                "INSERT INTO orders (id, customer_id) VALUES (1, 99);",
            ),
            Example(
                "postgres",
                'ERROR:  insert or update on table "orders" violates foreign key constraint "orders_customer_id_fkey"\n'
                'DETAIL:  Key (customer_id)=(99) is not present in table "customers".',
                "INSERT INTO orders (id, customer_id) VALUES (1, 99);",
            ),
            Example(
                "mysql",
                "ERROR 1452 (23000): Cannot add or update a child row: a foreign key constraint fails "
                "(`shop`.`orders`, CONSTRAINT `orders_customer_id_fkey` FOREIGN KEY (`customer_id`) "
                "REFERENCES `customers` (`id`))",
                "INSERT INTO orders (id, customer_id) VALUES (1, 99);",
            ),
            Example(
                "sqlite",
                "Error: FOREIGN KEY constraint failed",
                "INSERT INTO orders (id, customer_id) VALUES (1, 99);",
            ),
        ),
    ),
    Rule(
        code="datatype_mismatch",
        title="That value is the wrong type",
        summary="The column cannot store this literal.",
        why="A numeric column was given text, or a date column was given a format it does not accept. Quotes make a value text, even when it looks like a number.",
        steps=(
            "For a numeric column, write 12 and not '12'.",
            "If the text is not actually a number, fix the value. Do not force it into a numeric column.",
            "Dates usually need the format '2026-11-11'.",
        ),
        before="SELECT * FROM orders WHERE id = '12a';",
        after="SELECT * FROM orders WHERE id = 12;",
        patterns=(
            _p(
                r"""invalid input syntax for type""",
                r"""incorrect\s+(?:integer|int|double|decimal|datetime|date)\s+value""",
                r"""datatype mismatch""",
                r"""cannot store\s+\w+\s+value""",
                r"""conversion failed when converting""",
                r"""truncated incorrect\s+(?:integer|double|decimal)""",
                r"""\bERROR\s+1366\b""",
                r"""\bERROR\s+1292\b""",
                r"""\bMsg\s+245\b""",
                r"""\bSQLSTATE[:\s]+22P02\b""",
            ),
        ),
        examples=(
            Example(
                "postgres",
                'ERROR:  invalid input syntax for type integer: "12a"\n'
                "LINE 1: SELECT * FROM orders WHERE id = '12a';",
                "SELECT * FROM orders WHERE id = '12a';",
            ),
            Example(
                "mysql",
                "ERROR 1366 (HY000): Incorrect integer value: '12a' for column 'id' at row 1",
                "SELECT * FROM orders WHERE id = '12a';",
            ),
            Example(
                "sqlite",
                "Error: cannot store TEXT value in INTEGER column users.id",
                "INSERT INTO users (id) VALUES ('Ada');",
            ),
            Example(
                "sqlserver",
                "Msg 245, Level 16, State 1, Line 1\n"
                "Conversion failed when converting the varchar value '12a' to data type int.",
                "SELECT * FROM orders WHERE id = '12a';",
            ),
        ),
    ),
    Rule(
        code="subquery_cardinality",
        title="The subquery returned more than one row",
        summary="A comparison wanted one value and got several.",
        why="= , < , and the other comparisons accept a single value. This subquery is used in that spot and returned more than one row.",
        steps=(
            "Use IN instead of = when several rows are a valid answer.",
            "Or keep = and return one row. Postgres, MySQL, and SQLite use ORDER BY ... LIMIT 1. SQL Server uses TOP 1.",
            "Aggregate the subquery, such as SELECT MAX(id), when you want one summary value.",
        ),
        before="SELECT *\nFROM orders\nWHERE customer_id = (\n  SELECT id FROM customers WHERE country = 'IN'\n);",
        after="SELECT *\nFROM orders\nWHERE customer_id IN (\n  SELECT id FROM customers WHERE country = 'IN'\n);",
        patterns=(
            _p(
                r"""more than one row returned by a subquery""",
                r"""subquery returns more than 1 row""",
                r"""subquery returned more than 1 value""",
                r"""sub-select returns\s+\d+\s+rows?""",
                r"""\bERROR\s+1242\b""",
                r"""\bMsg\s+512\b""",
                r"""\bSQLSTATE[:\s]+21000\b""",
            ),
        ),
        examples=(
            Example(
                "mysql",
                "ERROR 1242 (21000): Subquery returns more than 1 row",
                "SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE country = 'IN');",
            ),
            Example(
                "postgres",
                "ERROR:  more than one row returned by a subquery used as an expression",
                "SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE country = 'IN');",
            ),
            Example(
                "sqlite",
                "Error: sub-select returns 2 rows",
                "SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE country = 'IN');",
            ),
            Example(
                "sqlserver",
                "Msg 512, Level 16, State 1, Line 1\n"
                "Subquery returned more than 1 value. This is not permitted when the subquery follows "
                "=, !=, <, <= , >, >= or when the subquery is used as an expression.",
                "SELECT * FROM orders WHERE customer_id = (SELECT id FROM customers WHERE country = 'IN');",
            ),
        ),
    ),
    Rule(
        code="syntax",
        title="The query is not valid SQL",
        summary="A word, comma, or quote is in the wrong place.",
        why="The database reads SQL in order. A misspelled keyword, a missing comma, or an extra comma makes the rest of the line unreadable, so it stops at the token named in the message.",
        steps=(
            "Read the word in quotes. That is where the database gave up.",
            "Check the word just before it. A missing comma or a misspelled keyword is the usual cause.",
            "FORM should be FROM. A comma immediately before FROM, or before a closing parenthesis, should be deleted.",
        ),
        before="SELECT * FORM orders;",
        after="SELECT * FROM orders;",
        patterns=(
            _p(
                r"""syntax error""",
                r"""error in your sql syntax""",
                r"""incorrect syntax near""",
                r"""\bERROR\s+1064\b""",
                r"""\bMsg\s+102\b""",
                r"""\bSQLSTATE[:\s]+42601\b""",
            ),
        ),
        examples=(
            Example(
                "postgres",
                'ERROR:  syntax error at or near "FORM"\nLINE 1: SELECT * FORM orders;\n                     ^',
                "SELECT * FORM orders;",
            ),
            Example(
                "mysql",
                "ERROR 1064 (42000): You have an error in your SQL syntax; check the manual that "
                "corresponds to your MySQL server version for the right syntax to use near "
                "'FORM orders' at line 1",
                "SELECT * FORM orders;",
            ),
            Example("sqlite", 'Error: near "FORM": syntax error', "SELECT * FORM orders;"),
            Example(
                "sqlserver",
                "Msg 102, Level 15, State 1, Line 1\nIncorrect syntax near 'FORM'.",
                "SELECT * FORM orders;",
            ),
        ),
    ),
)


DIALECT_TIPS: dict[tuple[str, str], str] = {
    ("missing_relation", "postgres"): "In psql, \\dt lists tables. If the table is in another schema, write sales.orders.",
    ("missing_relation", "mysql"): "The quoted name is database.table. Run SELECT DATABASE(); and confirm you are in that database.",
    ("missing_relation", "sqlite"): "SQLite has one file and no schemas. Check the file you opened, then the spelling.",
    ("missing_relation", "sqlserver"): "Check the database dropdown, then the schema, usually dbo. The full name looks like shop.dbo.orders.",
    ("missing_column", "postgres"): "If a HINT line names a column, try that spelling first.",
    ("missing_column", "mysql"): "Unknown column means none of the tables in this query have that name.",
    ("missing_column", "sqlite"): "Run PRAGMA table_info(your_table); and copy the name from the list.",
    ("missing_column", "sqlserver"): "Copy the column name from Object Explorer. Do not retype it.",
    ("syntax", "postgres"): "The caret under LINE 1 sits on the token where reading stopped.",
    ("syntax", "mysql"): "The near '...' snippet is the tail of the query from the failure onward. Read its first word.",
    ("syntax", "sqlite"): "The word inside near \"...\" is the token SQLite refused.",
    ("syntax", "sqlserver"): "Incorrect syntax near names the token. Inspect the keyword just before it.",
    ("foreign_key", "sqlite"): "SQLite checks foreign keys only after PRAGMA foreign_keys = ON.",
    ("group_by", "sqlite"): "SQLite usually allows this query. Postgres, MySQL in ONLY_FULL_GROUP_BY mode, and SQL Server do not.",
    ("ambiguous_column", "sqlite"): "SQLite prints ambiguous column name: and then the bare name.",
}

from sql_error_coach.more_rules import MORE_RULES, MORE_TIPS  # noqa: E402

RULES: tuple[Rule, ...] = MORE_RULES + _CORE
DIALECT_TIPS.update(MORE_TIPS)


def rule_by_code(code: str) -> Rule:
    for rule in RULES:
        if rule.code == code:
            return rule
    raise KeyError(code)
