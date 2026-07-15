from __future__ import annotations

import os
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .apply_pipeline import GenericHostedAdapter, HandshakeAdapter, IndeedAdapter, LinkedInAdapter
from .cloud_store import JsonStateStore, append_run, upsert_job
from .ingest import load_jobs
from .models import CandidateProfile, JobPosting
from .platforms import select_adapter_for_job
from .profile_loader import load_profile
from .scoring import score_job
from .submission import GenericSubmissionExecutor, HandshakeSubmissionExecutor
from .tracking import build_sheet_row_map, build_tracking_row


class CloudAutomationService:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        profile_path = os.getenv("JOB_AGENT_PROFILE_PATH")
        state_path = os.getenv("JOB_AGENT_STATE_PATH")
        self.profile_path = Path(profile_path) if profile_path else self.base_dir / "profile.json"
        self.state_store = JsonStateStore(Path(state_path) if state_path else self.base_dir / "data" / "state.json")
        self.adapters = {
            "handshake": HandshakeAdapter(),
            "linkedin": LinkedInAdapter(),
            "indeed": IndeedAdapter(),
            "generic_hosted": GenericHostedAdapter(),
        }
        self.executors = {
            "handshake": HandshakeSubmissionExecutor(),
            "linkedin": GenericSubmissionExecutor(),
            "indeed": GenericSubmissionExecutor(),
            "generic_hosted": GenericSubmissionExecutor(),
        }

    def load_profile(self) -> CandidateProfile:
        return load_profile(self.profile_path)

    def list_jobs(self) -> list[dict]:
        state = self.state_store.load()
        return [asdict(job) for job in state.jobs]

    def list_runs(self) -> list[dict]:
        state = self.state_store.load()
        return [asdict(run) for run in state.runs]

    def process_jobs(
        self,
        jobs: list[JobPosting],
        *,
        mark_applied: bool = False,
        execute_submissions: bool = False,
    ) -> dict:
        profile = self.load_profile()
        state = self.state_store.load()
        processed: list[dict] = []

        for job in jobs:
            score = score_job(job, profile)
            adapter = select_adapter_for_job(job, self.adapters)
            application_plan = adapter.create_application_plan(profile, job, score)
            executor = select_adapter_for_job(job, self.executors)
            existing = next((item for item in state.jobs if item.id == job.id), None)
            submission_attempt = (
                executor.submit(profile, job, application_plan)
                if execute_submissions
                else {
                    "attempted": False,
                    "submitted": False,
                    "status": "not_requested",
                    "notes": ["Automatic submission was not requested for this run."],
                }
            )
            submitted = (
                submission_attempt.submitted
                if hasattr(submission_attempt, "submitted")
                else bool(submission_attempt.get("submitted", False))
            )
            submission_status = (
                submission_attempt.status
                if hasattr(submission_attempt, "status")
                else str(submission_attempt.get("status", ""))
            )
            status_override = None
            if not submitted and application_plan.can_auto_submit:
                status_override = "queued"
            tracking_row = build_tracking_row(
                profile,
                job,
                score,
                applied=submitted,
                applied_on=date.today() if submitted else None,
                status_override=status_override,
            )
            stored_status = tracking_row.status
            # Preserve already-applied jobs during intake-only runs so a later
            # queueing pass does not regress them back to queued.
            if (
                existing is not None
                and str(existing.status).strip().lower()
                == str(profile.constraints.get("applied_status_value", "applied")).strip().lower()
                and not submitted
            ):
                stored_status = existing.status
            stored = upsert_job(
                state,
                job,
                score=score.score,
                decision=score.decision,
                status=stored_status,
            )
            processed.append(
                {
                    "job": asdict(stored),
                    "sheet_row": build_sheet_row_map(tracking_row),
                    "decision": score.decision,
                    "score": score.score,
                    "reasons": score.reasons,
                    "application_plan": asdict(application_plan),
                    "submission_attempt": asdict(submission_attempt)
                    if hasattr(submission_attempt, "__dataclass_fields__")
                    else submission_attempt,
                    "tracking_status_reason": submission_status,
                }
            )

        run = append_run(
            state,
            jobs_seen=len(jobs),
            jobs_written=len(processed),
            notes=["Cloud run executed against imported jobs."],
        )
        self.state_store.save(state)
        summary = build_run_summary(profile, processed)
        return {
            "jobs_seen": len(jobs),
            "jobs_written": len(processed),
            "run": asdict(run),
            "summary": summary,
            "results": processed,
        }

    def process_jobs_file(
        self,
        jobs_path: str | Path,
        *,
        mark_applied: bool = False,
        execute_submissions: bool = False,
    ) -> dict:
        jobs = load_jobs(jobs_path)
        result = self.process_jobs(jobs, mark_applied=mark_applied, execute_submissions=execute_submissions)
        result["jobs_path"] = str(jobs_path)
        return result


def build_run_summary(profile: CandidateProfile, processed: list[dict]) -> dict:
    submitted = 0
    queued = 0
    review = 0
    skipped = 0
    internal_ready = 0
    unknown_method = 0

    for item in processed:
        job = dict(item.get("job", {}))
        submission_attempt = dict(item.get("submission_attempt", {}))
        status = str(job.get("status", "")).strip().lower()
        decision = str(item.get("decision", "")).strip().lower()
        application_method = str(job.get("application_method", "")).strip().lower()

        if bool(submission_attempt.get("submitted", False)) or status == "applied":
            submitted += 1
        elif status == "queued":
            queued += 1
        elif decision == "skip":
            skipped += 1
        else:
            review += 1

        if application_method == "internal" and status == "queued":
            internal_ready += 1
        if application_method == "unknown":
            unknown_method += 1

    target_min = int(profile.constraints.get("daily_application_target_min", 0) or 0)
    target_max = int(profile.constraints.get("daily_application_target_max", target_min) or target_min)
    return {
        "submitted_count": submitted,
        "queued_count": queued,
        "review_count": review,
        "skipped_count": skipped,
        "internal_ready_count": internal_ready,
        "unknown_method_count": unknown_method,
        "daily_target_min": target_min,
        "daily_target_max": target_max,
        "submitted_target_gap": max(0, target_min - submitted),
        "qualified_volume_gap": max(0, target_min - (submitted + queued)),
    }
