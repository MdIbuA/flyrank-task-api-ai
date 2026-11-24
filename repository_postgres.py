"""PostgreSQL implementation of the task repository.

Same methods, same inputs, same return shapes as SqliteTaskRepository in
repository.py, so routes in main.py work with either one unchanged.
"""

from datetime import timezone

import psycopg

import db

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def _to_task(row: dict) -> dict:
    task = dict(row)
    for key in ("created_at", "updated_at"):
        task[key] = task[key].astimezone(timezone.utc).strftime(_ISO)
    return task


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PostgresTaskRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn  # opened with row_factory=dict_row

    def list_all(self, done: bool | None = None, search: str | None = None) -> list[dict]:
        sql = "SELECT * FROM tasks"
        clauses, params = [], []
        if done is not None:
            clauses.append("done = %s")
            params.append(done)
        if search:
            clauses.append("title ILIKE %s")  # ILIKE: case-insensitive; backslash is the default escape
            params.append(f"%{_escape_like(search)}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        return [_to_task(r) for r in self.conn.execute(sql, params).fetchall()]

    def get(self, task_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
        return _to_task(row) if row else None

    def create(self, title: str) -> dict:
        row = self.conn.execute(
            "INSERT INTO tasks (title) VALUES (%s) RETURNING *", (title,)
        ).fetchone()
        self.conn.commit()
        return _to_task(row)

    def update(self, task_id: int, title: str | None = None, done: bool | None = None) -> dict | None:
        # COALESCE keeps the current value when a field wasn't sent.
        row = self.conn.execute(
            """
            UPDATE tasks
               SET title = COALESCE(%s, title),
                   done = COALESCE(%s, done),
                   updated_at = now()
             WHERE id = %s
            RETURNING *
            """,
            (title, done, task_id),
        ).fetchone()
        self.conn.commit()
        return _to_task(row) if row else None

    def delete(self, task_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE done) AS done FROM tasks"
        ).fetchone()
        return {"total": row["total"], "done": row["done"], "open": row["total"] - row["done"]}

    def reset(self) -> list[dict]:
        self.conn.execute("TRUNCATE tasks RESTART IDENTITY")
        with self.conn.cursor() as cur:
            cur.executemany("INSERT INTO tasks (title, done) VALUES (%s, %s)", db.SEED_TITLES)
        self.conn.commit()
        return self.list_all()
