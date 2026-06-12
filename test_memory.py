"""Tests for memory.py, run inside the container:

    docker compose run --rm shin python3 -m pytest -q
"""

import pytest

from memory import WINDOW_SIZE, Memory


def tool_call_event(call_id):
    return {"source": "cli", "type": "tool_call", "content": {
        "role": "assistant", "content": "",
        "tool_calls": [{"id": call_id, "type": "function",
                        "function": {"name": "run_bash",
                                     "arguments": '{"command": "true"}'}}]}}


def tool_result_event(call_id):
    return {"source": "cli", "type": "tool_result", "content": {
        "role": "tool", "tool_call_id": call_id, "content": "[exit code: 0]"}}


@pytest.fixture
def memory(tmp_path):
    return Memory(path=tmp_path / "history.jsonl")


def test_append_and_events_roundtrip(memory):
    memory.append({"source": "cli", "type": "user", "content": "hi"})
    memory.append({"source": "cli", "type": "assistant", "content": "hello"})
    events = memory.events()
    assert [e["type"] for e in events] == ["user", "assistant"]
    assert all("ts" in e for e in events)


def test_window_maps_types_to_roles_and_skips_reasoning(memory):
    memory.append({"source": "cli", "type": "user", "content": "q"})
    memory.append({"source": "cli", "type": "reasoning", "content": "hmm"})
    memory.append({"source": "cli", "type": "assistant", "content": "a"})
    assert memory.window() == [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]


@pytest.fixture
def overfull_memory(memory):
    """62 events with a tool_call/tool_result pair placed so the
    WINDOW_SIZE=50 cut lands between them: the tool_call falls outside
    the window, its tool_result inside."""
    for i in range(5):
        memory.append({"source": "cli", "type": "user", "content": f"q{i}"})
        memory.append({"source": "cli", "type": "assistant", "content": f"a{i}"})
    memory.append(tool_call_event("t1"))
    memory.append(tool_result_event("t1"))
    for i in range(5, 30):
        memory.append({"source": "cli", "type": "user", "content": f"q{i}"})
        memory.append({"source": "cli", "type": "assistant", "content": f"a{i}"})
    assert len(memory.events()) == 62
    return memory


def test_window_caps_at_window_size(overfull_memory):
    assert len(overfull_memory.window()) <= WINDOW_SIZE


def test_window_drops_orphaned_tool_result(overfull_memory):
    window = overfull_memory.window()
    call_ids = {tc["id"] for msg in window if msg.get("tool_calls")
                for tc in msg["tool_calls"]}
    orphans = [msg for msg in window
               if msg["role"] == "tool" and msg["tool_call_id"] not in call_ids]
    assert orphans == []


def test_window_keeps_complete_tool_pairs(memory):
    memory.append({"source": "cli", "type": "user", "content": "q"})
    memory.append(tool_call_event("t1"))
    memory.append(tool_result_event("t1"))
    memory.append({"source": "cli", "type": "assistant", "content": "a"})
    roles = [m["role"] for m in memory.window()]
    assert roles == ["user", "assistant", "tool", "assistant"]
