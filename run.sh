#!/bin/bash
# Cron wrapper for Coles price tracker. Runs daily at 16:00.

set -euo pipefail

cd "$(dirname "$0")"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p logs
LOG_FILE="logs/run-$(date +%Y-%m-%d).log"

{
  echo "=== Run started at $(date) ==="
  /opt/homebrew/bin/uv run python main.py
  echo "=== Run finished at $(date) ==="
} >>"$LOG_FILE" 2>&1
