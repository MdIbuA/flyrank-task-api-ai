"""Triage logic. Stage 1: stub only, no model yet."""

import os

from llm.schema import STUB_RESULT, TriageResult


class TriageFailed(Exception):
    """The model's output never matched the schema."""


class TriageDisabled(Exception):
    """Kill switch is on."""


def triage(text: str) -> TriageResult:
    if os.getenv("LLM_STUB", "0").strip().lower() in ("1", "true", "yes", "on"):
        return STUB_RESULT
    raise NotImplementedError("model call arrives in Stage 2; run with LLM_STUB=1")
