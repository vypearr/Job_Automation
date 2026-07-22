#!/bin/zsh
set -eu

SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
PYTHON_EXE="$REPO_DIR/.venv/bin/python"
LOG_DIR="$REPO_DIR/data/logs"
LOCK_DIR="$REPO_DIR/data/.unattended_cycle.lock"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python virtual environment not found at $PYTHON_EXE" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another unattended cycle is already running; skipping this trigger."
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PLAYWRIGHT_BROWSERS_PATH="$REPO_DIR/data/ms-playwright"
export JOB_AGENT_TRACKING_WEBHOOK_URL="https://script.google.com/macros/s/AKfycbzpjB_VmuIrJ5DWlB3Qru60pYsOG9Vceqq6u4zf5uBkIFRc4A5wKe7FoYykvoXrolWV/exec"
export JOB_AGENT_JOBS_FILE="$REPO_DIR/data/handshake_enriched_jobs.json"
export JOB_AGENT_EXTRA_JOBS_FILES="$REPO_DIR/data/handshake_targeted_jobs.json,$REPO_DIR/data/linkedin_live_jobs.json"

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PATH="$LOG_DIR/finder_cycle_$RUN_STAMP.log"

cd "$REPO_DIR"
echo "[$(date)] Starting scheduled Handshake finder cycle" >> "$LOG_PATH"
echo "[$(date)] Refreshing live Handshake intake" >> "$LOG_PATH"
if "$REPO_DIR/scripts/refresh_handshake_intake.sh" >> "$LOG_PATH" 2>&1; then
  echo "[$(date)] Live Handshake intake refresh succeeded" >> "$LOG_PATH"
else
  echo "[$(date)] WARNING: Live Handshake intake refresh failed; continuing with the last valid intake files" >> "$LOG_PATH"
fi
set +e
"$PYTHON_EXE" -m job_agent.daily_run >> "$LOG_PATH" 2>&1
EXIT_CODE=$?
set -e
echo "[$(date)] Finished scheduled Handshake finder cycle with exit code $EXIT_CODE" >> "$LOG_PATH"
exit "$EXIT_CODE"
