from __future__ import annotations

import json
import re
from hashlib import sha1
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
        stable_id = stable_card_id("linkedin", title, company, location, fallback_index=index)
        jobs.append(
            JobPosting(
                id=stable_id,
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
        stable_id = stable_card_id("indeed", title, company, location, fallback_index=index)
        jobs.append(
            JobPosting(
                id=stable_id,
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


def stable_card_id(platform: str, title: str, company: str, location: str, *, fallback_index: int) -> str:
    normalized = "|".join(
        normalize_fragment(fragment)
        for fragment in [title, company, location]
    )
    if not normalized.replace("|", "").strip():
        return f"{platform}-card-{fallback_index:03d}"
    digest = sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{platform}-card-{digest}"


def normalize_fragment(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-+", "-", lowered).strip("-")
    return lowered
