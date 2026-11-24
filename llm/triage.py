"""Turn a note into a TriageResult the rest of the code can trust.

call model -> parse JSON -> validate against the schema
  -> if invalid: repair once (send the broken output + exact error back)
  -> if still invalid: quarantine the evidence and raise TriageFailed (422)

Raw model text never leaves this module.
"""

import json
import logging
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from llm import client
from llm.schema import STUB_RESULT, TriageResult

ROOT = Path(__file__).resolve().parent.parent
PROMPT_VERSION = "triage-v2"
PROMPT_FILE = ROOT / "prompts" / f"{PROMPT_VERSION}.md"
LOG_DIR = Path(os.getenv("LLM_LOG_DIR", ROOT / "logs"))

log = logging.getLogger("uvicorn.error")


class TriageFailed(Exception):
    """The model's output never matched the schema, even after one repair."""


class TriageDisabled(Exception):
    """Kill switch is on: LLM_ENABLED=false."""


def _flag(name: str, default: str) -> str:
    return os.getenv(name, default).strip().lower()


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


def user_message(text: str, today: date | None = None) -> dict:
    # The note goes in its own user message, JSON-encoded, never pasted into the
    # system prompt: it may contain instructions we must not follow.
    # v2: today's date is included, or "on 3rd dec" can't be ranked against "tomorrow".
    today = today or date.today()
    return {"role": "user", "content": json.dumps(
        {"note": text, "today": today.strftime("%Y-%m-%d (%A)")}, ensure_ascii=False)}


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_and_validate(raw: str) -> TriageResult:
    """Strip fences/preamble, take the JSON object, validate. Raises ValueError with the reason."""
    text = _FENCE.sub("", raw.strip())
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # reasoning models
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in the reply")
    try:
        return TriageResult.model_validate_json(text[start : end + 1])
    except ValidationError as exc:
        raise ValueError(_short_errors(exc)) from None


def _short_errors(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"]) or "object"
        parts.append(f"{where}: {err['msg']}")
    return "; ".join(parts)


def _append_jsonl(name: str, record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / name, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def triage(text: str) -> TriageResult:
    if _flag("LLM_ENABLED", "true") in ("false", "0", "no", "off"):
        raise TriageDisabled()
    if _flag("LLM_STUB", "0") in ("1", "true", "yes", "on"):
        return STUB_RESULT

    messages = [{"role": "system", "content": system_prompt()}, user_message(text)]
    started = time.perf_counter()
    tokens_in = tokens_out = repairs = 0
    model = client.model_name()
    outcome = "ok"
    try:
        reply = client.complete(messages)
        tokens_in, tokens_out, model = reply.input_tokens, reply.output_tokens, reply.model
        try:
            return parse_and_validate(reply.text)
        except ValueError as first_error:
            repairs = 1
            repair_messages = messages + [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": (
                    f"Your reply was rejected: {first_error}. "
                    "Reply again with only the corrected JSON object, using only the allowed values."
                )},
            ]
            fixed = client.complete(repair_messages)
            tokens_in += fixed.input_tokens
            tokens_out += fixed.output_tokens
            try:
                return parse_and_validate(fixed.text)
            except ValueError as second_error:
                outcome = "quarantined"
                _append_jsonl("quarantine.jsonl", {
                    "ts": _now(), "prompt_version": PROMPT_VERSION, "model": model, "input": text,
                    "first_output": reply.text, "first_error": str(first_error),
                    "repair_output": fixed.text, "repair_error": str(second_error),
                })
                raise TriageFailed(str(second_error)) from None
    except (client.LLMTimeout, client.LLMUnavailable) as exc:
        outcome = type(exc).__name__
        raise
    finally:
        record = {
            "ts": _now(), "prompt_version": PROMPT_VERSION, "model": model,
            "input_tokens": tokens_in, "output_tokens": tokens_out,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "repairs": repairs, "outcome": outcome,
        }
        _append_jsonl("llm-calls.jsonl", record)
        log.info("llm_call %s", json.dumps(record))
