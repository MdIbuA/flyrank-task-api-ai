"""Triage logic. Stage 2: real model call with a versioned prompt."""

import json
import os
from pathlib import Path

from llm import client
from llm.schema import STUB_RESULT, TriageResult

ROOT = Path(__file__).resolve().parent.parent
PROMPT_VERSION = "triage-v1"
PROMPT_FILE = ROOT / "prompts" / f"{PROMPT_VERSION}.md"


class TriageFailed(Exception):
    """The model's output never matched the schema."""


class TriageDisabled(Exception):
    """Kill switch is on."""


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def user_message(text: str) -> dict:
    # The note goes in its own user message, JSON-encoded, never pasted into the
    # system prompt: it may contain instructions we must not follow.
    return {"role": "user", "content": json.dumps({"note": text}, ensure_ascii=False)}


def triage(text: str) -> TriageResult:
    if os.getenv("LLM_STUB", "0").strip().lower() in ("1", "true", "yes", "on"):
        return STUB_RESULT
    reply = client.complete([{"role": "system", "content": system_prompt()}, user_message(text)])
    return TriageResult.model_validate_json(reply.text)  # Stage 3 makes this robust
