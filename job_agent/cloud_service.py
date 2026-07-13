from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path

from .cloud_store import JsonStateStore, append_run, upsert_job
from .ingest import load_jobs
from .models import CandidateProfile, JobPosting
from .profile_loader import load_profile
from .scoring import score_job
from .tracking import build_sheet_row_map, build_tracking_row


class CloudAutomationService:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.profile_path = self.base_dir / "profile.json"
        self.state_store = JsonStateStore(self.base_dir / "data" / "state.json")

    def load_profile(self) -> CandidateProfile:
        return load_profile(self.profile_path)

    def list_jobs(self) -> list[dict]:
        state = self.state_store.load()
        return [asdict(job) for job in state.jobs]

    def list_runs(self) -> list[dict]:
        state = self.state_store.load()
        return [asdict(run) for run in state.runs]

    def process_jobs(self, jobs: list[JobPosting], *, mark_applied: bool = False) -> dict:
        profile = self.load_profile()
        state = self.state_store.load()
        processed: list[dict] = []

        for job in jobs:
            score = score_job(job, profile)
            tracking_row = build_tracking_row(
                profile,
                job,
                score,
                applied=mark_applied and score.decision == "auto_apply" and job.application_method != "external",
                applied_on=date.today() if mark_applied and score.decision == "auto_apply" and job.application_method != "external" else None,
            )
            stored = upsert_job(
                state,
                job,
                score=score.score,
                decision=score.decision,
                status=tracking_row.status,
            )
            processed.append(
                {
                    "job": asdict(stored),
                    "sheet_row": build_sheet_row_map(tracking_row),
                    "decision": score.decision,
                    "score": score.score,
                    "reasons": score.reasons,
                }
            )

        run = append_run(
            state,
            jobs_seen=len(jobs),
            jobs_written=len(processed),
            notes=["Cloud run executed against imported jobs."],
        )
        self.state_store.save(state)
        return {
            "jobs_seen": len(jobs),
            "jobs_written": len(processed),
            "run": asdict(run),
            "results": processed,
        }

    def process_jobs_file(self, jobs_path: str | Path, *, mark_applied: bool = False) -> dict:
        jobs = load_jobs(jobs_path)
        return self.process_jobs(jobs, mark_applied=mark_applied)
