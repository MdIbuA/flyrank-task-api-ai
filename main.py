"""Task API: the same CRUD API as Assignment 1, now backed by PostgreSQL (or SQLite)."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictBool, StrictStr, field_validator, model_validator

import storage
from storage import TaskRepository, get_repo


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init()  # Postgres if DATABASE_URL is set, else SQLite; creates the table if missing
    yield
    storage.close()


app = FastAPI(
    title="Task API",
    version="3.0",
    description="A to-do list API with full CRUD. Tasks are stored in PostgreSQL (SQLite when DATABASE_URL is unset) and survive restarts.",
    lifespan=lifespan,
)


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
    created_at: str
    updated_at: str


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


# ---------- Errors ----------

def error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


def not_found(task_id: int) -> JSONResponse:
    return error(404, f"Task {task_id} not found")


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
    return {"name": "Task API", "version": "3.0", "endpoints": ["/tasks", "/stats", "/reset"]}


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
    repo: TaskRepository = Depends(get_repo),
):
    return repo.list_all(done=done, search=search)


@app.get(
    "/tasks/{task_id}",
    response_model=Task,
    responses={**NOT_FOUND, **BAD_REQUEST},
    tags=["tasks"],
    summary="Get one task by id",
)
def get_task(task_id: int, repo: TaskRepository = Depends(get_repo)):
    task = repo.get(task_id)
    return task if task else not_found(task_id)


@app.post(
    "/tasks",
    status_code=201,
    response_model=Task,
    responses=BAD_REQUEST,
    tags=["tasks"],
    summary="Create a task",
)
def create_task(payload: TaskCreate, repo: TaskRepository = Depends(get_repo)):
    return repo.create(payload.title)


@app.put(
    "/tasks/{task_id}",
    response_model=Task,
    responses={**NOT_FOUND, **BAD_REQUEST},
    tags=["tasks"],
    summary="Update a task's title and/or done flag",
)
def update_task(task_id: int, payload: TaskUpdate, repo: TaskRepository = Depends(get_repo)):
    task = repo.update(task_id, title=payload.title, done=payload.done)
    return task if task else not_found(task_id)


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    responses={**NOT_FOUND, **BAD_REQUEST},
    tags=["tasks"],
    summary="Delete a task",
)
def delete_task(task_id: int, repo: TaskRepository = Depends(get_repo)):
    if not repo.delete(task_id):
        return not_found(task_id)
    return Response(status_code=204)


@app.get("/stats", tags=["extras"], summary="Count total, done and open tasks with SQL COUNT()")
def stats(repo: TaskRepository = Depends(get_repo)):
    return repo.stats()


@app.post("/reset", response_model=list[Task], tags=["extras"], summary="Delete everything and restore the 3 example tasks")
def reset(repo: TaskRepository = Depends(get_repo)):
    return repo.reset()
