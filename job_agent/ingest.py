from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import JobPosting


REQUIRED_FIELDS = {"id", "title", "company", "location", "url", "description"}


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
    return JobPosting(
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


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _is_falsey(value: object) -> bool:
    return str(value).strip().lower() in {"0", "false", "no", "n"}
