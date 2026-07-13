from __future__ import annotations

import json
import os
from pathlib import Path

from .cloud_service import CloudAutomationService
from .tracking_sync import sync_tracking_rows


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    jobs_file = os.getenv("JOB_AGENT_JOBS_FILE", str(base_dir / "handshake_selected_job_sample.json"))
    mark_applied = os.getenv("JOB_AGENT_MARK_APPLIED", "false").lower() == "true"

    service = CloudAutomationService(base_dir)
    result = service.process_jobs_file(jobs_file, mark_applied=mark_applied)
    result["tracking_sync"] = sync_tracking_rows(result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
