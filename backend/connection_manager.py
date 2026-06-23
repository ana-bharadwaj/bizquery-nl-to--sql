from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from database import engine as default_engine

# Cache of live engines so we don't recreate a connection pool on every request
_engine_cache = {}

def to_async_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    return raw_url.replace("postgresql://", "postgresql+asyncpg://")


async def test_connection(connection_string: str) -> bool:
    """Tries to connect and run a trivial query. Raises if it fails."""
    test_engine = create_async_engine(to_async_url(connection_string))
    try:
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        return True
    finally:
        await test_engine.dispose()


async def save_connection(name: str, connection_string: str) -> dict:
    # Validate it actually works before saving
    await test_connection(connection_string)

    async with default_engine.begin() as conn:
        result = await conn.execute(
            text("""
                INSERT INTO bizquery_connections (name, connection_string)
                VALUES (:name, :conn_str)
                RETURNING id, name, created_at;
            """),
            {"name": name, "conn_str": connection_string}
        )
        row = result.fetchone()

    return {"id": row[0], "name": row[1], "created_at": str(row[2])}


async def list_connections() -> list:
    async with default_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, name, created_at FROM bizquery_connections ORDER BY created_at DESC;")
        )
        rows = result.fetchall()
    return [{"id": r[0], "name": r[1], "created_at": str(r[2])} for r in rows]


async def get_engine_for_connection(connection_id: int):
    """Returns a cached or freshly created engine for a given connection_id.
    connection_id = 0 means 'use our own default Supabase database'."""
    if connection_id == 0:
        return default_engine

    if connection_id in _engine_cache:
        return _engine_cache[connection_id]

    async with default_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT connection_string FROM bizquery_connections WHERE id = :id;"),
            {"id": connection_id}
        )
        row = result.fetchone()

    if not row:
        raise ValueError(f"No connection found with id {connection_id}")

    new_engine = create_async_engine(to_async_url(row[0]))
    _engine_cache[connection_id] = new_engine
    return new_engine