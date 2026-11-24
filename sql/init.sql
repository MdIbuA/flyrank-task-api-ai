-- Schema for the Task API on PostgreSQL.
-- Docker runs this once, when the database volume is first created
-- (docker-entrypoint-initdb.d). The app also runs it on startup; every
-- statement is safe to repeat.

CREATE TABLE IF NOT EXISTS tasks (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title      TEXT        NOT NULL CHECK (length(btrim(title)) > 0),
    done       BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Example tasks, only when the table is empty.
INSERT INTO tasks (title, done)
SELECT title, done
FROM (VALUES
    ('Read the FastAPI first-steps guide', TRUE),
    ('Build the read endpoints',           FALSE),
    ('Push the repo to GitHub',            FALSE)
) AS seed(title, done)
WHERE NOT EXISTS (SELECT 1 FROM tasks);
