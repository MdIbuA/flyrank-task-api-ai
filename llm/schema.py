"""What goes in and what must come out. Defined before any model is called."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

Category = Literal["study", "work", "errand", "health", "finance", "personal", "other"]
Priority = Literal["high", "medium", "low"]


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "examples": [{"text": "urgent!! submit DBMS assignment b4 friday 11:59pm"}]})

    text: StrictStr = Field(max_length=1000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be empty")
        return value


class TriageResult(BaseModel):
    """The only shape the endpoint ever returns on success."""

    model_config = ConfigDict(extra="forbid")  # an extra field from the model is a failure

    title: StrictStr = Field(min_length=3, max_length=80)
    category: Category
    priority: Priority
    confidence: float = Field(ge=0, le=1)


# Returned in stub mode (LLM_STUB=1): schema-valid, no model call.
STUB_RESULT = TriageResult(title="Stub: triage not run", category="other", priority="low", confidence=0.0)
