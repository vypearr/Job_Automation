from __future__ import annotations

import json
import re
from pathlib import Path

from .models import JobPosting


def load_labels(path: str | Path) -> list[str]:
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_linkedin_labels(labels: list[str]) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    for index, label in enumerate(labels, start=1):
        parts = [part.strip() for part in label.split("|")]
        if len(parts) < 3:
            continue
        title, company, location = parts[:3]
        jobs.append(
            JobPosting(
                id=f"linkedin-card-{index:03d}",
                title=title,
                company=company,
                location=location,
                url="https://www.linkedin.com/jobs/",
                description=f"Imported from visible LinkedIn job card. Company: {company}. Title: {title}. Location: {location}.",
                source="linkedin_card_import",
                application_method="unknown",
                application_url="",
                requires_cover_letter=False,
                requires_transcript=False,
                requires_resume=True,
            )
        )
    return jobs


def parse_indeed_labels(labels: list[str]) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    for index, label in enumerate(labels, start=1):
        parts = [part.strip() for part in label.split("|")]
        if len(parts) < 3:
            continue
        title, company, location = parts[:3]
        jobs.append(
            JobPosting(
                id=f"indeed-card-{index:03d}",
                title=title,
                company=company,
                location=location,
                url="https://www.indeed.com/jobs",
                description=f"Imported from visible Indeed job card. Company: {company}. Title: {title}. Location: {location}.",
                source="indeed_card_import",
                application_method="unknown",
                application_url="",
                requires_cover_letter=False,
                requires_transcript=False,
                requires_resume=True,
            )
        )
    return jobs


def export_jobs_to_json(path: str | Path, jobs: list[JobPosting]) -> None:
    Path(path).write_text(json.dumps([job.__dict__ for job in jobs], indent=2), encoding="utf-8")


def detect_label_source(path: str | Path) -> str:
    name = Path(path).name.lower()
    if "linkedin" in name:
        return "linkedin"
    if "indeed" in name:
        return "indeed"
    if "handshake" in name:
        return "handshake"
    return "unknown"
