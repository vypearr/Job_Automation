from __future__ import annotations

import json
import os
from pathlib import Path

from .cloud_service import CloudAutomationService
from .tracking_sync import sync_tracking_rows


def resolve_jobs_file(base_dir: Path) -> Path:
    configured = os.getenv("JOB_AGENT_JOBS_FILE", "").strip()
    if configured:
        return Path(configured)

    candidates = [
        base_dir / "data" / "handshake_enriched_jobs.json",
        base_dir / "data" / "handshake_targeted_jobs.json",
        base_dir / "data" / "handshake_live_jobs.json",
        base_dir / "handshake_selected_job_sample.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return base_dir / "handshake_selected_job_sample.json"


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    jobs_file = resolve_jobs_file(base_dir)
    mark_applied = os.getenv("JOB_AGENT_MARK_APPLIED", "false").lower() == "true"
    execute_submissions = os.getenv("JOB_AGENT_EXECUTE_SUBMISSIONS", "false").lower() == "true"

    service = CloudAutomationService(base_dir)
    result = service.process_jobs_file(
        jobs_file,
        mark_applied=mark_applied,
        execute_submissions=execute_submissions,
    )
    result["jobs_file"] = str(jobs_file)
    result["tracking_sync"] = sync_tracking_rows(result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
