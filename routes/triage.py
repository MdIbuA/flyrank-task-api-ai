"""POST /tasks/triage: one messy note in, one validated label out."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from llm.client import LLMTimeout, LLMUnavailable
from llm.schema import TriageRequest, TriageResult
from llm.triage import TriageDisabled, TriageFailed, triage

router = APIRouter(tags=["ai"])


class ErrorMessage(BaseModel):
    error: str


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


@router.post(
    "/tasks/triage",
    response_model=TriageResult,
    responses={
        400: {"model": ErrorMessage, "description": "Invalid input (no model call was made)"},
        422: {"model": ErrorMessage, "description": "Model output failed validation twice"},
        502: {"model": ErrorMessage, "description": "LLM provider refused or kept failing"},
        503: {"model": ErrorMessage, "description": "AI triage switched off (LLM_ENABLED=false)"},
        504: {"model": ErrorMessage, "description": "LLM provider timed out"},
    },
    summary="Turn a messy note into a clean title, category and priority",
)
def triage_note(body: TriageRequest):
    try:
        return triage(body.text)
    except TriageDisabled:
        return _error(503, "AI triage is switched off")
    except TriageFailed:
        return _error(422, "The model's answer didn't match the required shape; it has been logged for review")
    except LLMTimeout:
        return _error(504, "The AI provider took too long to answer")
    except LLMUnavailable:
        return _error(502, "The AI provider is unavailable right now")
