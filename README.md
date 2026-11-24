# Task API + PostgreSQL in Docker

The Task API from [A1](https://github.com/MdIbuA/flyrank-task-api) and [A2](https://github.com/MdIbuA/flyrank-task-api-sqlite), now running on **PostgreSQL in Docker**. One command starts the app and the database together, and the data lives in a Docker volume, so it survives restarts of both.

Built for FlyRank's Backend AI Engineering track, assignment **A3: Containerize your stack** (Python: FastAPI + psycopg 3).

## Run the whole stack

Requires Docker Desktop (or Docker Engine with Compose v2).

```bash
cp .env.example .env        # then change POSTGRES_PASSWORD in .env
docker compose up --build
```

- API: <http://localhost:8000>, Swagger UI at <http://localhost:8000/docs>
- Postgres: `localhost:5432`, with the user, password and database from your `.env`

`docker compose down` stops everything and keeps the data. `docker compose down -v` also deletes the volume, which wipes the data.

## What's in the stack

| Piece | File | Notes |
|---|---|---|
| Postgres 16 | `docker-compose.yml` → `db` | Named volume `pgdata` holds the data. A healthcheck (`pg_isready`) tells Compose when it's ready. |
| Schema | `sql/init.sql` | One SQL file: the `tasks` table plus three example rows, inserted only if the table is empty. Postgres runs it the first time the volume is created, and the app runs it again on startup; every statement is safe to repeat. |
| App | `Dockerfile` + `docker-compose.yml` → `app` | `python:3.12-slim`, runs as a non-root user, starts only after the database is healthy. |
| Secrets | `.env` (gitignored), `.env.example` (committed) | The connection string is built from `.env`; nothing secret is in the repo. |

## The swap: what changed and what didn't

A2 put every SQL query behind a repository class. A3 adds a second class with the same seven methods and switches to it:

| File | Status |
|---|---|
| `repository_postgres.py` | **New.** `PostgresTaskRepository`: same methods and return shapes as the SQLite one. |
| `storage.py` | **New.** Reads `DATABASE_URL` once at startup. If it's set: open a psycopg connection pool, apply `sql/init.sql`, hand out `PostgresTaskRepository`. If not: fall back to A2's SQLite file. |
| `main.py` | **Routes unchanged.** Every route body is identical to A2. Honest list of the edits: the startup hook calls `storage.init()`/`storage.close()` instead of `db.init_db()`; `get_repo` is now imported from `storage.py` instead of defined in `main.py`; the type hint on the `repo` parameter is a `TaskRepository` protocol instead of the SQLite class; and the version string is 3.0. |
| `repository.py`, `db.py` | Unchanged from A2. |

The client-facing API is byte-for-byte the same, including error messages and timestamp format. The test suite proves it: the same 11 tests run against both backends.

```bash
pip install -r requirements-dev.txt
pytest -q                                                             # SQLite only
TEST_DATABASE_URL=postgresql://tasks:change-me@localhost:5432/tasks pytest -q   # both (wipes that database)
```

Against Postgres 16: **22 passed** (11 tests × 2 backends).

## Proving persistence

What I did, against Postgres 16:

1. Started the app with `DATABASE_URL` pointing at Postgres and created a task:
   `POST /tasks {"title": "Survive a restart"}` → `201`, id 4.
2. Stopped the app **and** restarted the Postgres server.
3. Started the app again: `GET /tasks/4` returned the same task with the same `created_at`, and `/stats` showed 4 tasks (the 3 examples weren't inserted twice).

Repeat it with Compose:

```bash
docker compose up -d --build
curl -X POST localhost:8000/tasks -H "Content-Type: application/json" -d '{"title": "Survive a restart"}'
docker compose restart          # restarts the app AND the db containers
curl localhost:8000/tasks       # still there
docker compose down && docker compose up -d   # containers deleted and recreated; volume kept
curl localhost:8000/tasks       # still there
```

## Postgres-specific details

- `id` is `GENERATED ALWAYS AS IDENTITY`: the modern replacement for `SERIAL`, and ids are never reused.
- Partial updates use `COALESCE(%s, title)`, so one `UPDATE ... RETURNING *` handles "title only", "done only" or both, without building SQL strings.
- `?search=` uses `ILIKE` with `%` and `_` escaped; `/stats` uses `COUNT(*) FILTER (WHERE done)`.
- A connection pool (`psycopg_pool`, max 10) replaces the open-a-connection-per-request approach from A2. Opening a Postgres connection is far more expensive than opening a SQLite file.
- Every query is parameterised (`%s`); user input never becomes part of the SQL text.

## Run without Docker

`uvicorn main:app --reload` still works with no `DATABASE_URL`: it uses the A2 SQLite file. Set `DATABASE_URL` to use any Postgres you already have.
