from sqlalchemy import text
from connection_manager import get_engine_for_connection
from sql_guardrails import validate_sql, SQLValidationError
from sql_generator import generate_sql

class QueryExecutionError(Exception):
    pass

async def execute_query(question: str, connection_id: int = 0) -> dict:
    raw_sql = await generate_sql(question, connection_id)

    try:
        validated_sql = await validate_sql(raw_sql, connection_id)
    except SQLValidationError as e:
        raise QueryExecutionError(f"SQL validation failed: {str(e)}")

    try:
        engine = await get_engine_for_connection(connection_id)
        async with engine.connect() as conn:
            result = await conn.execute(text(validated_sql))
            col_names = list(result.keys())
            rows = [dict(zip(col_names, row)) for row in result.fetchall()]

        return {
            "question": question,
            "sql": validated_sql,
            "results": rows,
            "columns": col_names,
            "row_count": len(rows)
        }
    except Exception as e:
        raise QueryExecutionError(f"Query execution failed: {str(e)}")