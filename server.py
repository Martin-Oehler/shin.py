"""FastAPI daemon: owns the agent loop and the memory; everything else is a
thin HTTP client.

One concept: a single worker task consumes a queue, so runs are strictly
serialized with zero locking code. Every memory event is broadcast to all
connected SSE clients as it happens.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import agent
from memory import WINDOW_SIZE, Memory

memory = Memory()
runs: asyncio.Queue  # of (text, source, future); created in lifespan, because
# an asyncio.Queue binds to the event loop it is first awaited on
subscribers: list[asyncio.Queue] = []  # one event queue per SSE client


def broadcast(event):
    for q in subscribers:
        q.put_nowait(event)


async def worker():
    loop = asyncio.get_running_loop()
    # agent.run blocks (LLM request, subprocess), so it runs in a thread and
    # emits events back into the loop; SSE stays live during a run.
    emit = lambda event: loop.call_soon_threadsafe(broadcast, event)
    while True:
        text, source, future = await runs.get()
        try:
            answer = await asyncio.to_thread(agent.run, text, source, memory, emit)
            future.set_result(answer)
        except Exception as e:
            future.set_exception(e)


@asynccontextmanager
async def lifespan(app):
    global runs
    runs = asyncio.Queue()
    task = asyncio.create_task(worker())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


class Message(BaseModel):
    text: str
    source: str = "cli"


@app.post("/message")
async def message(msg: Message):
    future = asyncio.get_running_loop().create_future()
    await runs.put((msg.text, msg.source, future))
    return {"answer": await future}  # blocks until the run completes


@app.get("/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()

    async def stream():
        subscribers.append(q)
        try:
            # replay the current window so a fresh client sees history
            for event in memory.events()[-WINDOW_SIZE:]:
                yield f"data: {json.dumps(event)}\n\n"
            while True:
                yield f"data: {json.dumps(await q.get())}\n\n"
        finally:
            subscribers.remove(q)

    return StreamingResponse(stream(), media_type="text/event-stream")
