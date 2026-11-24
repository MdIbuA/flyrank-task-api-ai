"""Run every case in evals/cases.json through the real triage pipeline.

Usage (from the repo root, with .env pointing at a model):
    python -m evals.run

A case passes when category and priority both match the hand label, and,
for cases with max_confidence, the model's confidence is at or below it.
"""

import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from llm import client  # noqa: E402  (after load_dotenv on purpose)
from llm.triage import PROMPT_VERSION, TriageFailed, triage  # noqa: E402

CASES = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))


def main() -> int:
    passed, failures = 0, []
    for case in CASES:
        try:
            result = triage(case["text"])
            got = {"category": result.category, "priority": result.priority}
            ok = got == case["expect"]
            if ok and "max_confidence" in case:
                ok = result.confidence <= case["max_confidence"]
            detail = f"{got} conf={result.confidence:.2f} title={result.title!r}"
        except (TriageFailed, client.LLMTimeout, client.LLMUnavailable) as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {case['id']:<22} {detail}")
        if not ok:
            failures.append(case["id"])
    print(f"\n{passed}/{len(CASES)} matched | prompt {PROMPT_VERSION} | model {client.model_name()} | {date.today()}")
    if failures:
        print("failures:", ", ".join(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())
