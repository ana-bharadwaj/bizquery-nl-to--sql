# BizQuery

BizQuery is an AI-powered analytics platform that lets non-technical users query business data using plain English instead of SQL. Ask a question, get the generated SQL, the results, and a live view of the data — all in one place.

**Live app:** https://bizquery-nl-to-sql.vercel.app

## What it does

Type a question like *"Which team scored the most total points?"* and BizQuery:

1. Reads the live schema of your database (tables, columns, foreign keys)
2. Sends your question plus that schema to Claude, which generates a PostgreSQL query
3. Runs the generated SQL through a guardrails layer that blocks anything unsafe
4. Executes the validated query and streams the results back as they're ready
5. Displays the SQL, the results table, and row count in the UI

You can also:
- **Upload your own CSV** — BizQuery infers column types, creates a table, and makes it immediately queryable
- **Connect a different PostgreSQL database** — switch which database your questions run against

## Architecture

```
React (Vite)  →  FastAPI (async)  →  Claude API  →  PostgreSQL (Supabase)
   frontend         backend          SQL generation      data
```

- **Frontend:** React + Vite, Server-Sent Events (SSE) for live query progress, drag-and-drop CSV upload, multi-database connection picker
- **Backend:** FastAPI (fully async), SQLAlchemy async engine, asyncpg driver
- **Database:** PostgreSQL via Supabase, seeded with a real-world NBA dataset (teams, players, games, ~65k+ rows)
- **LLM:** Claude API (Anthropic) for natural-language-to-SQL translation, using live schema context injected into the prompt

## Safety guardrails

Since an LLM is generating SQL that runs against a real database, every query passes through validation before execution:

- Only single `SELECT` (or `WITH`) statements are allowed — no `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, or other destructive keywords, checked with word-boundary matching so column names like `created_at` don't false-positive
- Multi-statement injection is blocked (no stacking queries with semicolons)
- Queries can only reference tables on an explicit allowlist — for the default database that's a curated table list; for uploaded CSVs or connected databases, it's restricted to that database's own tables
- Every query is capped at 100 rows unless it's a single-row aggregate (`COUNT`, `SUM`, `AVG`, etc.)
- Markdown code fences and other LLM formatting quirks are stripped defensively before validation

## Tech stack

**Frontend:** React, Vite, Server-Sent Events, vanilla CSS
**Backend:** FastAPI, SQLAlchemy (async), asyncpg, Anthropic SDK, sqlparse
**Database:** PostgreSQL (Supabase)
**Deployment:** Vercel (frontend), Render (backend)

## Running locally

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
```

Create `backend/.env`:
```
DATABASE_URL=postgresql://...  (Supabase session pooler connection string)
ANTHROPIC_API_KEY=sk-ant-...
```

```bash
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
```

Create `frontend/.env`:
```
VITE_API_URL=http://127.0.0.1:8000
```

```bash
npm run dev
```

## Known limitations

- Connection strings for externally connected databases are currently stored in plaintext, not encrypted at rest — fine for personal/demo use, not production-ready for handling other people's credentials
- CSV type inference handles integers, decimals, and text; it does not yet detect dates or booleans from raw CSV values
- Render's free tier spins down on inactivity, so the first request after idle time can take 30–50 seconds

## Example questions to try

- "Which team scored the most total points across all games?"
- "Show the top 5 players by height"
- "How many games has each team played?"
