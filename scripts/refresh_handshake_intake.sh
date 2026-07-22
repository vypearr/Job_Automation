#!/bin/zsh
set -eu

SCRIPT_DIR="${0:A:h}"
REPO_DIR="${SCRIPT_DIR:h}"
PYTHON_EXE="$REPO_DIR/.venv/bin/python"
NODE_EXE="${JOB_AGENT_NODE_PATH:-/opt/homebrew/bin/node}"
PROFILE_DIR="$REPO_DIR/data/handshake_browser_profile"
TEMP_DIR="$(mktemp -d "$REPO_DIR/data/.handshake_refresh.XXXXXX")"
HEADLESS="${JOB_AGENT_HANDSHAKE_HEADLESS:-false}"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT INT TERM

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PLAYWRIGHT_BROWSERS_PATH="$REPO_DIR/data/ms-playwright"

cd "$REPO_DIR"
"$NODE_EXE" browser/handshake_refresh.js collect \
  --user-data-dir "$PROFILE_DIR" \
  --pages "${JOB_AGENT_HANDSHAKE_PAGES:-3}" \
  --per-page "${JOB_AGENT_HANDSHAKE_PER_PAGE:-25}" \
  --headless "$HEADLESS" \
  --out "$TEMP_DIR/handshake_live_jobs.json"

"$PYTHON_EXE" -m job_agent.curate_intake \
  --jobs "$TEMP_DIR/handshake_live_jobs.json" \
  --profile profile.json \
  --min-match-score "${JOB_AGENT_HANDSHAKE_MIN_MATCH_SCORE:-2}" \
  --out "$TEMP_DIR/handshake_targeted_jobs.json"

"$NODE_EXE" browser/handshake_refresh.js enrich \
  --jobs "$TEMP_DIR/handshake_targeted_jobs.json" \
  --user-data-dir "$PROFILE_DIR" \
  --limit "${JOB_AGENT_HANDSHAKE_ENRICH_LIMIT:-25}" \
  --headless "$HEADLESS" \
  --out "$TEMP_DIR/handshake_enriched_jobs.json"

mv "$TEMP_DIR/handshake_live_jobs.json" data/handshake_live_jobs.json
mv "$TEMP_DIR/handshake_targeted_jobs.json" data/handshake_targeted_jobs.json
mv "$TEMP_DIR/handshake_enriched_jobs.json" data/handshake_enriched_jobs.json
echo "Handshake live intake refresh completed successfully."
