"""Tests for server.py, run inside the container:

    docker compose run --rm shin python3 -m pytest -q

agent.run is replaced by a fake so no LLM is needed; the slice's end-to-end
gate against a live model is run manually per the plan.
"""

import asyncio
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import server
from memory import Memory


@pytest.fixture
def fake_runs(monkeypatch, tmp_path):
    """Patch memory to a temp file and agent.run to a fake that logs
    (text, start, end) and echoes; return the log."""
    log = []
    monkeypatch.setattr(server, "memory", Memory(path=tmp_path / "history.jsonl"))

    def fake_run(text, source, memory, emit):
        start = time.monotonic()
        emit(memory.append({"source": source, "type": "user", "content": text}))
        time.sleep(0.2)
        answer = f"echo: {text}"
        emit(memory.append({"source": source, "type": "assistant", "content": answer}))
        log.append((text, start, time.monotonic()))
        return answer

    monkeypatch.setattr(server.agent, "run", fake_run)
    return log


@pytest.fixture
def client(fake_runs):
    with TestClient(server.app) as client:
        yield client


def test_message_blocks_until_run_completes(client):
    resp = client.post("/message", json={"text": "hello", "source": "cli"})
    assert resp.status_code == 200
    assert resp.json() == {"answer": "echo: hello"}
    assert [e["type"] for e in server.memory.events()] == ["user", "assistant"]


def test_concurrent_messages_are_serialized(client, fake_runs):
    def post(text):
        client.post("/message", json={"text": text, "source": "trigger"})

    threads = [threading.Thread(target=post, args=(t,)) for t in ("one", "two")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(fake_runs) == 2
    first, second = sorted(fake_runs, key=lambda r: r[1])
    assert second[1] >= first[2], "runs overlapped instead of serializing"


def test_index_serves_chat_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "EventSource" in resp.text  # the page is a live /events client


def test_events_replays_history_on_connect(client):
    """Consume the SSE generator directly: TestClient cannot close a
    never-ending stream (it waits for the generator to finish), and the
    live HTTP stream is covered by the slice gate's curl check."""
    client.post("/message", json={"text": "hi", "source": "cli"})

    async def first_two_messages():
        stream = (await server.events()).body_iterator
        messages = [await anext(stream), await anext(stream)]
        await stream.aclose()
        return messages

    replayed = [json.loads(m.removeprefix("data: ").strip())
                for m in asyncio.run(first_two_messages())]
    assert [e["type"] for e in replayed] == ["user", "assistant"]
    assert replayed[0]["content"] == "hi"
    assert replayed[1]["content"] == "echo: hi"
    assert server.subscribers == []  # aclose() must unsubscribe
