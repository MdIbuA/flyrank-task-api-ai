"""Stage 0 smoke test: can we reach the model at all? Prints one word."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"], timeout=30, max_retries=0)
reply = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    messages=[{"role": "user", "content": "Reply with exactly one word: the colour of a clear daytime sky."}],
    temperature=0,
    **({"reasoning_effort": os.environ["LLM_REASONING_EFFORT"]} if os.getenv("LLM_REASONING_EFFORT") else {}),
)
print(reply.choices[0].message.content.strip())
