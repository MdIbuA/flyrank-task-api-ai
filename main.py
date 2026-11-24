"""Task API: a small in-memory CRUD API built with FastAPI."""

import copy
from contextlib import asynccontextmanager

from collections.abc import Iterator

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictBool, StrictStr, field_validator, model_validator

import db
from repository import SqliteTaskRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # creates tasks.db + table on first run, seeds only if empty
    yield

app = FastAPI(
    title="Task API",
    version="1.0",
    description=(
        "A to-do list API with full CRUD on an in-memory list. "
        "Data is lost when the server restarts; that is intentional for this stage."
    ),
    lifespan=lifespan,
)

# In-memory "database": lives only as long as the process does.
SEED_TASKS = [
    {"id": 1, "title": "Read the FastAPI first-steps guide", "done": True},
    {"id": 2, "title": "Build the read endpoints", "done": False},
    {"id": 3, "title": "Push the repo to GitHub", "done": False},
]
tasks: list[dict] = copy.deepcopy(SEED_TASKS)
next_id = len(SEED_TASKS) + 1


def get_repo() -> Iterator[SqliteTaskRepository]:
    # One short-lived connection per request: SQLite connections are cheap
    # and this keeps FastAPI's worker threads from sharing one.
    conn = db.connect()
    try:
        yield SqliteTaskRepository(conn)
    finally:
        conn.close()


# ---------- Schemas ----------

def clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("title must not be empty")
    return value


class Task(BaseModel):
    id: int
    title: str
    done: bool
    created_at: str | None = None
    updated_at: str | None = None


class TaskCreate(BaseModel):
    title: StrictStr

    model_config = {"json_schema_extra": {"examples": [{"title": "Buy milk"}]}}

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        return clean_title(value)


class TaskUpdate(BaseModel):
    title: StrictStr | None = None
    done: StrictBool | None = None

    model_config = {"json_schema_extra": {"examples": [{"title": "Buy oat milk", "done": True}]}}

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else clean_title(value)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.title is None and self.done is None:
            raise ValueError("send at least one of: title, done")
        return self


class ErrorMessage(BaseModel):
    error: str


NOT_FOUND = {404: {"model": ErrorMessage, "description": "No task with that id"}}
BAD_REQUEST = {400: {"model": ErrorMessage, "description": "Invalid request body or id"}}


# ---------- Helpers ----------

def error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


def find_task(task_id: int) -> dict | None:
    return next((t for t in tasks if t["id"] == task_id), None)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # FastAPI answers bad input with 422 by default; this API uses 400 Bad Request
    # and a single readable message instead of Pydantic's error list.
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    message = first["msg"].removeprefix("Value error, ")
    return error(400, f"{field}: {message}" if field else message)


# ---------- Routes ----------

@app.get("/", tags=["meta"], summary="Describe this API")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks", "/stats", "/reset"]}


@app.get("/health", tags=["meta"], summary="Liveness check")
def health():
    return {"status": "ok"}


@app.get(
    "/tasks",
    response_model=list[Task],
    tags=["tasks"],
    summary="List tasks, optionally filtered by done and/or a title search",
)
def list_tasks(
    done: bool | None = Query(None, description="Only finished (true) or open (false) tasks"),
    search: str | None = Query(None, description="Case-insensitive substring of the title"),
    repo: SqliteTaskRepository = Depends(get_repo),
):
    return repo.list_all(done=done, search=search)


@app.get("/stats", tags=["extras"], summary="Count total, done and open tasks")
def stats():
    done_count = sum(1 for t in tasks if t["done"])
    return {"total": len(tasks), "done": done_count, "open": len(tasks) - done_count}


@app.post("/reset", response_model=list[Task], tags=["extras"], summary="Restore the 3 example tasks")
def reset():
    global tasks, next_id
    tasks = copy.deepcopy(SEED_TASKS)
    next_id = len(SEED_TASKS) + 1
    return tasks


@app.get(
    "/tasks/{task_id}",
    response_model=Task,
    responses={**NOT_FOUND, **BAD_REQUEST},
    tags=["tasks"],
    summary="Get one task by id",
)
def get_task(task_id: int, repo: SqliteTaskRepository = Depends(get_repo)):
    task = repo.get(task_id)
    if task is None:
        return error(404, f"Task {task_id} not found")
    return task


@app.post(
    "/tasks",
    status_code=201,
    response_model=Task,
    responses=BAD_REQUEST,
    tags=["tasks"],
    summary="Create a task",
)
def create_task(payload: TaskCreate):
    global next_id
    task = {"id": next_id, "title": payload.title, "done": False}
    next_id += 1
    tasks.append(task)
    return task


@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    responses={**NOT_FOUND, **BAD_REQUEST},
    tags=["tasks"],
    summary="Update a task's title and/or done flag",
)
def update_task(task_id: int, payload: TaskUpdate):
    task = find_task(task_id)
    if task is None:
        return error(404, f"Task {task_id} not found")
    if payload.title is not None:
        task["title"] = payload.title
    if payload.done is not None:
        task["done"] = payload.done
    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    responses={**NOT_FOUND, **BAD_REQUEST},
    tags=["tasks"],
    summary="Delete a task",
)
def delete_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return error(404, f"Task {task_id} not found")
    tasks.remove(task)
    return Response(status_code=204)
