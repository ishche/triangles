#!/usr/bin/env bash
# Run the API (auto-restarts on Python changes) and the Vite dev server (hot reload) together.
# Open http://localhost:5173. Ctrl-C stops both.
#   API_PORT=8001 WEB_PORT=5174 ./dev.sh
set -euo pipefail
cd "$(dirname "$0")"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

command -v uv >/dev/null || { echo "uv not found: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm not found: install Node.js 20+" >&2; exit 1; }

uv sync --quiet
if [ ! -d web/node_modules ] || [ web/package.json -nt web/node_modules ]; then
  npm --prefix web install
fi

trap 'trap - EXIT; kill 0' INT TERM EXIT

uv run watchfiles --filter python "python -m domeprint.server --port $API_PORT" src &
api=$!
DOMEPRINT_API="http://127.0.0.1:$API_PORT" npm --prefix web run dev -- --port "$WEB_PORT" --strictPort &
web=$!

# Stop everything as soon as either process exits (macOS bash 3.2 has no `wait -n`).
while kill -0 "$api" 2>/dev/null && kill -0 "$web" 2>/dev/null; do sleep 1; done
