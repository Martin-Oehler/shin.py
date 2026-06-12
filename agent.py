"""The core agentic loop: LLM call → tool execution → repeat until a final answer.

Every step is emitted as an event through memory.append; the emit callback
lets callers layer visualization (stdout here, SSE broadcast in the server)
on top without the loop knowing about it.
"""

import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

from memory import Memory
from tools import TOOLS, run_bash

MAX_ITERATIONS = 20
MODEL = os.environ.get("MODEL", "google/gemma-4-e4b")

SOUL_FILE = Path(__file__).parent / "Soul.md"
SOUL = (
    SOUL_FILE.read_text()
    if SOUL_FILE.exists()
    else "You are shin, a helpful assistant running inside a Docker container. "
    "You have one tool: bash."
)

client = OpenAI(
    base_url=os.environ.get("OPENAI_BASE_URL", "http://host.docker.internal:1234/v1"),
    api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"),
)


def _split_reasoning(msg):
    """Separate reasoning from the answer, handling both LM Studio conventions:
    a reasoning_content field on the message, or inline <think>…</think>."""
    reasoning = getattr(msg, "reasoning_content", None)
    text = msg.content or ""
    if not reasoning:
        m = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
        if m:
            reasoning = m.group(1).strip()
            text = (text[: m.start()] + text[m.end() :]).strip()
    return reasoning, text


def run(user_text, source, memory, emit):
    emit(memory.append({"source": source, "type": "user", "content": user_text}))
    for _ in range(MAX_ITERATIONS):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SOUL}] + memory.window(),
            tools=TOOLS,
        )
        msg = resp.choices[0].message
        reasoning, text = _split_reasoning(msg)
        if reasoning:
            emit(memory.append({"source": source, "type": "reasoning", "content": reasoning}))
        if msg.tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": text,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            }
            emit(memory.append({"source": source, "type": "tool_call", "content": assistant_msg}))
            for tc in msg.tool_calls:
                result = run_bash(**json.loads(tc.function.arguments))
                tool_msg = {"role": "tool", "tool_call_id": tc.id, "content": result}
                emit(memory.append({"source": source, "type": "tool_result", "content": tool_msg}))
            continue
        emit(memory.append({"source": source, "type": "assistant", "content": text}))
        return text
    text = "[iteration limit reached]"
    emit(memory.append({"source": source, "type": "assistant", "content": text}))
    return text


def _print_event(event):
    t = event["type"]
    if t == "reasoning":
        print(f"\033[2m[reasoning] {event['content']}\033[0m")
    elif t == "tool_call":
        for tc in event["content"]["tool_calls"]:
            print(f"[tool_call] run_bash {tc['function']['arguments']}")
    elif t == "tool_result":
        print(f"[tool_result] {event['content']['content']}")
    elif t == "assistant":
        print(event["content"])


if __name__ == "__main__":
    run(" ".join(sys.argv[1:]), "cli", Memory(), _print_event)
