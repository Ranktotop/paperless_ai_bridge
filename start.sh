#!/bin/sh
# Start the AI-Bridge API server.
# Forwards SIGTERM/SIGINT to the child process so Docker shutdown is clean.

mkdir -p /app/logs

uvicorn server.api_server:app \
    --host 0.0.0.0 \
    --port 8080 \
    --log-level info &
API_PID=$!

trap "kill $API_PID 2>/dev/null" TERM INT

wait $API_PID
