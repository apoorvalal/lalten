#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-${PORT:-8501}}"
ADDRESS="${ADDRESS:-0.0.0.0}"
BASE_PATH="${BASE_PATH:-/arxiv_methods_charts}"
APP_PATH="bsky_paperbot/streamlit_app.py"

if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
  echo "Error: port must be a numeric value. Got: $PORT" >&2
  exit 1
fi

exec uv run streamlit run "$APP_PATH" \
  --server.address "$ADDRESS" \
  --server.port "$PORT" \
  --server.baseUrlPath "$BASE_PATH" \
  --server.headless true
