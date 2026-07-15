from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .cloud_store import JsonStateStore, append_run, now_utc_iso
from .models import JobPosting, ScoreBreakdown
from .profile_loader import load_profile
from .tracking import build_sheet_row_map, build_tracking_row
from .tracking_sync import sync_tracking_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit queued Handshake jobs using a local signed-in browser profile.")
    parser.add_argument("--profile", default="profile.json", help="Path to the candidate profile JSON file.")
    parser.add_argument("--state", default="data/state.json", help="Path to the local state JSON file.")
    parser.add_argument("--limit", type=int, default=15, help="Maximum queued Handshake jobs to attempt in one run.")
    parser.add_argument(
        "--user-data-dir",
        default="data/handshake_browser_profile",
        help="Persistent browser profile directory for the local Handshake session.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the local Chromium session headlessly after you have already logged in once.",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    profile = load_profile(base_dir / args.profile)
    state_store = JsonStateStore(base_dir / args.state)
    state = state_store.load()

    queued_jobs = [
        stored
        for stored in state.jobs
        if stored.status == "queued" and stored.application_method == "internal"
    ][: max(0, args.limit)]

    if not queued_jobs:
        print(json.dumps({"queued_jobs": 0, "attempted_jobs": 0, "message": "No queued internal Handshake jobs found."}, indent=2))
        return

    results = run_local_handshake_submit(
        base_dir=base_dir,
        jobs=[stored_job_to_payload(job) for job in queued_jobs],
        user_data_dir=base_dir / args.user_data_dir,
        headless=args.headless,
    )

    processed_rows = []
    submitted_count = 0
    for result in results:
        stored = next((item for item in state.jobs if item.id == result["job_id"]), None)
        if stored is None:
            continue

        if result["status"] == "submitted" and result.get("submitted", False):
            stored.status = str(profile.constraints.get("applied_status_value", "applied"))
            submitted_count += 1
            applied = True
            applied_on = date.today()
            status_override = None
        elif result["status"] in {"login_required", "submit_uncertain", "apply_button_not_found", "submit_button_not_found"}:
            stored.status = "queued"
            applied = False
            applied_on = None
            status_override = "queued"
        else:
            stored.status = "Checkin/Review"
            applied = False
            applied_on = None
            status_override = "Checkin/Review"

        stored.updated_at = now_utc_iso()
        score = ScoreBreakdown(score=stored.score, decision=stored.decision)
        tracking_row = build_tracking_row(
            profile,
            stored_job_to_posting(stored),
            score,
            applied=applied,
            applied_on=applied_on,
            status_override=status_override,
        )
        processed_rows.append(
            {
                "job": asdict(stored),
                "decision": stored.decision,
                "score": stored.score,
                "sheet_row": build_sheet_row_map(tracking_row),
                "submission_attempt": result,
            }
        )

    run = append_run(
        state,
        jobs_seen=len(queued_jobs),
        jobs_written=len(processed_rows),
        notes=["Local Handshake submit runner executed against queued internal jobs."],
    )
    state_store.save(state)

    payload = {
        "jobs_seen": len(queued_jobs),
        "jobs_written": len(processed_rows),
        "run": asdict(run),
        "summary": {
            "submitted_count": submitted_count,
            "attempted_count": len(results),
            "queued_remaining_count": sum(1 for item in state.jobs if item.status == "queued"),
        },
        "results": processed_rows,
    }
    payload["tracking_sync"] = sync_tracking_rows(payload)
    print(json.dumps(payload, indent=2))


def stored_job_to_posting(stored) -> JobPosting:
    return JobPosting(
        id=stored.id,
        title=stored.title,
        company=stored.company,
        location=stored.location,
        url=stored.url,
        description=stored.description,
        source=stored.source,
        application_method=stored.application_method,
        application_url=stored.application_url,
        requires_cover_letter=stored.requires_cover_letter,
        requires_transcript=stored.requires_transcript,
        requires_resume=stored.requires_resume,
    )


def stored_job_to_payload(stored) -> dict:
    return {
        "id": stored.id,
        "title": stored.title,
        "company": stored.company,
        "location": stored.location,
        "url": stored.url,
    }


def detect_node_executable() -> Path:
    configured = os.getenv("JOB_AGENT_NODE_PATH", "").strip()
    if configured:
        return Path(configured)

    node_on_path = shutil.which("node")
    if node_on_path:
        return Path(node_on_path)

    home = Path.home()
    candidates = [
        home / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
        home / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("Could not find Node.js. Set JOB_AGENT_NODE_PATH to the bundled Codex node executable.")


def detect_node_modules(node_executable: Path) -> Path | None:
    configured = os.getenv("JOB_AGENT_NODE_MODULES_PATH", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return configured_path

    candidates = [
        node_executable.parent.parent / "node_modules",
        node_executable.parent.parent.parent / "node_modules",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_local_handshake_submit(*, base_dir: Path, jobs: list[dict], user_data_dir: Path, headless: bool) -> list[dict]:
    node_executable = detect_node_executable()
    node_modules = detect_node_modules(node_executable)
    submit_script = base_dir / "browser" / "handshake_submit.js"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        jobs_path = temp_path / "queued_jobs.json"
        output_path = temp_path / "submit_results.json"
        jobs_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

        env = os.environ.copy()
        if node_modules:
            env["NODE_PATH"] = str(node_modules)

        command = [
            str(node_executable),
            str(submit_script),
            "--jobs",
            str(jobs_path),
            "--out",
            str(output_path),
            "--user-data-dir",
            str(user_data_dir),
            "--headless",
            "true" if headless else "false",
        ]
        completed = subprocess.run(
            command,
            cwd=str(base_dir),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Local submit runner failed.")

        return json.loads(output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
