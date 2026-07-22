#!/bin/zsh
set -eu

SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
PYTHON_EXE="$REPO_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "Python virtual environment not found at $PYTHON_EXE" >&2
  exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PLAYWRIGHT_BROWSERS_PATH="$REPO_DIR/data/ms-playwright"
cd "$REPO_DIR"
echo "Opening the persistent Handshake browser profile for sign-in..."
exec "$PYTHON_EXE" -m job_agent.local_submit --login-only --limit 1 "$@"
