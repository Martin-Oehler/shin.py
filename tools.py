"""The agent's single tool: run a bash command inside the container."""

import subprocess

TIMEOUT_SECONDS = 30
MAX_OUTPUT_CHARS = 10_000  # protect the context window from huge outputs


def run_bash(command: str) -> str:
    try:
        proc = subprocess.run(
            ["bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"[command timed out after {TIMEOUT_SECONDS}s]"
    output = proc.stdout + proc.stderr
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "\n[output truncated]"
    return f"{output}\n[exit code: {proc.returncode}]"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": (
                "Run a bash command inside the container. Returns combined "
                f"stdout and stderr plus the exit code. Commands are killed "
                f"after {TIMEOUT_SECONDS} seconds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute.",
                    }
                },
                "required": ["command"],
            },
        },
    }
]
