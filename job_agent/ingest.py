from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .models import JobPosting


REQUIRED_FIELDS = {"id", "title", "company", "location", "url", "description"}
LINKEDIN_CITY_STATE_LOCATION_RE = re.compile(
    r"^(?P<company>.+?)\s+(?P<location>(?:[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2}),\s?[A-Z]{2}(?:\s*\((?:On-site|Hybrid|Remote)\))?)$"
)
LINKEDIN_REGION_LOCATION_RE = re.compile(
    r"^(?P<company>.+?)\s+(?P<location>(?:San Francisco Bay Area|Bay Area|Remote)(?:\s*\((?:On-site|Hybrid|Remote)\))?)$",
    re.IGNORECASE,
)
LINKEDIN_COMPANY_SUFFIXES = {
    "technologies",
    "technology",
    "corporation",
    "corp",
    "inc",
    "inc.",
    "llc",
    "systems",
    "labs",
    "lab",
    "group",
    "solutions",
}


def load_jobs(path: str | Path) -> list[JobPosting]:
    job_path = Path(path)
    suffix = job_path.suffix.lower()
    if suffix == ".json":
        return _load_json(job_path)
    if suffix == ".csv":
        return _load_csv(job_path)
    raise ValueError(f"Unsupported file format: {job_path.suffix}")


def _load_json(path: Path) -> list[JobPosting]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [_job_from_row(row) for row in rows]


def _load_csv(path: Path) -> list[JobPosting]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {sorted(missing)}")
        return [_job_from_row(row) for row in reader]


def _job_from_row(row: dict[str, str]) -> JobPosting:
    missing = REQUIRED_FIELDS - set(row)
    if missing:
        raise ValueError(f"Missing job fields: {sorted(missing)}")
    job = JobPosting(
        id=str(row["id"]).strip(),
        title=str(row["title"]).strip(),
        company=str(row["company"]).strip(),
        location=str(row["location"]).strip(),
        url=str(row["url"]).strip(),
        description=str(row["description"]).strip(),
        source=str(row.get("source", "manual")).strip() or "manual",
        application_method=str(row.get("application_method", "unknown")).strip() or "unknown",
        application_url=str(row.get("application_url", "")).strip(),
        requires_cover_letter=_parse_bool(row.get("requires_cover_letter", "")),
        requires_transcript=_parse_bool(row.get("requires_transcript", "")),
        requires_resume=not _is_falsey(row.get("requires_resume", "true")),
    )
    return _normalize_job(job)


def _normalize_job(job: JobPosting) -> JobPosting:
    if "linkedin" not in str(job.source or "").lower():
        return job

    if job.company and not job.location:
        inferred_company, inferred_location = _split_company_and_location(job.company)
        if inferred_company and inferred_location:
            job.company = inferred_company
            job.location = inferred_location

    if not job.company:
        inferred_company, inferred_location = _split_company_and_location(job.location)
        if inferred_company:
            job.company = inferred_company
        if inferred_location:
            job.location = inferred_location

    if (not job.company or not job.location) and job.description:
        description_tail = _strip_title_prefix(job.title, job.description)
        description_tail = description_tail.replace("with verification", " ").strip()
        inferred_company, inferred_location = _split_company_and_location(description_tail)
        if not job.company and inferred_company:
            job.company = inferred_company
        if not job.location and inferred_location:
            job.location = inferred_location

    job.company = job.company.strip()
    job.location = job.location.strip()
    return job


def _strip_title_prefix(title: str, description: str) -> str:
    cleaned_title = str(title or "").strip()
    cleaned_description = str(description or "").strip()
    if not cleaned_title or not cleaned_description:
        return cleaned_description

    doubled_prefix = f"{cleaned_title} {cleaned_title}"
    if cleaned_description.startswith(doubled_prefix):
        return cleaned_description[len(doubled_prefix) :].strip()
    if cleaned_description.startswith(cleaned_title):
        return cleaned_description[len(cleaned_title) :].strip()
    return cleaned_description


def _split_company_and_location(text: str) -> tuple[str, str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return "", ""

    full_match = LINKEDIN_CITY_STATE_LOCATION_RE.match(cleaned) or LINKEDIN_REGION_LOCATION_RE.match(cleaned)
    if full_match:
        company, location = (
            full_match.group("company").strip(" ,-"),
            full_match.group("location").strip(),
        )
        company, location = _repair_suffix_split(company, location)
        return company, location
    return "", ""


def _repair_suffix_split(company: str, location: str) -> tuple[str, str]:
    current_company = company.strip()
    current_location = location.strip()
    while True:
        first_token, remainder = _split_first_token(current_location)
        if not first_token:
            return current_company, current_location
        if first_token.lower().rstrip(".") not in LINKEDIN_COMPANY_SUFFIXES:
            return current_company, current_location
        current_company = f"{current_company} {first_token}".strip()
        current_location = remainder


def _split_first_token(text: str) -> tuple[str, str]:
    cleaned = text.strip()
    if not cleaned:
        return "", ""
    parts = cleaned.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1].strip()


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _is_falsey(value: object) -> bool:
    return str(value).strip().lower() in {"0", "false", "no", "n"}
