# shin.py

> **shin** (芯) — *core*. A minimalistic agent, reduced to its essential core.

No framework, no plugins, no abstraction layers. One LLM loop, one tool (bash), one event log as memory — about 300 lines of Python across five files, each small enough to read over coffee.

## Why

Most agent frameworks bury the loop under layers of indirection. shin.py is the opposite: the entire mechanism is on the surface.

- **One tool** — bash inside a Docker container. The container *is* the safety boundary.
- **One memory** — an append-only `history.jsonl` event log; the LLM context is rebuilt from its tail, so persistence across restarts falls out for free.
- **One daemon** — a FastAPI server owns the loop; web UI, CLI, and cron triggers are all thin HTTP clients.
- **Any OpenAI-compatible backend** — runs against LM Studio out of the box, or point it at any other endpoint.

## Quick start

You need Docker and an OpenAI-compatible LLM endpoint (by default: [LM Studio](https://lmstudio.ai) on the host, port 1234).

```sh
docker compose up
```

Then open the live web UI at **http://localhost:8000** — or talk to it from the terminal:

```sh
python cli.py                      # interactive REPL
python cli.py -p "what time is it" # one-shot (this is what cron calls)
```

To use a different backend or model:

```sh
OPENAI_BASE_URL=https://api.example.com/v1 OPENAI_API_KEY=... MODEL=... docker compose up
```

## How it works

| File | Lines | What it does |
|---|---|---|
| `agent.py` | ~75 | The loop: LLM call → tool execution → repeat until a final answer |
| `memory.py` | ~55 | Event log as single source of truth; rolling context window from its tail |
| `tools.py` | ~50 | The single tool: run a bash command, capped output, 30 s timeout |
| `server.py` | ~90 | FastAPI daemon: serialized run queue, SSE broadcast of every event |
| `cli.py` | ~40 | Thin HTTP client — no agent logic at all |

Every step (user message, reasoning, tool call, tool result, answer) is an event. Events are appended to the log and streamed live to the browser. That's the whole system.

Drop a `Soul.md` next to `agent.py` to give the agent a custom system prompt.

## License

[MIT](LICENSE)
