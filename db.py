"""SQLite setup: where the database lives, and how it is created on first run."""

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("TASKS_DB", Path(__file__).parent / "tasks.db"))

SEED_TITLES = [
    ("Read the FastAPI first-steps guide", True),
    ("Build the read endpoints", False),
    ("Push the repo to GitHub", False),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    done       BOOLEAN NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["title"]
    return conn


def seed(conn: sqlite3.Connection) -> None:
    conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", SEED_TITLES)


def init_db(path: Path | str = DB_PATH) -> None:
    """Create the file and table if missing; insert example tasks only when empty."""
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        (count,) = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
        if count == 0:
            seed(conn)
    conn.close()
