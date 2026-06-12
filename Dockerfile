# The container IS the safety boundary: the agent has an unrestricted bash
# tool, so agent code only ever runs inside this image, never on the host.
FROM ubuntu:latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip cron ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages fastapi uvicorn openai pytest

WORKDIR /app
