from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobPosting:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    source: str = "manual"
    application_method: str = "unknown"
    application_url: str = ""
    requires_cover_letter: bool = False
    requires_transcript: bool = False
    requires_resume: bool = True


@dataclass
class ScoreBreakdown:
    score: int
    decision: str
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    gating_flags: list[str] = field(default_factory=list)


@dataclass
class CandidateProfile:
    name: str
    email: str
    phone: str
    school: str
    major: str
    degree: str
    graduation: str
    gpa: float
    target_domains: list[str]
    preferred_titles: list[str]
    skills: dict[str, list[str]]
    coursework: list[str]
    experience_highlights: list[str]
    links: dict[str, str]
    documents: dict[str, str]
    constraints: dict[str, object]


@dataclass
class TrackingRow:
    date_applied: str
    company: str
    role: str
    description: str
    reply: str
    status: str
