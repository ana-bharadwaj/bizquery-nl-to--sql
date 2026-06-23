import re
import csv
import io
from sqlalchemy import text
from database import engine

def sanitize_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = f"col_{name}"
    return name

def infer_pg_type(values):
    """Looks at sample values in a column and guesses the best Postgres type."""
    sample = [v for v in values if v not in (None, "")]
    if not sample:
        return "TEXT"

    def is_int(v):
        try:
            int(v)
            return True
        except ValueError:
            return False

    def is_float(v):
        try:
            float(v)
            return True
        except ValueError:
            return False

    if all(is_int(v) for v in sample):
        return "BIGINT"
    if all(is_float(v) for v in sample):
        return "NUMERIC"
    return "TEXT"


async def upload_csv_to_table(file_bytes: bytes, desired_table_name: str) -> dict:
    text_data = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_data))

    raw_columns = reader.fieldnames
    if not raw_columns:
        raise ValueError("CSV appears to be empty or has no header row.")

    columns = [sanitize_name(c) for c in raw_columns]
    rows = list(reader)

    col_types = {}
    for orig, col in zip(raw_columns, columns):
        values = [row[orig] for row in rows]
        col_types[col] = infer_pg_type(values)

    table_name = sanitize_name(desired_table_name)
    col_defs = ", ".join(f'"{c}" {col_types[c]}' for c in columns)
    create_stmt = f'CREATE TABLE "{table_name}" ({col_defs});'

    def cast_value(val, pg_type):
        if val in (None, ""):
            return None
        try:
            if pg_type == "BIGINT":
                return int(val)
            if pg_type == "NUMERIC":
                return float(val)
            return val  # TEXT - leave as string
        except (ValueError, TypeError):
            return None  # if a row breaks the inferred type, fall back to NULL rather than crash

    async with engine.begin() as conn:
        await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}";'))
        await conn.execute(text(create_stmt))

        if rows:
            col_list = ", ".join(f'"{c}"' for c in columns)
            placeholders = ", ".join(f":{c}" for c in columns)
            insert_stmt = text(f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})')

            records = []
            for row in rows:
                record = {}
                for orig, col in zip(raw_columns, columns):
                    record[col] = cast_value(row[orig], col_types[col])
                records.append(record)

            await conn.execute(insert_stmt, records)

        await conn.execute(
            text("""
                INSERT INTO bizquery_managed_tables (table_name)
                VALUES (:table_name)
                ON CONFLICT (table_name) DO UPDATE SET uploaded_at = now();
            """),
            {"table_name": table_name}
        )

    return {
        "table_name": table_name,
        "row_count": len(rows),
        "columns": columns
    }