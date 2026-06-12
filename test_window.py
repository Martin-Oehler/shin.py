"""Slice 2 test gate: window() trims to the last N events without orphaning
a tool_result from its tool_call. Uses a throwaway history file."""

import json

from memory import WINDOW_SIZE, Memory

m = Memory(path="/tmp/test_history.jsonl")

# 30 user/assistant filler pairs (60 events), with a tool_call/tool_result
# pair placed so the WINDOW_SIZE cut lands between them: the cut keeps the
# last 50 of 62 events, so put the pair at positions 11/12 (0-indexed)
# -> the tool_call falls outside the window, the tool_result inside.
for i in range(5):
    m.append({"source": "cli", "type": "user", "content": f"filler question {i}"})
    m.append({"source": "cli", "type": "assistant", "content": f"filler answer {i}"})
m.append({"source": "cli", "type": "tool_call", "content": {
    "role": "assistant", "content": "",
    "tool_calls": [{"id": "t1", "type": "function",
                    "function": {"name": "run_bash", "arguments": "{\"command\": \"true\"}"}}]}})
m.append({"source": "cli", "type": "tool_result", "content": {
    "role": "tool", "tool_call_id": "t1", "content": "[exit code: 0]"}})
for i in range(5, 30):
    m.append({"source": "cli", "type": "user", "content": f"filler question {i}"})
    m.append({"source": "cli", "type": "assistant", "content": f"filler answer {i}"})

total = len(m.events())
window = m.window()
assert total == 62, total
assert len(window) <= WINDOW_SIZE, len(window)
# the raw cut would start with the orphaned tool_result; it must be dropped
assert window[0]["role"] != "tool", window[0]
assert not any(msg["role"] == "tool" and i == 0 for i, msg in enumerate(window))
# the surviving window must contain no tool message whose call is missing
call_ids = {tc["id"] for msg in window if msg.get("tool_calls") for tc in msg["tool_calls"]}
orphans = [msg for msg in window if msg["role"] == "tool" and msg["tool_call_id"] not in call_ids]
assert not orphans, orphans
print(f"OK: {total} events total, window={len(window)} messages, "
      f"first role={window[0]['role']}, no orphaned tool_result")
print(json.dumps(window[0]))
