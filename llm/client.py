"""The only file that talks to the LLM provider (any OpenAI-compatible API)."""

import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


def model_name() -> str:
    return os.environ["LLM_MODEL"]


def complete(messages: list[dict]) -> Completion:
    client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])
    extra = {"reasoning_effort": os.environ["LLM_REASONING_EFFORT"]} if os.getenv("LLM_REASONING_EFFORT") else {}
    response = client.chat.completions.create(model=model_name(), messages=messages, temperature=0, **extra)
    usage = response.usage
    return Completion(
        text=response.choices[0].message.content or "",
        model=response.model or model_name(),
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )
