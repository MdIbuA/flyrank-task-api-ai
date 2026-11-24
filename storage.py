"""Picks the storage backend once, at startup.

DATABASE_URL set   -> PostgreSQL (connection pool, schema from sql/init.sql)
DATABASE_URL unset -> SQLite file (Assignment 2 behaviour, handy without Docker)

main.py only ever calls init(), close() and get_repo().
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import db
from repository import SqliteTaskRepository

SCHEMA_FILE = Path(__file__).parent / "sql" / "init.sql"

_pool = None  # psycopg_pool.ConnectionPool when using Postgres


class TaskRepository(Protocol):
    def list_all(self, done: bool | None = None, search: str | None = None) -> list[dict]: ...
    def get(self, task_id: int) -> dict | None: ...
    def create(self, title: str) -> dict: ...
    def update(self, task_id: int, title: str | None = None, done: bool | None = None) -> dict | None: ...
    def delete(self, task_id: int) -> bool: ...
    def stats(self) -> dict: ...
    def reset(self) -> list[dict]: ...


def database_url() -> str | None:
    return os.getenv("DATABASE_URL") or None


def init() -> None:
    global _pool
    url = database_url()
    if not url:
        db.init_db()
        return

    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    _pool = ConnectionPool(url, kwargs={"row_factory": dict_row}, min_size=1, max_size=10, open=True)
    _pool.wait(timeout=30)  # fail fast at startup if the database is unreachable
    with _pool.connection() as conn:
        conn.execute(SCHEMA_FILE.read_text())


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_repo() -> Iterator[TaskRepository]:
    """FastAPI dependency: one connection per request, returned afterwards."""
    if _pool is not None:
        from repository_postgres import PostgresTaskRepository

        with _pool.connection() as conn:
            yield PostgresTaskRepository(conn)
    else:
        conn = db.connect()
        try:
            yield SqliteTaskRepository(conn)
        finally:
            conn.close()
