# Stage 4: SQL session against `tasks.db`

Queries run directly on the database file while the API was running. After each write, the API is called to show it sees the change immediately.

## List every task

```sql
SELECT * FROM tasks;
```

| id | title | done | created_at | updated_at |
|---|---|---|---|---|
| 1 | Read the FastAPI first-steps guide | 1 | 2026-11-24T16:50:38Z | 2026-11-24T16:50:38Z |
| 2 | Build the read endpoints | 0 | 2026-11-24T16:50:38Z | 2026-11-24T16:50:38Z |
| 3 | Push the repo to GitHub | 0 | 2026-11-24T16:50:38Z | 2026-11-24T16:50:38Z |
| 4 | Buy milk | 1 | 2026-11-24T16:50:40Z | 2026-11-24T16:50:40Z |
| 5 | Write the SQLite README | 0 | 2026-11-24T16:50:40Z | 2026-11-24T16:50:40Z |

## Show only completed tasks

```sql
SELECT * FROM tasks WHERE done = 1;
```

| id | title | done | created_at | updated_at |
|---|---|---|---|---|
| 1 | Read the FastAPI first-steps guide | 1 | 2026-11-24T16:50:38Z | 2026-11-24T16:50:38Z |
| 4 | Buy milk | 1 | 2026-11-24T16:50:40Z | 2026-11-24T16:50:40Z |

## Count all tasks

```sql
SELECT COUNT(*) FROM tasks;
```

| COUNT(*) |
|---|
| 5 |

## Mark every task as completed

```sql
UPDATE tasks SET done = 1;
```

(5 rows changed)

API afterwards, `GET /stats`:

```json
{"total":5,"done":5,"open":0}
```

## Delete all completed tasks

```sql
DELETE FROM tasks WHERE done = 1;
```

(5 rows changed)

API afterwards, `GET /tasks`:

```json
[]
```
