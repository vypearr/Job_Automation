from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .models import JobPosting, TrackingRow


@dataclass
class StoredJob:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str
    application_method: str
    application_url: str
    requires_cover_letter: bool
    requires_transcript: bool
    requires_resume: bool
    score: int
    decision: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class StoredRun:
    run_id: str
    created_at: str
    jobs_seen: int
    jobs_written: int
    notes: list[str] = field(default_factory=list)


@dataclass
class CloudState:
    jobs: list[StoredJob] = field(default_factory=list)
    runs: list[StoredRun] = field(default_factory=list)


class JsonStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> CloudState:
        if not self.path.exists():
            return CloudState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return CloudState(
            jobs=[StoredJob(**row) for row in data.get("jobs", [])],
            runs=[StoredRun(**row) for row in data.get("runs", [])],
        )

    def save(self, state: CloudState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "jobs": [asdict(job) for job in state.jobs],
            "runs": [asdict(run) for run in state.runs],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_job(
    state: CloudState,
    job: JobPosting,
    *,
    score: int,
    decision: str,
    status: str,
) -> StoredJob:
    existing = next((item for item in state.jobs if item.id == job.id), None)
    timestamp = now_utc_iso()
    if existing:
        existing.title = job.title
        existing.company = job.company
        existing.location = job.location
        existing.url = job.url
        existing.description = job.description
        existing.source = job.source
        existing.application_method = job.application_method
        existing.application_url = job.application_url
        existing.requires_cover_letter = job.requires_cover_letter
        existing.requires_transcript = job.requires_transcript
        existing.requires_resume = job.requires_resume
        existing.score = score
        existing.decision = decision
        existing.status = status
        existing.updated_at = timestamp
        return existing

    created = StoredJob(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        description=job.description,
        source=job.source,
        application_method=job.application_method,
        application_url=job.application_url,
        requires_cover_letter=job.requires_cover_letter,
        requires_transcript=job.requires_transcript,
        requires_resume=job.requires_resume,
        score=score,
        decision=decision,
        status=status,
        created_at=timestamp,
        updated_at=timestamp,
    )
    state.jobs.append(created)
    return created


def append_run(state: CloudState, *, jobs_seen: int, jobs_written: int, notes: list[str]) -> StoredRun:
    run = StoredRun(
        run_id=f"run-{len(state.runs) + 1:04d}",
        created_at=now_utc_iso(),
        jobs_seen=jobs_seen,
        jobs_written=jobs_written,
        notes=notes,
    )
    state.runs.append(run)
    return run
