#!/bin/sh
# vibe-watcher.sh — Vibe Coding 自动落盘守护进程
#
# 用途：在 Vibe Coding 期间作为后台进程运行，定时将变更 commit 并 push 到远端。
#       完全独立于 Agent，不对外暴露任何工具接口。
#
# 用法：
#   scripts/vibe-watcher.sh start [--interval 300] [--branch-prefix agent/vibe]
#   scripts/vibe-watcher.sh               # 在非 vibe 分支时默认等价于 start
#   scripts/vibe-watcher.sh stop
#   scripts/vibe-watcher.sh status
#   scripts/vibe-watcher.sh finish         # 停止监控并生成合并建议

set -eu

# ============================================================
# 常量与默认值
# ============================================================
# 获取项目标识（基于 git 仓库路径的 hash）
PROJECT_ID=""
get_project_id() {
  if [ -z "$PROJECT_ID" ]; then
    local git_dir
    git_dir="$(git rev-parse --git-dir 2>/dev/null || echo "default")"
    PROJECT_ID="$(printf '%s' "$git_dir" | md5sum | cut -c1-8)"
  fi
  printf '%s' "$PROJECT_ID"
}

PID_FILE="/tmp/vibe-watcher.$(get_project_id).pid"
LOG_FILE="${VIBE_WATCHER_LOG:-$(git rev-parse --show-toplevel 2>/dev/null || echo ".")/logs/vibe-watcher.log}"
INTERVAL="${VIBE_WATCHER_INTERVAL:-300}"        # 默认每 300 秒检查一次
BRANCH_PREFIX="${VIBE_WATCHER_PREFIX:-agent/vibe}"
COMMIT_MSG_PREFIX="vibe-checkpoint"

# 临时文件路径（基于项目）
ORIGIN_BRANCH_FILE="/tmp/vibe-watcher.$(get_project_id).origin-branch"
VIBE_BRANCH_FILE="/tmp/vibe-watcher.$(get_project_id).vibe-branch"

# ============================================================
# 颜色输出（仅终端模式）
# ============================================================
if [ -t 1 ]; then
  RED=$(printf '\033[0;31m')
  GREEN=$(printf '\033[0;32m')
  YELLOW=$(printf '\033[1;33m')
  CYAN=$(printf '\033[0;36m')
  NC=$(printf '\033[0m')
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; NC=''
fi

log_time() {
  date '+%Y-%m-%d %H:%M:%S'
}

log()     { printf '%s [%s[vibe-watcher]%s] %s\n' "$(log_time)" "$CYAN"   "$NC" "$*" | tee -a "$LOG_FILE"; }
log_ok()  { printf '%s [%s[vibe-watcher]%s] %s\n' "$(log_time)" "$GREEN"  "$NC" "$*" | tee -a "$LOG_FILE"; }
log_warn(){ printf '%s [%s[vibe-watcher]%s] %s\n' "$(log_time)" "$YELLOW" "$NC" "$*" | tee -a "$LOG_FILE"; }
log_err() { printf '%s [%s[vibe-watcher]%s] %s\n' "$(log_time)" "$RED"    "$NC" "$*" | tee -a "$LOG_FILE"; }

# ============================================================
# 辅助函数
# ============================================================
ensure_log_dir() {
  mkdir -p "$(dirname "$LOG_FILE")"
}

current_branch() {
  git rev-parse --abbrev-ref HEAD 2>/dev/null
}

has_changes() {
  ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]
}

# 检测 VS Code 或 Copilot 相关进程是否还存活
vscode_alive() {
  # 匹配各种 IDE 进程
  pgrep -f "Visual Studio Code|code-insiders|com.microsoft.VSCode" > /dev/null 2>&1 || \
  pgrep -f "Cursor" > /dev/null 2>&1 || \
  pgrep -f "vscode-server" > /dev/null 2>&1 || \
  pgrep -f "Claude|claude" > /dev/null 2>&1 || \
  pgrep -f "Copilot|copilot" > /dev/null 2>&1
}

do_checkpoint() {
  branch="$(current_branch)"
  ts="$(date '+%Y-%m-%d %H:%M:%S')"

  if has_changes; then
    git add --all
    if git commit -m "${COMMIT_MSG_PREFIX}: ${ts}" --no-verify --quiet; then
      log_ok "committed checkpoint at ${ts} on branch [${branch}]"
    else
      log_err "commit failed at ${ts}"
      return 1
    fi

    # push — 失败不退出，仅记录
    if git push origin HEAD --quiet 2>>"$LOG_FILE"; then
      log_ok "pushed to origin/${branch}"
    else
      log_warn "push failed (will retry next cycle)"
    fi
  else
    log "no changes detected at ${ts}, skipping"
  fi
}

# ============================================================
# START
# ============================================================
cmd_start() {
  # 解析额外参数
  FORCE_FORK=false
  while [ $# -gt 0 ]; do
    case "$1" in
      --interval|-i) INTERVAL="$2"; shift 2 ;;
      --branch-prefix|-p) BRANCH_PREFIX="$2"; shift 2 ;;
      --fork|-f) FORCE_FORK=true; shift ;;
      *) shift ;;
    esac
  done

  # 防止重复启动
  if [ -f "$PID_FILE" ]; then
    old_pid="$(cat "$PID_FILE")"
    if kill -0 "$old_pid" 2>/dev/null; then
      log_warn "vibe-watcher is already running (PID ${old_pid}). Use 'stop' first."
      exit 1
    else
      log_warn "stale PID file found, cleaning up"
      rm -f "$PID_FILE"
    fi
  fi

  ensure_log_dir

  # 确认在 git 仓库内
  if ! git rev-parse --git-dir > /dev/null 2>&1; then
    log_err "not a git repository. Aborting."
    exit 1
  fi

  origin_branch="$(current_branch)"
  vibe_branch="${BRANCH_PREFIX}-$(date '+%Y%m%d%H%M')"

  # 分支策略：保护分支自动 fork，或用户指定 --fork
  case "$origin_branch" in
    main|master|HEAD)
      log "protected branch detected ('${origin_branch}'), creating vibe branch: ${vibe_branch}"
      git checkout -b "$vibe_branch" --quiet
      log_ok "switched to branch [${vibe_branch}]"
      ;;
    *)
      if [ "$FORCE_FORK" = true ]; then
        log "--fork specified, creating vibe branch: ${vibe_branch}"
        git checkout -b "$vibe_branch" --quiet
        log_ok "switched to branch [${vibe_branch}]"
      else
        vibe_branch="$origin_branch"
        log "using current branch [${vibe_branch}]"
      fi
      ;;
  esac

  log "starting vibe-watcher (interval: ${INTERVAL}s, branch: ${vibe_branch}, log: ${LOG_FILE})"
  log "monitoring for VS Code / Cursor process..."

  # 后台运行主循环（使用子 shell，将 PID 写入文件）
  (
    # 保存初始分支信息供 finish 使用
    printf '%s\n' "$origin_branch" > "$ORIGIN_BRANCH_FILE"
    printf '%s\n' "$vibe_branch"   > "$VIBE_BRANCH_FILE"

    trap 'log "vibe-watcher loop exiting gracefully"; exit 0' TERM INT

    while true; do
      sleep "$INTERVAL"

      # 心跳检测：VS Code/Cursor 进程不在时自动退出
      if ! vscode_alive; then
        log_warn "VS Code / Cursor process not detected. Running final checkpoint and exiting..."
        do_checkpoint
        log "vibe-watcher stopped (IDE process gone)"
        rm -f "$PID_FILE"
        exit 0
      fi

      do_checkpoint
    done
  ) >> "$LOG_FILE" 2>&1 &

  bg_pid=$!
  printf '%s\n' "$bg_pid" > "$PID_FILE"
  log_ok "vibe-watcher started in background (PID ${bg_pid})"
  log_ok "  tail -f ${LOG_FILE}   — to monitor"
  log_ok "  scripts/vibe-watcher.sh stop   — to stop"
  log_ok "  scripts/vibe-watcher.sh finish — to stop and merge back"
}

# ============================================================
# STOP
# ============================================================
cmd_stop() {
  if [ ! -f "$PID_FILE" ]; then
    log_warn "vibe-watcher is not running (no PID file found)"
    exit 0
  fi

  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    log "stopping vibe-watcher (PID ${pid})..."
    kill -TERM "$pid"
    sleep 2
    # 确保进程已退出
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
    log_ok "vibe-watcher stopped"
  else
    log_warn "PID ${pid} is not running, cleaning up stale PID file"
  fi

  rm -f "$PID_FILE"
}

# ============================================================
# STATUS
# ============================================================
cmd_status() {
  if [ ! -f "$PID_FILE" ]; then
    printf '%svibe-watcher is NOT running%s\n' "$YELLOW" "$NC"
    return
  fi

  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    vibe_branch="$(cat "$VIBE_BRANCH_FILE" 2>/dev/null || printf 'unknown')"
    printf '%svibe-watcher is RUNNING%s\n' "$GREEN" "$NC"
    printf '  PID:      %s\n' "$pid"
    printf '  Branch:   %s\n' "$vibe_branch"
    printf '  Log:      %s\n' "$LOG_FILE"
    printf '  Interval: %ss\n' "$INTERVAL"
    printf '\n'
    printf 'Recent checkpoints:\n'
    git log --oneline --grep="^${COMMIT_MSG_PREFIX}" -10 2>/dev/null || true
  else
    printf '%svibe-watcher has a stale PID file (process %s not found)%s\n' "$YELLOW" "$pid" "$NC"
    rm -f "$PID_FILE"
  fi
}

# ============================================================
# FINISH — 停止监控，自动 squash-merge 回原分支
# ============================================================
cmd_finish() {
  local auto_merge=false
  local origin_branch_arg=""
  local commit_args_provided=false

  # 解析参数（使用 '--' 分隔后续传递给 git commit 的参数；
  # 遇到未识别的参数时也视为 git commit 参数的开始，例如 finish -a -m "msg"）
  while [ $# -gt 0 ]; do
    case "$1" in
      --auto-merge|-a) auto_merge=true; shift ;;
      --origin|-o)
        origin_branch_arg="$2"
        shift 2
        ;;
      --) shift; commit_args_provided=true; break ;;
      *)
        # 未识别参数视为 git commit 参数的开始，保留其及后续所有参数
        commit_args_provided=true
        break
        ;;
    esac
  done

  origin_branch=""
  vibe_branch=""
  if [ -f "$ORIGIN_BRANCH_FILE" ]; then
    origin_branch="$(cat "$ORIGIN_BRANCH_FILE")"
  fi
  if [ -f "$VIBE_BRANCH_FILE" ]; then
    vibe_branch="$(cat "$VIBE_BRANCH_FILE")"
  fi
  if [ -n "$origin_branch_arg" ]; then
    origin_branch="$origin_branch_arg"
  fi

  if [ -z "$vibe_branch" ]; then
    current="$(current_branch || printf '')"
    case "$current" in
      "${BRANCH_PREFIX}"*)
        vibe_branch="$current"
        ;;
    esac
  fi

  if [ -z "$vibe_branch" ]; then
    log_err "session state lost and no vibe branch detected."
    log_err "If you are on a vibe branch, run 'scripts/vibe-watcher.sh finish --origin <origin-branch>'"
    return 1
  fi

  if [ -z "$origin_branch" ] && [ "$auto_merge" = true ]; then
    log_err "origin branch is unknown. Provide it with --origin <branch> to auto-merge."
    return 1
  fi

  # 如果只是打印指引，不强制要求 origin_branch
  if [ -n "$origin_branch" ] && [ "$auto_merge" = true ]; then
    if ! git rev-parse --verify "$origin_branch" > /dev/null 2>&1; then
      log_err "origin branch '${origin_branch}' not found"
      return 1
    fi
  fi

  if [ -z "$vibe_branch" ]; then
    log_err "invalid session state: vibe branch is empty"
    return 1
  fi

  # 验证 vibe 分支存在
  if ! git rev-parse --verify "$vibe_branch" > /dev/null 2>&1; then
    log_err "vibe branch '${vibe_branch}' not found"
    return 1
  fi

  # 先执行最后一次 checkpoint
  # 停止后台进程（先停止再做最终 checkpoint，避免日志文件等竞态导致 checkout 失败）
  cmd_stop

  # 再执行最后一次 checkpoint，确保所有未提交的变更都被提交
  log "running final checkpoint before finish..."
  do_checkpoint || true

  # 防止后续日志写入再次修改工作区（例如本脚本打印信息会写入 LOG_FILE），
  # 在切换分支前临时将日志目标设置为 /dev/null
  LOG_FILE_SAVE="${LOG_FILE:-}" || true
  LOG_FILE="/dev/null"

  # 如果在 commit 之后仍有未提交的变更（例如日志在并发写入），
  # 将其暂时提交为一个最后的 checkpoint，避免 checkout 被阻塞。
  git add --all 2>/dev/null || true
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "${COMMIT_MSG_PREFIX}: final flush" --no-verify --quiet 2>/dev/null || true
  fi

  display_origin="${origin_branch:-<origin-branch>}"

  display_origin="${origin_branch:-<origin-branch>}"

  # 打印完成信息
  printf '\n'
  printf '%s╔══════════════════════════════════════════════════════╗%s\n' "$GREEN" "$NC"
  printf '%s║          Vibe Coding Session Complete!               ║%s\n' "$GREEN" "$NC"
  printf '%s╚══════════════════════════════════════════════════════╝%s\n' "$GREEN" "$NC"
  printf '\n'
  printf '  Vibe Branch  : %s\n' "$vibe_branch"
  printf '  Origin Branch: %s\n' "$display_origin"
  printf '\n'

  # 自动合并逻辑
  if [ "$origin_branch" != "$vibe_branch" ]; then
    if [ "$auto_merge" = true ]; then
      printf '%sAuto-merging back to %s...%s\n' "$CYAN" "$origin_branch" "$NC"

      # 执行 squash merge
      if ! git checkout "$origin_branch" --quiet; then
        log_err "failed to checkout ${origin_branch}"
        return 1
      fi

      if ! git merge --squash "$vibe_branch"; then
        log_err "merge conflict detected, please resolve manually"
        printf '\n%sConflict resolution steps:%s\n' "$YELLOW" "$NC"
        printf '  1. Resolve conflicts in your editor\n'
        printf '  2. git add <resolved-files>\n'
        printf '  3. git commit <your-args>\n'
        return 1
      fi

      # 执行 commit（透传参数，无参数时进入 editor）
          if [ "$commit_args_provided" = true ] && [ "$#" -gt 0 ]; then
            # 用户传入了 git commit 参数，直接把剩余的参数透传给 git commit
            if git commit "$@"; then
              log_ok "successfully merged and committed to ${origin_branch}"
            else
              log_err "commit failed, please check git status"
              return 1
            fi
      else
        # 无参数，进入 editor
        printf '\n%sOpening editor for commit message...%s\n' "$CYAN" "$NC"
        if git commit; then
          log_ok "successfully merged and committed to ${origin_branch}"
        else
          log_err "commit failed or aborted"
          return 1
        fi
      fi

      printf '\n%sTo clean up the vibe branch:%s\n' "$CYAN" "$NC"
      printf '  git branch -d %s\n' "$vibe_branch"
      printf '  git push origin --delete %s   # optional\n' "$vibe_branch"
    else
      # 仅打印指引
      printf '%sTo merge your work back as a single clean commit:%s\n' "$CYAN" "$NC"
      printf '\n'
      printf '  git checkout %s\n' "$display_origin"
      printf '  git merge --squash %s\n' "$vibe_branch"
      printf '  git commit  # or: git commit -m "your message"\n'
      printf '\n'
      if [ -z "$origin_branch" ]; then
        printf '%sOrigin branch unknown. Use --origin to specify it if you want auto-merge.%s\n' "$YELLOW" "$NC"
        printf '  scripts/vibe-watcher.sh finish --auto-merge --origin <origin-branch>\n'
        printf '\n'
      fi
      printf '%sOr use auto-merge:%s\n' "$CYAN" "$NC"
      printf '  scripts/vibe-watcher.sh finish --auto-merge\n'
      printf '  scripts/vibe-watcher.sh finish -a -m "feat: xxx"\n'
      printf '\n'
      printf '%sTo clean up the vibe branch after merging:%s\n' "$CYAN" "$NC"
      printf '\n'
      printf '  git branch -d %s\n' "$vibe_branch"
      printf '  git push origin --delete %s   # optional\n' "$vibe_branch"
    fi
  else
    printf '  # You are already on the working branch: %s\n' "$vibe_branch"
    printf '  # No merge needed.\n'
  fi
  printf '\n'

  rm -f "$ORIGIN_BRANCH_FILE" "$VIBE_BRANCH_FILE"
}

# ============================================================
# 命令分发
# ============================================================
COMMAND=''
if [ "$#" -gt 0 ]; then
  COMMAND="$1"
  shift || true
else
  if git rev-parse --git-dir > /dev/null 2>&1; then
    branch="$(current_branch || printf '')"
    # 检查是否正在运行
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
      # 如果正在运行，不管在哪个分支都显示 status
      COMMAND='status'
    else
      # 如果未运行，根据分支决定
      case "$branch" in
        "${BRANCH_PREFIX}"*)
          # 在 vibe 分支但未运行，显示 status
          COMMAND='status'
          ;;
        '')
          COMMAND='help'
          ;;
        *)
          # 在非 vibe 分支，启动 start
          COMMAND='start'
          ;;
      esac
    fi
  else
    COMMAND='help'
  fi
fi

case "$COMMAND" in
  start)  cmd_start "$@" ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  finish) cmd_finish "$@" ;;
  help|--help|-h)
    printf 'Usage: scripts/vibe-watcher.sh <command> [options]\n'
    printf '       scripts/vibe-watcher.sh  # auto-start on non-vibe branch\n'
    printf '\n'
    printf 'Commands:\n'
    printf '  start   [-i|--interval N] [-p|--branch-prefix PREFIX] [-f|--fork]\n'
    printf '            Start background checkpointing (default interval: 300s)\n'
    printf '            -f|--fork: force create vibe branch even on feature/dev branch\n'
    printf '  stop      Stop the background watcher\n'
    printf '  status    Show current watcher status and recent checkpoints\n'
    printf '  finish    [-a|--auto-merge] [-o|--origin ORIGIN_BRANCH] [-- | <git-commit-args>]\n'
    printf '            Final checkpoint, stop, and print merge instructions\n'
    printf '            -a|--auto-merge: automatically squash-merge back to origin branch\n'
    printf '            -o|--origin ORIGIN_BRANCH: specify origin branch when session state is lost\n'
    printf '            <git-commit-args>: pass args to git commit; use -- prefix or just write them directly\n'
    printf '              e.g. -m "msg" or -- -m "msg" (both work); opens editor if omitted\n'
    printf '\n'
    printf 'Examples:\n'
    printf '  scripts/vibe-watcher.sh start -i 60 -f\n'
    printf '  scripts/vibe-watcher.sh finish -a -m "feat: add new feature"\n'
    printf '  scripts/vibe-watcher.sh finish -a  # opens editor for commit message\n'
    printf '\n'
    printf 'Environment variables:\n'
    printf '  VIBE_WATCHER_INTERVAL=300        Override default commit interval (seconds)\n'
    printf '  VIBE_WATCHER_PREFIX=agent/vibe  Override branch name prefix\n'
    printf '  VIBE_WATCHER_LOG=<path>         Override log file path\n'
    ;;
  *)
    log_err "Unknown command: ${COMMAND}. Run with 'help' for usage."
    exit 1
    ;;
esac
