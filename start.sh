#!/bin/bash
# cron gives the agent its hook mechanism (self-registered jobs that call
# cli.py -p); uvicorn is the daemon everything talks to.
cron
exec uvicorn server:app --host 0.0.0.0 --port 8000
