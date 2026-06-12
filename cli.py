"""Thin HTTP client for the shin daemon: no agent logic at all.

Interactive REPL by default; `cli.py -p "<task>"` posts one prompt with
source="trigger" and exits — this is what cron jobs call.
"""

import argparse
import json
import os
import urllib.request

SHIN_URL = os.environ.get("SHIN_URL", "http://localhost:8000")


def post(text: str, source: str) -> str:
    req = urllib.request.Request(
        f"{SHIN_URL}/message",
        data=json.dumps({"text": text, "source": source}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["answer"]


def main():
    parser = argparse.ArgumentParser(description="Thin client for the shin daemon.")
    parser.add_argument("-p", "--prompt", help="one-shot: send prompt, print answer, exit")
    args = parser.parse_args()
    if args.prompt:
        print(post(args.prompt, "trigger"))
        return
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line.strip():
            print(post(line, "cli"))


if __name__ == "__main__":
    main()
