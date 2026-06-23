from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine
from schema_introspection import get_schema_context
from sql_generator import generate_sql
from sql_guardrails import validate_sql, SQLValidationError
from query_executor import execute_query, QueryExecutionError
import json
from fastapi.responses import StreamingResponse
from decimal import Decimal
from datetime import date, datetime
from fastapi import UploadFile, File
from csv_upload import upload_csv_to_table
from connection_manager import get_engine_for_connection, save_connection, list_connections
from schema_introspection import get_allowed_tables






def safe_json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


app = FastAPI(title="BizQuery API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://bizquery.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/db-check")
async def db_check():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version();"))
        version = result.fetchone()
    return {"postgres_version": version[0]}


@app.get("/schema")
async def schema():
    return {"schema": await get_schema_context()}


@app.get("/tables")
async def list_tables():
    tables = await get_allowed_tables()
    return {"tables": tables}

@app.get("/generate-sql")
async def test_generate_sql(question: str):
    sql = await generate_sql(question)
    return {"question": question, "generated_sql": sql}


@app.get("/validate-sql")
async def test_validate(question: str):
    raw_sql = await generate_sql(question)
    try:
        safe_sql = await validate_sql(raw_sql)
        return {"question": question, "raw_sql": raw_sql, "validated_sql": safe_sql, "safe": True}
    except SQLValidationError as e:
        return {"question": question, "raw_sql": raw_sql, "error": str(e), "safe": False}
    



async def query_event_stream(question: str, connection_id: int = 0):
    def sse_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data, default=safe_json_default)}\n\n"

    try:
        yield sse_event("status", {"message": "Generating SQL..."})
        raw_sql = await generate_sql(question, connection_id)

        yield sse_event("status", {"message": "Validating SQL..."})
        try:
            validated_sql = await validate_sql(raw_sql, connection_id)
        except SQLValidationError as e:
            yield sse_event("error", {"message": str(e)})
            return

        yield sse_event("status", {"message": "Executing query..."})
        engine = await get_engine_for_connection(connection_id)
        async with engine.connect() as conn:
            result = await conn.execute(text(validated_sql))
            col_names = list(result.keys())
            rows = [dict(zip(col_names, row)) for row in result.fetchall()]

        yield sse_event("result", {
            "question": question,
            "sql": validated_sql,
            "columns": col_names,
            "results": rows,
            "row_count": len(rows)
        })

    except Exception as e:
        yield sse_event("error", {"message": str(e)})


@app.get("/query-stream")
async def query_stream(question: str, connection_id: int = 0):
    return StreamingResponse(
        query_event_stream(question, connection_id),
        media_type="text/event-stream"
    )

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), table_name: str = None):
    if not file.filename.endswith(".csv"):
        return {"success": False, "error": "Only .csv files are supported."}

    contents = await file.read()
    name = table_name or file.filename.rsplit(".", 1)[0]

    try:
        result = await upload_csv_to_table(contents, name)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/query")
async def run_query(question: str):
    try:
        result = await execute_query(question)
        return {
            "success": True,
            "question": result["question"],
            "sql": result["sql"],
            "columns": result["columns"],
            "results": result["results"],
            "row_count": result["row_count"]
        }
    except QueryExecutionError as e:
        return {
            "success": False,
            "error": str(e)
        }
    

@app.get("/connections")
async def get_connections():
    connections = await list_connections()
    # Always include the default "0" option representing our own database
    return {"connections": [{"id": 0, "name": "BizQuery Default (NBA data)", "created_at": None}] + connections}


@app.post("/connections")
async def add_connection(name: str, connection_string: str):
    try:
        result = await save_connection(name, connection_string)
        return {"success": True, **result}
    except Exception as e:
        return {"success": False, "error": f"Could not connect: {str(e)}"}