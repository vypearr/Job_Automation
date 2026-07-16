from __future__ import annotations

import json
import os
from pathlib import Path

from .cloud_service import CloudAutomationService
from .ingest import load_jobs
from .tracking_sync import sync_tracking_rows


def enrich_summary_with_sheet_target(result: dict, target_min: int, target_max: int) -> None:
    summary = dict(result.get("summary", {}))
    tracking_sync = dict(result.get("tracking_sync", {}))
    appended = int(tracking_sync.get("appended", 0) or 0)
    updated = int(tracking_sync.get("updated", 0) or 0)

    summary["daily_sheet_target_min"] = target_min
    summary["daily_sheet_target_max"] = target_max
    summary["new_sheet_rows_appended"] = appended
    summary["existing_sheet_rows_updated"] = updated
    summary["sheet_target_gap"] = max(0, target_min - appended)
    result["summary"] = summary


def resolve_jobs_files(base_dir: Path) -> list[Path]:
    configured = os.getenv("JOB_AGENT_JOBS_FILE", "").strip()
    if configured:
        return [Path(configured)]

    candidates = [
        base_dir / "data" / "handshake_enriched_jobs.json",
        base_dir / "data" / "handshake_live_jobs.json",
        base_dir / "data" / "handshake_targeted_jobs.json",
        base_dir / "handshake_selected_job_sample.json",
    ]
    existing = [candidate for candidate in candidates if candidate.exists()]
    return existing or [base_dir / "handshake_selected_job_sample.json"]


def merge_jobs_from_files(job_files: list[Path]):
    merged: dict[str, object] = {}
    for job_file in job_files:
        for job in load_jobs(job_file):
            existing = merged.get(job.id)
            if existing is None or should_replace_job(existing, job):
                merged[job.id] = job
    return list(merged.values())


def should_replace_job(existing, candidate) -> bool:
    if existing.application_method == "unknown" and candidate.application_method != "unknown":
        return True
    if candidate.requires_cover_letter and not existing.requires_cover_letter:
        return True
    if candidate.requires_transcript and not existing.requires_transcript:
        return True
    if len(candidate.description) > len(existing.description) and (
        candidate.application_method == existing.application_method
    ):
        return True
    return False


def main() -> None:
    base_dir = Path(__file__).resolve().parent.parent
    jobs_files = resolve_jobs_files(base_dir)
    jobs = merge_jobs_from_files(jobs_files)
    mark_applied = os.getenv("JOB_AGENT_MARK_APPLIED", "false").lower() == "true"
    execute_submissions = os.getenv("JOB_AGENT_EXECUTE_SUBMISSIONS", "false").lower() == "true"

    service = CloudAutomationService(base_dir)
    result = service.process_jobs(
        jobs,
        mark_applied=mark_applied,
        execute_submissions=execute_submissions,
    )
    result["jobs_file"] = str(jobs_files[0])
    result["jobs_files"] = [str(job_file) for job_file in jobs_files]
    result["merged_jobs_count"] = len(jobs)
    result["tracking_sync"] = sync_tracking_rows(result)
    target_min = int(service.load_profile().constraints.get("daily_application_target_min", 0) or 0)
    target_max = int(service.load_profile().constraints.get("daily_application_target_max", target_min) or target_min)
    enrich_summary_with_sheet_target(result, target_min, target_max)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
