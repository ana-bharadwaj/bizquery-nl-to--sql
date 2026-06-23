from sqlalchemy import text
from connection_manager import get_engine_for_connection


async def get_allowed_tables(connection_id: int = 0):
    engine = await get_engine_for_connection(connection_id)

    if connection_id == 0:
        # Our own Supabase DB tracks allowed tables explicitly
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT table_name FROM bizquery_managed_tables;"))
            return [row[0] for row in result.fetchall()]
    else:
        # External database: expose all tables in the public schema.
        # (We don't control their schema, so there's no managed-tables list to check.)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
                """)
            )
            return [row[0] for row in result.fetchall()]


async def get_schema_context(connection_id: int = 0):
    engine = await get_engine_for_connection(connection_id)
    allowed_tables = await get_allowed_tables(connection_id)
    schema_parts = []

    async with engine.connect() as conn:
        for table in allowed_tables:
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = :table
                    ORDER BY ordinal_position;
                """),
                {"table": table}
            )
            columns = result.fetchall()
            column_lines = [f"  - {col[0]} ({col[1]})" for col in columns]
            schema_parts.append(f"Table: {table}\nColumns:\n" + "\n".join(column_lines))

        fk_result = await conn.execute(
            text("""
                SELECT
                    tc.table_name AS from_table,
                    kcu.column_name AS from_column,
                    ccu.table_name AS to_table,
                    ccu.column_name AS to_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = ANY(:tables);
            """),
            {"tables": allowed_tables}
        )
        foreign_keys = fk_result.fetchall()

    if foreign_keys:
        fk_lines = [f"  - {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}" for fk in foreign_keys]
        schema_parts.append("Foreign Key Relationships:\n" + "\n".join(fk_lines))

    return "\n\n".join(schema_parts)