from __future__ import annotations

import re

from .models import CandidateProfile, JobPosting


TITLE_PRIORITY_TERMS = [
    "robot",
    "robotics",
    "mechatronic",
    "mechatronics",
    "embedded",
    "firmware",
    "hardware",
    "electrical",
    "controls",
    "autonomy",
    "manipulation",
    "teleoperation",
    "systems",
]

DESCRIPTION_PRIORITY_TERMS = [
    "robot",
    "robotics",
    "embedded",
    "firmware",
    "hardware",
    "controls",
    "electrical",
    "sensor",
    "linux",
    "python",
    "c++",
    "c ",
    "stm32",
    "pcb",
]

ROLE_SHAPE_TERMS = [
    "intern",
    "internship",
    "new grad",
    "entry level",
    "early career",
    "student",
]


def select_targeted_jobs(
    jobs: list[JobPosting],
    profile: CandidateProfile,
    *,
    min_match_score: int = 2,
) -> list[JobPosting]:
    selected: list[JobPosting] = []
    for job in jobs:
        if target_match_score(job, profile) >= min_match_score:
            selected.append(job)
    return selected


def target_match_score(job: JobPosting, profile: CandidateProfile) -> int:
    title = normalize(job.title)
    description = normalize(job.description)

    score = 0

    title_hits = count_hits(title, TITLE_PRIORITY_TERMS)
    description_hits = count_hits(description, DESCRIPTION_PRIORITY_TERMS)
    role_shape_hits = count_hits(title, ROLE_SHAPE_TERMS) + count_hits(description, ROLE_SHAPE_TERMS)

    if title_hits:
        score += min(4, title_hits)
    if description_hits:
        score += min(3, description_hits)
    if role_shape_hits:
        score += 1

    preferred_location_terms = [
        normalize(str(value)).strip()
        for value in profile.constraints.get("preferred_locations", [])
        if str(value).strip()
    ]
    location = normalize(job.location)
    if any(term and term in location for term in preferred_location_terms):
        score += 1
    if "remote" in location:
        score += 1

    return score


def count_hits(haystack: str, terms: list[str]) -> int:
    return sum(1 for term in terms if normalize(term) in haystack)


def normalize(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9+\-#\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return f" {lowered.strip()} "
