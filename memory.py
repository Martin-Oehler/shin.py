"""Event log as single source of truth.

Everything that happens is an event appended to state/history.jsonl:
    {ts, source, type, content}
type ∈ {user, reasoning, tool_call, tool_result, assistant}
source ∈ {web, cli, trigger}

The file is the memory: the rolling LLM context is rebuilt from its tail,
so persistence across processes and restarts falls out for free.
"""

import json
import time
from pathlib import Path

WINDOW_SIZE = 50  # events; the rolling short-term memory
HISTORY_FILE = Path(__file__).parent / "state" / "history.jsonl"


class Memory:
    def __init__(self, path=HISTORY_FILE):
        self.path = Path(path)
        self.path.parent.mkdir(exist_ok=True)

    def append(self, event: dict) -> dict:
        event = {"ts": time.time(), **event}
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")
        return event

    def events(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def window(self, n=WINDOW_SIZE) -> list[dict]:
        """Rebuild the LLM message list from the last n events.

        reasoning events are visualization-only and skipped. tool_call and
        tool_result events hold OpenAI message dicts verbatim and are
        replayed as-is. The cut must not orphan a tool_result from its
        tool_call, so leading tool_results are dropped.
        """
        events = [e for e in self.events()[-n:] if e["type"] != "reasoning"]
        while events and events[0]["type"] == "tool_result":
            events.pop(0)
        messages = []
        for e in events:
            if e["type"] in ("tool_call", "tool_result"):
                messages.append(e["content"])
            else:  # user / assistant: content is plain text, type is the role
                messages.append({"role": e["type"], "content": e["content"]})
        return messages
