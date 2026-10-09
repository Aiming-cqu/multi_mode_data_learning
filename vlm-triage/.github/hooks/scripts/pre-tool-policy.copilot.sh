#!/bin/bash
# preToolUse policy hook — three-tier tool execution control.
#   Tier 1 "deny": permanently blocked, no execution path
#   Tier 2 "ask" : user must confirm before execution
#   Tier 3 "allow": default; secrets redacted via modifiedArgs if present
#
# Input:  {toolName, toolArgs: {command}} (camelCase) or {tool_name, tool_input: {command}} (snake_case)
# Output: {"permissionDecision":"deny|ask", "permissionDecisionReason":"..."} or {"permissionDecision":"allow", "modifiedArgs":{"command":"..."}}
# Empty stdout = clean allow (default behavior).
set -euo pipefail

INPUT="$(cat)"
TOOL_NAME="$(echo "$INPUT" | jq -r '.toolName // .tool_name // empty')"
TOOL_ARGS_RAW="$(echo "$INPUT" | jq '.toolArgs // .tool_input // empty' | jq -c . 2>/dev/null || echo "$INPUT" | jq -r '.toolArgs // .tool_input // empty')"

LOG_DIR="$HOME/.agents/hooks/logs/"
test -d "$LOG_DIR" || exit 0

# ── Redaction ────────────────────────────────────────────────────────────
redact() {
  echo "$1" | sed -E \
    -e 's/gh[psuo]_[A-Za-z0-9]{20,}/[REDACTED_TOKEN]/g' \
    -e 's/Bearer [A-Za-z0-9_\-\.]+/Bearer [REDACTED]/g' \
    -e 's/--password[= ][^ ]+/--password=[REDACTED]/g' \
    -e 's/--token[= ][^ ]+/--token=[REDACTED]/g'
}

# ── Recursive command unwrapper ──────────────────────────────────────────
# Strips one wrapper layer. Returns 0 if unwrapped, 1 if no wrapper found.
unwrap_command() {
  local cmd="$1" stripped

  # Simple wrappers: wrapper [opts] command [args...]
  for pattern in \
    'env\s+((--ignore-environment|-i)\s+)?((--unset|-u)\s+\S+\s+)*(\S+=\S+\s+)*' \
    'xargs\s+(-[a-zA-Z0-9]\S*(\s+|$))*' \
    'sudo\s+(-[a-zA-Z0-9]\S*(\s+|$))*' \
    'nice(\s+-n\s+\S+)?\s+' \
    'nohup\s+' \
    '(?:/usr/bin/)?time\s+(-[a-zA-Z]\S*(\s+|$))*' \
    'timeout\s+(-[a-zA-Z]\S*(\s+|$))*[0-9]+(\.[0-9]+)?[smhd]?(\s+|$)' \
    'watch\s+(-[a-zA-Z0-9]\S*(\s+|$))*' \
    'flock\s+(-[a-zA-Z0-9]\S*(\s+|$))*\S+\s+' \
    'chroot\s+(-[a-zA-Z0-9]\S*(\s+|$))*\S+\s+' \
    'eval\s+' \
  ; do
    stripped="$(echo "$cmd" | sed -E "s/^${pattern}//")"
    if [ "$stripped" != "$cmd" ] && [ -n "$stripped" ]; then
      echo "$stripped"; return 0
    fi
  done

  # Namespace/container escapers
  for w in nsenter unshare systemd-run pkexec doas stdbuf ionice taskset setsid; do
    stripped="$(echo "$cmd" | sed -E "s/^${w}\s+(-[a-zA-Z0-9]\S*(\s+|$))*//")"
    if [ "$stripped" != "$cmd" ] && [ -n "$stripped" ]; then
      echo "$stripped"; return 0
    fi
  done

  # parallel: parallel [opts] command
  stripped="$(echo "$cmd" | sed -E 's/^parallel\s+(-[a-zA-Z0-9]\S*(\s+|$))*//')"
  if [ "$stripped" != "$cmd" ] && [ -n "$stripped" ]; then echo "$stripped"; return 0; fi

  # bash/sh/zsh/dash/ksh -c 'command string'
  if echo "$cmd" | grep -qE '^(bash|sh|zsh|dash|ksh)\s+.*-c\s+'; then
    stripped="$(echo "$cmd" | sed -E "s/^(bash|sh|zsh|dash|ksh)\s+(-[a-zA-Z]+\s+)*\s*-c\s+//; s/^['\"]//; s/['\"]$//")"
    if [ -n "$stripped" ]; then echo "$stripped"; return 0; fi
  fi

  # su [user] -c 'command'
  if echo "$cmd" | grep -qE '^su\s+.*-c\s+'; then
    stripped="$(echo "$cmd" | sed -E "s/^su\s+(\S+\s+)?(-[a-zA-Z]+\s+)*\s*-c\s+//; s/^['\"]//; s/['\"]$//")"
    if [ -n "$stripped" ]; then echo "$stripped"; return 0; fi
  fi

  # find ... -exec command ... \; / +
  if echo "$cmd" | grep -qE '\bfind\b.*-exec\b'; then
    stripped="$(echo "$cmd" | sed -E 's/.*-exec\s+//; s/\s*(\+|\\;).*//')"
    if [ -n "$stripped" ] && [ "$stripped" != "$cmd" ]; then echo "$stripped"; return 0; fi
  fi

  return 1
}

unwrap_recursive() {
  local cmd="$1" depth=0 prev
  while [ "$depth" -lt 10 ]; do
    prev="$cmd"
    cmd="$(unwrap_command "$cmd" 2>/dev/null)" || break
    [ "$cmd" = "$prev" ] && break
    depth=$((depth + 1))
  done
  echo "$prev"
}

# ── Audit (with rotation) ────────────────────────────────────────────────
AUDIT_LOG="$LOG_DIR/audit.jsonl"
ROTATE_AT=$((2 * 1024 * 1024))
if [ -f "$AUDIT_LOG" ] && [ "$(stat -f%z "$AUDIT_LOG" 2>/dev/null || stat -c%s "$AUDIT_LOG" 2>/dev/null || echo 0)" -gt "$ROTATE_AT" ]; then
  mv "$AUDIT_LOG" "${AUDIT_LOG}.1"
fi
REDACTED_ARGS="$(redact "$TOOL_ARGS_RAW")"
jq -nc \
  --arg tool "$TOOL_NAME" \
  --arg args "$REDACTED_ARGS" \
  '{event:"preToolUse", toolName:$tool, toolArgs:$args}' \
  >> "$AUDIT_LOG"

# ── Only enforce policy on shell commands ────────────────────────────────
case "$TOOL_NAME" in bash|run_in_terminal|sh|zsh|dash|ksh|powershell|pwsh) ;; *) exit 0 ;; esac
if ! echo "$TOOL_ARGS_RAW" | jq -e . >/dev/null 2>&1; then exit 0; fi
COMMAND="$(echo "$TOOL_ARGS_RAW" | jq -r '.command // empty')"
REDACTED_CMD="$(redact "$COMMAND")"
UNWRAPPED_CMD="$(unwrap_recursive "$COMMAND")"

# ── Syntax-check / info-only bypasses ────────────────────────────────────
# These patterns never modify files or execute runtime side effects.
if echo "$COMMAND" | grep -qE '^(bash|sh|zsh|dash|ksh)\s+.*-n\b| -n\s+'; then exit 0; fi
if echo "$COMMAND" | grep -qE '\b(node\s+(-c|--check)|python[0-9]*(\.[0-9]+)?\s+-m\s+(py_compile|compileall)|ruby\s+-c|perl\s+-c|php\s+-l)\b'; then exit 0; fi
if echo "$COMMAND" | grep -qE '\b(gcc|g\+\+|clang|clang\+\+)\s+.*-fsyntax-only\b'; then exit 0; fi
if echo "$COMMAND" | grep -qE '\b(tsc\s+--noEmit|cargo\s+check|go\s+vet)\b'; then exit 0; fi
if echo "$COMMAND" | grep -qE '\bruff\s+(check|format\s+--check)\b'; then exit 0; fi
if echo "$COMMAND" | grep -qE '^(node|npm|npx|python[0-9]*(\.[0-9]+)?|go|rustc|cargo|ruby|perl|php|gcc|g\+\+|clang|clang\+\+|tsc|ruff|make|cmake|git|docker|curl|wget|bash|sh|zsh|dash|ksh|java|javac|mvn|gradle)\s+--version\s*$'; then exit 0; fi

# ── Output helpers ──────────────────────────────────────────────────────
deny() {
  jq -nc --arg tool "$TOOL_NAME" --arg cmd "$REDACTED_CMD" --arg r "$1" \
    '{event:"policyDeny", toolName:$tool, command:$cmd, reason:$r}' >> "$AUDIT_LOG"
  jq -nc --arg r "$1" '{permissionDecision:"deny", permissionDecisionReason:$r}'
  exit 0
}
ask() {
  jq -nc --arg tool "$TOOL_NAME" --arg cmd "$REDACTED_CMD" --arg r "$1" \
    '{event:"policyAsk", toolName:$tool, command:$cmd, reason:$r}' >> "$AUDIT_LOG"
  # Best-effort DChat notification
  echo "$(jq -nc --arg tool "$TOOL_NAME" --arg cmd "$REDACTED_CMD" --arg r "$1" \
    '{event:"policyAsk", toolName:$tool, command:$cmd, reason:$r}')" \
    | "$(cd "$(dirname "$0")" && pwd)/notify-dchat.sh" "policyAsk" 2>/dev/null || true
  jq -nc --arg r "$1" '{permissionDecision:"ask", permissionDecisionReason:$r}'
  exit 0
}
allow_with_redaction() {
  local reason="${1:-Secrets redacted from command}"
  local modified="$(echo "$TOOL_ARGS_RAW" | jq --arg cmd "$REDACTED_CMD" '.command = $cmd')"
  jq -nc --arg tool "$TOOL_NAME" --arg cmd "$REDACTED_CMD" --arg r "$reason" \
    '{event:"policyAllowRedacted", toolName:$tool, command:$cmd, reason:$r}' >> "$AUDIT_LOG"
  jq -nc --arg r "$reason" --argjson m "$modified" \
    '{permissionDecision:"allow", permissionDecisionReason:$r, modifiedArgs:$m}'
  exit 0
}

# ═══════════════════════════════════════════════════════════════════════
# TIER 1 — DENY
# ═══════════════════════════════════════════════════════════════════════

# Privilege escalation
if echo "$UNWRAPPED_CMD" | grep -qE '\b(su|runas)\b'; then
  deny "Privilege escalation (su/runas) is permanently blocked."
fi

# pip (blocked in all forms)
if echo "$UNWRAPPED_CMD" | grep -qE '\buv\s+pip\s+install\b'; then
  deny "uv pip install is permanently blocked. Use uv add <pkg> instead."
fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bpip([0-9]+(\.[0-9]+)?)?\s+(install|uninstall|download|wheel|hash|check|config|list|show|freeze|inspect|debug|cache|index)\b'; then
  deny "pip is permanently blocked. Use pixi add / uv add instead."
fi
if echo "$UNWRAPPED_CMD" | grep -qE 'python[0-9]*(\.[0-9]+)?\s+-m\s+pip\b'; then
  deny "pip (via python -m pip) is permanently blocked."
fi

# Destructive system ops
if echo "$UNWRAPPED_CMD" | grep -qE 'rm\s+-rf\s*/($|\s)|rm\s+.*-rf\s*/($|\s)|rm\s+.*\*\*/\*'; then
  deny "Destructive rm targeting filesystem root or recursive glob (/**/*) is permanently blocked."
fi
if echo "$UNWRAPPED_CMD" | grep -qE '\b(mkfs|format)\b'; then
  deny "System-level destructive operations (mkfs/format) are permanently blocked."
fi

# sed write/exec flags
if echo "$UNWRAPPED_CMD" | grep -qE '\bsed\b.*;W'; then ask "sed ;W (write to file) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bsed\b.*s\/.*\/.*\/[ew]'; then ask "sed s///e or s///w (execute/write) requires your confirmation. Proceed?"; fi

# ═══════════════════════════════════════════════════════════════════════
# TIER 2 — ASK
# ═══════════════════════════════════════════════════════════════════════

# Package managers
if echo "$UNWRAPPED_CMD" | grep -qE '\bpixi\s+(add|remove|exec)\b'; then ask "pixi add/remove/exec requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\b(uv\s+add|uvx)\b'; then ask "uv add / uvx requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bconda\s+(install|remove|update)\b'; then ask "conda install/remove/update requires your confirmation. Proceed?"; fi

# Runtime execution
if echo "$UNWRAPPED_CMD" | grep -qE '\bnode\b' && ! echo "$UNWRAPPED_CMD" | grep -qE '\bnode\s+(-c|--check|--version)\b'; then
  ask "node execution requires your confirmation. Proceed?"
fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bpython[0-9]*(\.[0-9]+)?\b' && ! echo "$UNWRAPPED_CMD" | grep -qE '\bpython[0-9]*(\.[0-9]+)?\s+(-m\s+(py_compile|compileall|pip)|--version)\b'; then
  ask "python execution requires your confirmation. Proceed?"
fi

# Privilege / disk / network
if echo "$UNWRAPPED_CMD" | grep -qE '\bdd\b'; then ask "dd (low-level disk copy) requires your confirmation. Proceed?"; fi
if echo "$COMMAND" | grep -qE '\bsudo\b'; then ask "sudo requires your confirmation. Proceed?"; fi

# tmux
if echo "$COMMAND" | grep -qE '\btmux\s+(send-keys|send|kill-session|kill-window|kill-pane|kill-server|new-session|new|source-file|source|run-shell|run|pipe-pane)\b'; then
  ask "tmux destructive/risky operation requires your confirmation. Proceed?"
elif echo "$UNWRAPPED_CMD" | grep -qE '\btmux\s+(send-keys|send|kill-session|kill-window|kill-pane|kill-server|new-session|new|source-file|source|run-shell|run|pipe-pane)\b'; then
  ask "tmux (via wrapper) requires your confirmation. Proceed?"
fi

# find -exec/-delete
if echo "$COMMAND" | grep -qE '\bfind\b' && echo "$COMMAND" | grep -qE -- '-(delete|exec|execdir|ok|okdir)'; then
  ask "find with -delete/-exec/-ok requires your confirmation. Proceed?"
elif echo "$UNWRAPPED_CMD" | grep -qE '\bfind\b' && echo "$UNWRAPPED_CMD" | grep -qE -- '-(delete|exec|execdir|ok|okdir)'; then
  ask "find (via wrapper) with -delete/-exec/-ok requires your confirmation. Proceed?"
fi

# Namespace/cgroup escapers
if echo "$COMMAND" | grep -qE '\b(chroot|nsenter|unshare|systemd-run|pkexec|doas)\b'; then
  ask "Namespace/container escape requires your confirmation. Proceed?"
fi

# Destructive git / misc write-to-file
if echo "$UNWRAPPED_CMD" | grep -qE '\bgit\b.*\s+branch\b.*\s-(d|D|m|M|--delete|--force)\b'; then ask "git branch -d/-D/-m/-M requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bgit\b.*\s+log\b.*\s--output(=|\s)'; then ask "git log --output (writes to file) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bdate\b.*\s(-s|--set)\b'; then ask "date -s/--set (modifies system time) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bsort\b.*\s-o\b'; then ask "sort -o (writes to file) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\btree\b.*\s-o\b'; then ask "tree -o (writes to file) requires your confirmation. Proceed?"; fi

# Network / process / docker
if echo "$UNWRAPPED_CMD" | grep -qE '\b(curl|wget)\b'; then ask "curl/wget (network request) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bkill\b'; then ask "kill (process signaling) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\brg\b.*\s(--pre|--hostname-bin)\b'; then ask "rg --pre/--hostname-bin (arbitrary code execution) requires your confirmation. Proceed?"; fi
if echo "$UNWRAPPED_CMD" | grep -qE '\bdocker\b' && ! echo "$UNWRAPPED_CMD" | grep -qE '\bdocker\s+(ps|images|info|version|inspect|logs|top|stats|port|diff|search|events|compose\s+(ps|ls|top|logs|images|config|version|port|events))\b'; then
  ask "docker non-read-only operation requires your confirmation. Proceed?"
fi

# ═══════════════════════════════════════════════════════════════════════
# TIER 3 — ALLOW (secrets redacted via modifiedArgs)
# ═══════════════════════════════════════════════════════════════════════

if [ "$COMMAND" != "$REDACTED_CMD" ]; then
  allow_with_redaction "Command allowed with secrets redacted"
fi

exit 0
