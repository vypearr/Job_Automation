from __future__ import annotations

import json
import re
from pathlib import Path

from .models import JobPosting


TITLE_STARTERS = {
    "ai",
    "automation",
    "computer",
    "controls",
    "embedded",
    "firmware",
    "internal",
    "machine",
    "mechatronic",
    "mechatronics",
    "product",
    "robot",
    "robotics",
    "software",
    "systems",
}

TITLE_SUFFIXES = {
    "intern",
    "engineer",
    "developer",
    "scientist",
    "technician",
}

LOCATION_PATTERN = re.compile(
    r"(?P<location>Remote|[A-Z][A-Za-z.\s]+,\s?[A-Z]{2}|[A-Z][A-Za-z.\s]+,\s?[A-Za-z\s]+)$"
)


def load_handshake_labels(path: str | Path) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def parse_handshake_labels(labels: list[str]) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    for index, label in enumerate(labels, start=1):
        job = parse_handshake_label(label, index=index)
        if job:
            jobs.append(job)
    return jobs


def parse_handshake_label(label: str, *, index: int) -> JobPosting | None:
    cleaned = normalize_label(label)
    if " · " not in cleaned:
        return None
    left = cleaned.split("$", 1)[0].strip()
    location = extract_location(cleaned)
    company, title = split_company_and_title(left)
    if not company or not title:
        return None
    posting_id = f"handshake-card-{index:03d}"
    description = (
        f"Imported from visible Handshake job card. Company: {company}. "
        f"Title: {title}. Location: {location}."
    )

    return JobPosting(
        id=posting_id,
        title=title,
        company=company,
        location=location,
        url="https://sfsu.joinhandshake.com/job-search",
        description=description,
        source="handshake_card_import",
        application_method="unknown",
        application_url="",
        requires_resume=True,
        requires_transcript=False,
        requires_cover_letter=False,
    )


def export_jobs_to_json(path: str | Path, jobs: list[JobPosting]) -> None:
    rows = [job.__dict__ for job in jobs]
    Path(path).write_text(json.dumps(rows, indent=2), encoding="utf-8")


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.replace("·", " · ")).strip()


def extract_location(cleaned: str) -> str:
    prefix = cleaned
    for marker in [" New", " Promoted", " 6d ago", " 2wk ago", " 3wk ago", " 2mo ago"]:
        if marker in prefix:
            prefix = prefix.split(marker, 1)[0].strip()
    match = LOCATION_PATTERN.search(prefix)
    location = match.group("location").strip() if match else ""
    for prefix in ["Internship ", "Full-time ", "Part-time job "]:
        if location.startswith(prefix):
            location = location[len(prefix) :].strip()
    return location


def split_company_and_title(left: str) -> tuple[str, str]:
    tokens = left.split()
    suffix_indexes = [
        index for index, token in enumerate(tokens) if normalize_token(token) in TITLE_SUFFIXES
    ]
    if not suffix_indexes:
        return "", ""

    suffix_index = suffix_indexes[-1]
    start_index = None
    for index in range(suffix_index, -1, -1):
        if normalize_token(tokens[index]) in TITLE_STARTERS:
            start_index = index
            break
    if start_index is None:
        start_index = max(1, suffix_index - 1)

    company = " ".join(tokens[:start_index]).strip(" -")
    title = " ".join(tokens[start_index:]).strip(" -")
    return company, title


def normalize_token(token: str) -> str:
    return re.sub(r"[^a-z]", "", token.lower())
