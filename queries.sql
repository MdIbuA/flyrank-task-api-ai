-- Stage 4: run these against tasks.db (DB Browser for SQLite, or `sqlite3 tasks.db`).
-- The last two change data. Call GET /stats or GET /tasks afterwards to watch the API follow.

-- List every task
SELECT * FROM tasks;

-- Show only completed tasks
SELECT * FROM tasks WHERE done = 1;

-- Count all tasks
SELECT COUNT(*) FROM tasks;

-- Mark every task as completed
UPDATE tasks SET done = 1;

-- Delete all completed tasks
DELETE FROM tasks WHERE done = 1;
