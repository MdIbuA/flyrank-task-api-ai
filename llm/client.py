"""The only file that talks to the LLM provider.

Provider = three env vars (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL), so moving
between OpenRouter, Ollama or any OpenAI-compatible API is a config change.

Retries are ours, not the SDK's (max_retries=0), so the policy is visible
and testable: retry only timeouts, connection drops, 429 and 5xx, with
exponential backoff + jitter, honouring Retry-After. Never retry 4xx auth or
request errors: retrying a wrong key just burns rate limit.
"""

import os
import random
import time
from dataclasses import dataclass

import openai
from openai import OpenAI

TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
MAX_ATTEMPTS = 3  # 1 try + 2 retries; waits ~1s, ~2s
BACKOFF_BASE = 1.0


class LLMTimeout(Exception):
    """The provider didn't answer in time, even after retries."""


class LLMUnavailable(Exception):
    """The provider refused (bad key, bad request) or kept failing."""


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=TIMEOUT_SECONDS,  # SDK default is 10 minutes: never acceptable for a request handler
        max_retries=0,            # our own retry loop below
    )


def model_name() -> str:
    return os.environ["LLM_MODEL"]


def _reasoning_args() -> dict:
    # Reasoning models (qwen3, deepseek-r1...) "think" for hundreds of tokens before
    # answering. A one-label job doesn't need that: LLM_REASONING_EFFORT=none turns it
    # off on providers that support the field (Ollama, OpenAI). Unset = provider default.
    effort = os.getenv("LLM_REASONING_EFFORT", "").strip()
    return {"reasoning_effort": effort} if effort else {}


def _retry_after(exc: openai.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after") if exc.response is not None else None
    try:
        return min(float(value), 20.0) if value else None
    except ValueError:
        return None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def complete(messages: list[dict], sleep=None) -> Completion:
    sleep = sleep or time.sleep  # looked up at call time, so tests can patch it
    client = _client()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=model_name(), messages=messages, temperature=0, **_reasoning_args()
            )
            usage = response.usage
            return Completion(
                text=response.choices[0].message.content or "",
                model=response.model or model_name(),
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            )
        except Exception as exc:  # noqa: BLE001 - classified right below
            if not _is_retryable(exc):
                raise LLMUnavailable(f"provider refused the request: {type(exc).__name__}") from exc
            if attempt == MAX_ATTEMPTS:
                if isinstance(exc, openai.APITimeoutError):
                    raise LLMTimeout(f"no answer within {TIMEOUT_SECONDS:.0f}s after {attempt} attempts") from exc
                raise LLMUnavailable(f"provider kept failing: {type(exc).__name__}") from exc
            wait = None
            if isinstance(exc, openai.APIStatusError):
                wait = _retry_after(exc)
            if wait is None:
                wait = BACKOFF_BASE * 2 ** (attempt - 1) + random.uniform(0, 0.5)  # 1s, 2s (+ jitter)
            sleep(wait)
    raise AssertionError("unreachable")
