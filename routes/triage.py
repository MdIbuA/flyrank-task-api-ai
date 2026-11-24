"""POST /tasks/triage: one messy note in, one validated label out."""

from fastapi import APIRouter

from llm.schema import TriageRequest, TriageResult
from llm.triage import triage

router = APIRouter(tags=["ai"])


@router.post("/tasks/triage", response_model=TriageResult, summary="Turn a messy note into a clean title, category and priority")
def triage_note(body: TriageRequest):
    return triage(body.text)
