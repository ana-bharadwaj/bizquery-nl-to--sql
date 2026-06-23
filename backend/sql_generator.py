import os
import anthropic
from dotenv import load_dotenv
from schema_introspection import get_schema_context

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are a PostgreSQL expert. Given a database schema and a natural language question, generate a single, safe, read-only SQL query that answers the question.

Rules:
- Only use SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE.
- Only reference tables and columns that exist in the provided schema.
- Always add a LIMIT clause (max 100 rows) unless the question asks for an aggregate (like COUNT, SUM, AVG) that returns one row.
- Return ONLY the SQL query, no explanation, no markdown formatting, no backticks.
"""

async def generate_sql(question: str, connection_id: int = 0) -> str:
    schema = await get_schema_context(connection_id)

    user_message = f"""Database schema:
{schema}

Question: {question}

Generate the PostgreSQL query."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    sql = response.content[0].text.strip()
    return sql