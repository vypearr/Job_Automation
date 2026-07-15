from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cloud_service import CloudAutomationService
from .daily_run import merge_jobs_from_files, resolve_jobs_files
from .local_submit import process_local_queue
from .sync_state_to_sheet import sync_state_to_sheet
from .tracking_sync import sync_tracking_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local daily cycle: intake/score queue, local Handshake submit pass, and full sheet resync."
    )
    parser.add_argument("--submit-limit", type=int, default=25, help="Maximum queued Handshake jobs to attempt locally.")
    parser.add_argument(
        "--user-data-dir",
        default="data/handshake_browser_profile",
        help="Persistent browser profile directory for the local Handshake session.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the local Handshake submit pass headlessly after the browser profile is already signed in.",
    )
    parser.add_argument("--profile", default="profile.json", help="Path to the candidate profile JSON file.")
    parser.add_argument("--state", default="data/state.json", help="Path to the local state JSON file.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent

    jobs_files = resolve_jobs_files(base_dir)
    jobs = merge_jobs_from_files(jobs_files)
    service = CloudAutomationService(base_dir)
    intake_result = service.process_jobs(jobs, mark_applied=False, execute_submissions=False)
    intake_result["jobs_file"] = str(jobs_files[0]) if jobs_files else ""
    intake_result["jobs_files"] = [str(job_file) for job_file in jobs_files]
    intake_result["merged_jobs_count"] = len(jobs)
    intake_result["tracking_sync"] = sync_tracking_rows(intake_result)

    submit_result = process_local_queue(
        base_dir=base_dir,
        profile_path=args.profile,
        state_path=args.state,
        limit=args.submit_limit,
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        login_only=False,
    )

    final_sync_result = sync_state_to_sheet(
        base_dir=base_dir,
        profile_path=args.profile,
        state_path=args.state,
    )

    summary = {
        "intake": {
            "jobs_seen": intake_result.get("jobs_seen", 0),
            "jobs_written": intake_result.get("jobs_written", 0),
            "summary": intake_result.get("summary", {}),
            "tracking_sync": intake_result.get("tracking_sync", {}),
        },
        "local_submit": {
            "jobs_seen": submit_result.get("jobs_seen", 0),
            "jobs_written": submit_result.get("jobs_written", 0),
            "summary": submit_result.get("summary", {}),
            "tracking_sync": submit_result.get("tracking_sync", {}),
        },
        "final_sync": {
            "jobs_seen": final_sync_result.get("jobs_seen", 0),
            "jobs_written": final_sync_result.get("jobs_written", 0),
            "summary": final_sync_result.get("summary", {}),
            "tracking_sync": final_sync_result.get("tracking_sync", {}),
        },
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
