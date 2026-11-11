"""Stored fixes beyond the original ten. Checked before the core rules."""

from sql_error_coach.catalog import Example, Rule, _p

MORE_TIPS: dict[tuple[str, str], str] = {
    ("division_by_zero", "postgres"): "NULLIF(units, 0) turns a zero divisor into NULL so the row survives.",
    ("division_by_zero", "mysql"): "NULLIF(units, 0) works in MySQL too. The row becomes NULL instead of failing the query.",
    ("permission_denied", "postgres"): "The owner of the table, or a superuser, has to run the GRANT. The query text is fine.",
    ("missing_function", "postgres"): "The HINT line often shows the argument types Postgres actually has.",
    ("transaction_aborted", "postgres"): "In psql, ROLLBACK; ends the failed transaction. Then run the statement again.",
    ("deadlock", "mysql"): "InnoDB already rolled back one transaction. Run that statement again.",
}


def _rule(
    code: str,
    title: str,
    summary: str,
    why: str,
    steps: tuple[str, ...],
    before: str,
    after: str,
    patterns: tuple[str, ...],
    examples: tuple[Example, ...],
) -> Rule:
    return Rule(
        code=code,
        title=title,
        summary=summary,
        why=why,
        steps=steps,
        before=before,
        after=after,
        patterns=(_p(*patterns),),
        examples=examples,
    )


MORE_RULES: tuple[Rule, ...] = (
    _rule(
        "division_by_zero",
        "The query divided by zero",
        "A divisor in this statement was zero.",
        "SQL stops the whole statement when a number is divided by zero. A guard such as NULLIF turns that zero into NULL for that row.",
        (
            "Find the divisor. It may be a column that is zero on some rows, not a literal 0.",
            "Wrap that divisor in NULLIF(column, 0) so a zero becomes NULL instead of an error.",
            "If zero should have been filtered out, add that filter in WHERE before the division.",
        ),
        "SELECT total / units FROM orders;",
        "SELECT total / NULLIF(units, 0) FROM orders;",
        (r"division by zero", r"divide by zero", r"\bERROR\s+1365\b", r"\bMsg\s+8134\b"),
        (
            Example("postgres", "ERROR:  division by zero", "SELECT total / units FROM orders;"),
            Example("mysql", "ERROR 1365 (22012): Division by 0", "SELECT total / units FROM orders;"),
            Example(
                "sqlserver",
                "Msg 8134, Level 16, State 1, Line 1\nDivide by zero error encountered.",
                "SELECT total / units FROM orders;",
            ),
        ),
    ),
    _rule(
        "permission_denied",
        "This account is not allowed to do that",
        "The query is valid, and this login may not run it.",
        "The database refused the statement because the user lacks a privilege. Changing the SQL will not grant that privilege.",
        (
            "Read the command and the object in the message. That is the privilege you need.",
            "Ask the table owner to grant it, or connect with an account that already has it.",
            "Do not rewrite the SELECT. The text is not the problem.",
        ),
        "SELECT * FROM salaries;",
        "GRANT SELECT ON salaries TO ada;",
        (
            r"permission denied",
            r"command denied",
            r"permission was denied",
            r"\bERROR\s+1142\b",
            r"\bMsg\s+229\b",
        ),
        (
            Example("postgres", "ERROR:  permission denied for table salaries", "SELECT * FROM salaries;"),
            Example(
                "mysql",
                "ERROR 1142 (42000): SELECT command denied to user 'ada'@'localhost' for table 'salaries'",
                "SELECT * FROM salaries;",
            ),
            Example(
                "sqlserver",
                "Msg 229, Level 14, State 5, Line 1\n"
                "The SELECT permission was denied on the object 'salaries', database 'shop', schema 'dbo'.",
                "SELECT * FROM salaries;",
            ),
        ),
    ),
    _rule(
        "missing_database",
        "That database is not on this server",
        "The connection named a database the server does not have.",
        "The query never started. The server rejected the database name in the connection.",
        (
            "Check the database name in the connection string or the database dropdown.",
            "List the databases on this server and copy the name.",
            "Create the database only if you meant to, and you have permission to create one.",
        ),
        "-- connected to database shop",
        "-- Connect to a database that exists on this server, then run the query.",
        (
            r"unknown database",
            r"""database\s+["'`]\S+["'`]\s+does not exist""",
            r"\bERROR\s+1049\b",
            r"\bMsg\s+911\b",
        ),
        (
            Example("mysql", "ERROR 1049 (42000): Unknown database 'shop'", ""),
            Example("postgres", 'FATAL:  database "shop" does not exist', ""),
            Example(
                "sqlserver",
                "Msg 911, Level 16, State 1, Line 1\nDatabase 'shop' does not exist. Make sure that the name is entered correctly.",
                "",
            ),
        ),
    ),
    _rule(
        "missing_function",
        "That function is not there",
        "No function matches this name and these argument types.",
        "The name can be right while the argument types are wrong. Postgres treats round(float) and round(numeric, int) as different functions.",
        (
            "Read the argument types in the parentheses. One of them is the mismatch.",
            "Cast the argument to the type the function expects.",
            "If there is a HINT, that list is the set of functions the database does have.",
        ),
        "SELECT round(price, 2) FROM orders;",
        "SELECT round(price::numeric, 2) FROM orders;",
        (
            r"function\s+.+?\s+does not exist",
            r"no such function",
            r"not a recognized built-in function",
            r"\bERROR\s+1305\b",
            r"\bMsg\s+195\b",
        ),
        (
            Example(
                "postgres",
                "ERROR:  function round(double precision, integer) does not exist\n"
                "HINT:  No function matches the given name and argument types.",
                "SELECT round(price, 2) FROM orders;",
            ),
            Example("sqlite", "Error: no such function: round", "SELECT round(price, 2) FROM orders;"),
            Example(
                "mysql",
                "ERROR 1305 (42000): FUNCTION shop.round does not exist",
                "SELECT round(price, 2) FROM orders;",
            ),
            Example(
                "sqlserver",
                "Msg 195, Level 15, State 10, Line 1\n'round' is not a recognized built-in function name.",
                "SELECT round(price, 2) FROM orders;",
            ),
        ),
    ),
    _rule(
        "operator_mismatch",
        "Those two values cannot be compared like that",
        "The operator does not exist for this pair of types.",
        "A number and a piece of text need an explicit cast. The database will not guess which type you meant.",
        (
            "Look at the two types after the colon, such as integer and text.",
            "Cast the text side when it really is a number, or cast the number side when you want text.",
            "Do not compare a number column with a quoted word.",
        ),
        "SELECT * FROM orders WHERE id = code;",
        "SELECT * FROM orders WHERE id = CAST(code AS integer);",
        (r"operator does not exist", r"no operator matches the given name and argument types"),
        (
            Example(
                "postgres",
                "ERROR:  operator does not exist: integer = text\n"
                "HINT:  No operator matches the given name and argument types. You might need to add explicit type casts.",
                "SELECT * FROM orders WHERE id = code;",
            ),
        ),
    ),
    _rule(
        "insert_count",
        "The INSERT list and the VALUES list differ",
        "The number of columns and the number of values are not the same.",
        "Each column in the INSERT needs one value, in the same order. An extra comma or a missing value shifts the rest.",
        (
            "Count the columns in the INSERT list.",
            "Count the values in VALUES. The two counts have to match.",
            "Name the columns. Do not rely on table order.",
        ),
        "INSERT INTO users (id, name, email)\nVALUES (1, 'Ada');",
        "INSERT INTO users (id, name, email)\nVALUES (1, 'Ada', 'ada@example.com');",
        (
            r"more expressions than target columns",
            r"more target columns than expressions",
            r"column count doesn't match value count",
            r"values were supplied",
            r"number of supplied values does not match",
            r"\bERROR\s+1136\b",
            r"\bMsg\s+213\b",
        ),
        (
            Example(
                "postgres",
                "ERROR:  INSERT has more target columns than expressions",
                "INSERT INTO users (id, name, email) VALUES (1, 'Ada');",
            ),
            Example(
                "mysql",
                "ERROR 1136 (21S01): Column count doesn't match value count at row 1",
                "INSERT INTO users (id, name, email) VALUES (1, 'Ada');",
            ),
            Example(
                "sqlite",
                "Error: table users has 3 columns but 2 values were supplied",
                "INSERT INTO users (id, name, email) VALUES (1, 'Ada');",
            ),
            Example(
                "sqlserver",
                "Msg 213, Level 16, State 1, Line 1\n"
                "Column name or number of supplied values does not match table definition.",
                "INSERT INTO users (id, name, email) VALUES (1, 'Ada');",
            ),
        ),
    ),
    _rule(
        "value_too_long",
        "That value does not fit in the column",
        "The text is longer than the column allows.",
        "A VARCHAR(5) cannot store six characters. The database rejects the row instead of cutting the value, unless an older setting still truncates it.",
        (
            "Shorten the value, or store it in a wider column.",
            "Read the length in the message. That number is the limit.",
            "Check for a hidden space or a newline that pushes the value over the limit.",
        ),
        "INSERT INTO codes (code) VALUES ('ABCDEF');",
        "INSERT INTO codes (code) VALUES ('ABCDE');",
        (
            r"value too long for type",
            r"data too long for column",
            r"string or binary data would be truncated",
            r"\bERROR\s+1406\b",
            r"\bMsg\s+8152\b",
            r"\bSQLSTATE[:\s]+22001\b",
        ),
        (
            Example(
                "postgres",
                "ERROR:  value too long for type character varying(5)",
                "INSERT INTO codes (code) VALUES ('ABCDEF');",
            ),
            Example(
                "mysql",
                "ERROR 1406 (22001): Data too long for column 'code' at row 1",
                "INSERT INTO codes (code) VALUES ('ABCDEF');",
            ),
            Example(
                "sqlserver",
                "Msg 8152, Level 16, State 14, Line 1\nString or binary data would be truncated.",
                "INSERT INTO codes (code) VALUES ('ABCDEF');",
            ),
        ),
    ),
    _rule(
        "aggregate_where",
        "An aggregate cannot filter rows in WHERE",
        "WHERE runs before SUM or COUNT, so it cannot use them.",
        "WHERE chooses rows. An aggregate needs those rows first. The filter on the aggregate belongs in HAVING, after GROUP BY.",
        (
            "Move the condition that uses SUM, COUNT, AVG, MIN, or MAX from WHERE to HAVING.",
            "Leave ordinary row filters, such as status = 'open', in WHERE.",
            "HAVING comes after GROUP BY.",
        ),
        "SELECT customer_id, SUM(total)\nFROM orders\nWHERE SUM(total) > 100\nGROUP BY customer_id;",
        "SELECT customer_id, SUM(total)\nFROM orders\nGROUP BY customer_id\nHAVING SUM(total) > 100;",
        (
            r"aggregate functions are not allowed in where",
            r"invalid use of group function",
            r"misuse of aggregate",
            r"aggregate may not appear in the where",
            r"\bERROR\s+1111\b",
            r"\bMsg\s+147\b",
        ),
        (
            Example(
                "postgres",
                "ERROR:  aggregate functions are not allowed in WHERE",
                "SELECT customer_id, SUM(total) FROM orders WHERE SUM(total) > 100 GROUP BY customer_id;",
            ),
            Example("mysql", "ERROR 1111 (HY000): Invalid use of group function", "SELECT customer_id FROM orders WHERE SUM(total) > 100;"),
            Example(
                "sqlite",
                "Error: misuse of aggregate function SUM()",
                "SELECT customer_id FROM orders WHERE SUM(total) > 100;",
            ),
            Example(
                "sqlserver",
                "Msg 147, Level 15, State 1, Line 1\n"
                "An aggregate may not appear in the WHERE clause unless it is in a subquery.",
                "SELECT customer_id FROM orders WHERE SUM(total) > 100;",
            ),
        ),
    ),
    _rule(
        "undeclared_variable",
        "That variable was never declared",
        "The statement uses a variable the batch does not know.",
        "SQL Server needs DECLARE before a variable is used. Postgres uses $1 only when the statement was given a parameter.",
        (
            "Declare the variable before the statement that uses it.",
            "Check the @ name. One different character is a different variable.",
            "In Postgres, pass the parameter from the client, or replace $1 with a literal while you are testing.",
        ),
        "SELECT @bonus;",
        "DECLARE @bonus int = 10;\nSELECT @bonus;",
        (r"must declare the scalar variable", r"there is no parameter", r"\bMsg\s+137\b"),
        (
            Example(
                "sqlserver",
                "Msg 137, Level 15, State 1, Line 1\nMust declare the scalar variable \"@bonus\".",
                "SELECT @bonus;",
            ),
            Example("postgres", "ERROR:  there is no parameter $1", "SELECT $1;"),
        ),
    ),
    _rule(
        "transaction_aborted",
        "The transaction already failed",
        "An earlier statement in this transaction failed, so later statements are ignored.",
        "Postgres keeps the transaction open after an error. Nothing else runs until you roll it back.",
        (
            "Run ROLLBACK.",
            "Fix the statement that failed first.",
            "Run the transaction again from the beginning.",
        ),
        "UPDATE orders SET total = total + 1;",
        "ROLLBACK;",
        (r"current transaction is aborted", r"commands ignored until end of transaction"),
        (
            Example(
                "postgres",
                "ERROR:  current transaction is aborted, commands ignored until end of transaction block",
                "UPDATE orders SET total = total + 1;",
            ),
        ),
    ),
    _rule(
        "deadlock",
        "Two transactions blocked each other",
        "This transaction was chosen as the one to fail.",
        "Each transaction held a row the other needed. The database aborted one of them so the rest can continue.",
        (
            "Run the statement again. The other transaction may have finished.",
            "Touch rows in the same order in every transaction, so two sessions cannot lock each other.",
            "Keep the transaction short. Do not wait on a person while rows are locked.",
        ),
        "UPDATE orders SET total = 1 WHERE id = 1;",
        "-- Run the statement again after the other transaction finishes.\nUPDATE orders SET total = 1 WHERE id = 1;",
        (r"deadlock detected", r"deadlock found", r"was deadlocked", r"\bERROR\s+1213\b", r"\bMsg\s+1205\b"),
        (
            Example("postgres", "ERROR:  deadlock detected\nDETAIL:  Process 42 waits for ShareLock.", "UPDATE orders SET total = 1 WHERE id = 1;"),
            Example(
                "mysql",
                "ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction",
                "UPDATE orders SET total = 1 WHERE id = 1;",
            ),
            Example(
                "sqlserver",
                "Msg 1205, Level 13, State 51, Line 1\n"
                "Transaction (Process ID 42) was deadlocked on lock resources with another process "
                "and has been chosen as the deadlock victim. Rerun the transaction.",
                "UPDATE orders SET total = 1 WHERE id = 1;",
            ),
        ),
    ),
    _rule(
        "union_mismatch",
        "The UNION sides have different widths",
        "Each SELECT in a UNION must return the same number of columns.",
        "UNION stacks results. The columns line up by position, so both sides need the same count and compatible types.",
        (
            "Count the expressions in each SELECT.",
            "Add the missing column, or remove the extra one, so the counts match.",
            "Use NULL or a literal as a placeholder when one side has no such column.",
        ),
        "SELECT id, name FROM customers\nUNION\nSELECT id FROM orders;",
        "SELECT id, name FROM customers\nUNION\nSELECT id, NULL FROM orders;",
        (
            r"each union query must have the same number of columns",
            r"different number of columns",
            r"do not have the same number of result columns",
            r"equal number of expressions in their target lists",
            r"\bERROR\s+1222\b",
            r"\bMsg\s+205\b",
        ),
        (
            Example("postgres", "ERROR:  each UNION query must have the same number of columns", "SELECT id, name FROM customers UNION SELECT id FROM orders;"),
            Example(
                "mysql",
                "ERROR 1222 (21000): The used SELECT statements have a different number of columns",
                "SELECT id, name FROM customers UNION SELECT id FROM orders;",
            ),
            Example(
                "sqlite",
                "Error: SELECTs to the left and right of UNION do not have the same number of result columns",
                "SELECT id, name FROM customers UNION SELECT id FROM orders;",
            ),
            Example(
                "sqlserver",
                "Msg 205, Level 16, State 1, Line 1\n"
                "All queries combined using a UNION, INTERSECT or EXCEPT operator must have an equal number of expressions in their target lists.",
                "SELECT id, name FROM customers UNION SELECT id FROM orders;",
            ),
        ),
    ),
    _rule(
        "subquery_alias",
        "That subquery needs a name",
        "A SELECT in the FROM list must have an alias.",
        "The outer query has to call the subquery by a name. Without an alias there is nothing to refer to.",
        (
            "Add AS and a name after the closing parenthesis.",
            "Use that name when you refer to its columns.",
            "The name can be short. It has to be unique in the FROM list.",
        ),
        "SELECT * FROM (SELECT id FROM orders);",
        "SELECT recent.* FROM (SELECT id FROM orders) AS recent;",
        (
            r"subquery in from must have an alias",
            r"every derived table must have its own alias",
            r"\bERROR\s+1248\b",
        ),
        (
            Example(
                "postgres",
                "ERROR:  subquery in FROM must have an alias\n"
                "HINT:  For example, FROM (SELECT ...) [AS] foo.",
                "SELECT * FROM (SELECT id FROM orders);",
            ),
            Example(
                "mysql",
                "ERROR 1248 (42000): Every derived table must have its own alias",
                "SELECT * FROM (SELECT id FROM orders);",
            ),
        ),
    ),
    _rule(
        "missing_from",
        "That table is named, but it is not in FROM",
        "A column was qualified with a table the FROM clause does not include.",
        "orders.id is legal only when orders is in FROM, or when it is a real alias. A typo in the alias produces this error.",
        (
            "Add the missing table to FROM, or fix the alias so it matches a table that is already there.",
            "Check the letter after the dot. That is the name the database could not find.",
            "If you meant a column of the one table you did list, drop the table prefix.",
        ),
        "SELECT orders.id FROM customers;",
        "SELECT orders.id FROM customers JOIN orders ON orders.customer_id = customers.id;",
        (r"missing from-clause entry", r"invalid reference to from-clause entry"),
        (
            Example(
                "postgres",
                'ERROR:  missing FROM-clause entry for table "orders"',
                "SELECT orders.id FROM customers;",
            ),
        ),
    ),
    _rule(
        "check_constraint",
        "A CHECK rule rejected this row",
        "The new values break a rule stored on the table.",
        "A CHECK constraint is a condition every row must satisfy, such as age >= 0. This row does not.",
        (
            "Read the constraint name. It usually contains the column.",
            "Change the value so it satisfies that rule.",
            "Change the CHECK itself only when the rule is wrong, not when this one row is wrong.",
        ),
        "INSERT INTO users (age) VALUES (-1);",
        "INSERT INTO users (age) VALUES (21);",
        (r"violates check constraint", r"check constraint '.+' is violated", r"check constraint failed"),
        (
            Example(
                "postgres",
                'ERROR:  new row for relation "users" violates check constraint "users_age_check"',
                "INSERT INTO users (age) VALUES (-1);",
            ),
            Example(
                "mysql",
                "ERROR 3819 (HY000): Check constraint 'users_age_check' is violated.",
                "INSERT INTO users (age) VALUES (-1);",
            ),
            Example("sqlite", "Error: CHECK constraint failed: users_age_check", "INSERT INTO users (age) VALUES (-1);"),
        ),
    ),
    _rule(
        "dependent_objects",
        "Something else still uses this table",
        "The drop was refused because another object depends on it.",
        "A view, a foreign key, or another table still points here. Dropping it would break that object.",
        (
            "Read the DETAIL line. That is the object that still depends on this one.",
            "Drop or change the dependent object first.",
            "CASCADE drops the dependents too. Use it only when that is what you mean.",
        ),
        "DROP TABLE orders;",
        "-- Drop the view or foreign key that uses orders, then drop the table.\nDROP TABLE orders;",
        (
            r"other objects depend on it",
            r"could not drop object",
            r"cannot drop table",
            r"referenced by a foreign key constraint",
        ),
        (
            Example(
                "postgres",
                'ERROR:  cannot drop table orders because other objects depend on it\n'
                'DETAIL:  view orders_open depends on table orders',
                "DROP TABLE orders;",
            ),
            Example(
                "sqlserver",
                "Msg 3726, Level 16, State 1, Line 1\n"
                "Could not drop object 'orders' because it is referenced by a FOREIGN KEY constraint.",
                "DROP TABLE orders;",
            ),
        ),
    ),
)
