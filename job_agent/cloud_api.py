from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .cloud_service import CloudAutomationService
from .models import JobPosting


BASE_DIR = Path(__file__).resolve().parent.parent
service = CloudAutomationService(BASE_DIR)
app = FastAPI(title="Robotics Job Agent Cloud API", version="0.1.0")


class JobPayload(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str = "api"
    application_method: str = "unknown"
    application_url: str = ""
    requires_cover_letter: bool = False
    requires_transcript: bool = False
    requires_resume: bool = True


class BatchPayload(BaseModel):
    jobs: list[JobPayload] = Field(default_factory=list)
    mark_applied: bool = False
    execute_submissions: bool = False


class FileRunPayload(BaseModel):
    jobs_path: str
    mark_applied: bool = False
    execute_submissions: bool = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/profile")
def profile() -> dict:
    return service.load_profile().__dict__


@app.get("/jobs")
def jobs() -> dict:
    return {"jobs": service.list_jobs()}


@app.get("/runs")
def runs() -> dict:
    return {"runs": service.list_runs()}


@app.post("/jobs/process")
def process_jobs(payload: BatchPayload) -> dict:
    jobs = [JobPosting(**item.model_dump()) for item in payload.jobs]
    return service.process_jobs(
        jobs,
        mark_applied=payload.mark_applied,
        execute_submissions=payload.execute_submissions,
    )


@app.post("/runs/process-file")
def process_file(payload: FileRunPayload) -> dict:
    return service.process_jobs_file(
        payload.jobs_path,
        mark_applied=payload.mark_applied,
        execute_submissions=payload.execute_submissions,
    )
