#!/bin/bash
set -euo pipefail

INPUT="$(cat)"

TIMESTAMP_MS="$(echo "$INPUT" | jq -r '.timestamp // empty')"
CWD="$(echo "$INPUT" | jq -r '.cwd // empty')"

LOG_DIR="$HOME/.agents/hooks/logs/"
test -d "$LOG_DIR" || exit 0

# Rotate at 2 MiB
AUDIT_LOG="$LOG_DIR/audit.jsonl"
ROTATE_AT=$((2 * 1024 * 1024))
if [ -f "$AUDIT_LOG" ] && [ "$(stat -f%z "$AUDIT_LOG" 2>/dev/null || stat -c%s "$AUDIT_LOG" 2>/dev/null || echo 0)" -gt "$ROTATE_AT" ]; then
  mv "$AUDIT_LOG" "${AUDIT_LOG}.1"
fi

jq -nc \
  --arg ts "$TIMESTAMP_MS" \
  --arg cwd "$CWD" \
  '{event:"userPromptSubmitted", timestampMs:$ts, cwd:$cwd}' \
  >> "$AUDIT_LOG"

exit 0
