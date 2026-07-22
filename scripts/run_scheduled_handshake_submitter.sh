#!/bin/zsh
set -eu

SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
PYTHON_EXE="$REPO_DIR/.venv/bin/python"
SUBMIT_LIMIT="${1:-25}"
LOG_DIR="$REPO_DIR/data/logs"
LOCK_DIR="$REPO_DIR/data/.unattended_cycle.lock"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python virtual environment not found at $PYTHON_EXE" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another job-agent cycle is already running; skipping this trigger."
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PLAYWRIGHT_BROWSERS_PATH="$REPO_DIR/data/ms-playwright"
export JOB_AGENT_TRACKING_WEBHOOK_URL="https://script.google.com/macros/s/AKfycbzpjB_VmuIrJ5DWlB3Qru60pYsOG9Vceqq6u4zf5uBkIFRc4A5wKe7FoYykvoXrolWV/exec"

RUN_STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PATH="$LOG_DIR/submitter_cycle_$RUN_STAMP.log"

cd "$REPO_DIR"
echo "[$(date)] Starting scheduled Handshake submitter with limit $SUBMIT_LIMIT" >> "$LOG_PATH"
set +e
"$PYTHON_EXE" -m job_agent.local_submit --limit "$SUBMIT_LIMIT" >> "$LOG_PATH" 2>&1
SUBMIT_EXIT=$?
"$PYTHON_EXE" -m job_agent.sync_state_to_sheet >> "$LOG_PATH" 2>&1
SYNC_EXIT=$?
set -e

if (( SUBMIT_EXIT != 0 )); then
  EXIT_CODE=$SUBMIT_EXIT
else
  EXIT_CODE=$SYNC_EXIT
fi
echo "[$(date)] Finished scheduled Handshake submitter: submit=$SUBMIT_EXIT sync=$SYNC_EXIT exit=$EXIT_CODE" >> "$LOG_PATH"
exit "$EXIT_CODE"
