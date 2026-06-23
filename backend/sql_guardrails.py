import re
import sqlparse

from schema_introspection import get_allowed_tables

# Keywords that indicate a destructive or non-read-only operation
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXECUTE", "CALL", "MERGE",
    "REPLACE", "RENAME", "VACUUM", "COMMENT", "SECURITY"
]

MAX_ROW_LIMIT = 100


class SQLValidationError(Exception):
    """Raised when generated SQL fails a guardrail check."""
    pass


def clean_sql(raw_sql: str) -> str:
    sql = raw_sql.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip()


async def validate_sql(raw_sql: str, connection_id: int = 0) -> str:
    """
    Runs a SQL string through all guardrail checks for the given connection.
    Returns the cleaned, validated SQL if safe.
    Raises SQLValidationError if any check fails.
    """
    sql = clean_sql(raw_sql)

    if not sql:
        raise SQLValidationError("Generated SQL is empty.")

    statements = [s for s in sqlparse.parse(sql) if s.token_first(skip_cm=True)]
    if len(statements) != 1:
        raise SQLValidationError(
            f"Expected exactly one SQL statement, found {len(statements)}."
        )

    statement = statements[0]

    first_token = statement.token_first(skip_cm=True)
    first_keyword = first_token.value.upper() if first_token else ""
    if first_keyword not in ("SELECT", "WITH"):
        raise SQLValidationError(
            f"Only SELECT queries are allowed. Found statement starting with '{first_keyword}'."
        )

    sql_upper = sql.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", sql_upper):
            raise SQLValidationError(
                f"Forbidden keyword detected: '{keyword}'. Only read-only SELECT queries are allowed."
            )

    stripped = sql.rstrip(";").rstrip()
    if ";" in stripped:
        raise SQLValidationError("Multiple statements detected (semicolon found mid-query).")

    # Validate against the allowed tables for THIS connection
    allowed_tables = await get_allowed_tables(connection_id)
    sql_lower = sql.lower()
    referenced = re.findall(r"(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql_lower)
    for table in referenced:
        if table not in [t.lower() for t in allowed_tables]:
            raise SQLValidationError(
                f"Query references unapproved table: '{table}'. "
                f"Allowed tables: {', '.join(allowed_tables)}."
            )

    limit_match = re.search(r"\blimit\s+(\d+)", sql_lower)
    if limit_match:
        existing_limit = int(limit_match.group(1))
        if existing_limit > MAX_ROW_LIMIT:
            sql = re.sub(
                r"\blimit\s+\d+", f"LIMIT {MAX_ROW_LIMIT}", sql, flags=re.IGNORECASE
            )
    else:
        has_group_by = "group by" in sql_lower
        is_pure_aggregate = re.search(r"\b(count|sum|avg|min|max)\s*\(", sql_lower) and not has_group_by
        if not is_pure_aggregate:
            sql = sql.rstrip(";").rstrip() + f" LIMIT {MAX_ROW_LIMIT}"

    return sql