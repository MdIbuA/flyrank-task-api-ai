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

    def update(self, task_id: int, title: str | None = None, done: bool | None = None) -> dict | None:
        sets, params = [], []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if done is not None:
            sets.append("done = ?")
            params.append(int(done))
        sets.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')")
        cur = self.conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", (*params, task_id)
        )
        self.conn.commit()
        return self.get(task_id) if cur.rowcount else None

    def delete(self, task_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict:
        total, done = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(done), 0) FROM tasks"
        ).fetchone()
        return {"total": total, "done": done, "open": total - done}

    def reset(self) -> list[dict]:
        self.conn.execute("DELETE FROM tasks")
        self.conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tasks'")  # restart ids at 1
        db.seed(self.conn)
        self.conn.commit()
        return self.list_all()
