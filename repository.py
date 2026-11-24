"""All SQL lives here. Routes call these methods and never see a query.

Swapping SQLite for another database later means writing another class with
the same methods; main.py does not change.
"""

import sqlite3

import db


def _to_task(row: sqlite3.Row) -> dict:
    task = dict(row)
    task["done"] = bool(task["done"])  # SQLite stores booleans as 0/1
    return task


class SqliteTaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_all(self, done: bool | None = None, search: str | None = None) -> list[dict]:
        sql = "SELECT * FROM tasks"
        clauses, params = [], []
        if done is not None:
            clauses.append("done = ?")
            params.append(int(done))
        if search:
            clauses.append("title LIKE ? ESCAPE '\\'")
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        return [_to_task(r) for r in self.conn.execute(sql, params)]

    def get(self, task_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _to_task(row) if row else None

    def create(self, title: str) -> dict:
        cur = self.conn.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
        self.conn.commit()
        return self.get(cur.lastrowid)
