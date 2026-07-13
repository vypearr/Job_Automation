from __future__ import annotations

import re

from .models import CandidateProfile, JobPosting, ScoreBreakdown


KEYWORD_GROUPS = {
    "robotics_core": {
        "weight": 20,
        "terms": [
            "robotics",
            "robot",
            "autonomy",
            "mechatronics",
            "teleoperation",
            "manipulator",
            "mobile robot",
            "drone",
            "quadruped",
            "humanoid",
        ],
    },
    "embedded": {
        "weight": 18,
        "terms": [
            "embedded",
            "firmware",
            "microcontroller",
            "stm32",
            "arduino",
            "pcb",
            "circuit",
            "bring-up",
            "serial",
            "sensor",
        ],
    },
    "systems_software": {
        "weight": 14,
        "terms": [
            "linux",
            "debugging",
            "integration",
            "testing",
            "python",
            "c++",
            "c ",
            "controls",
            "simulation",
        ],
    },
    "student_fit": {
        "weight": 12,
        "terms": [
            "intern",
            "internship",
            "student",
            "new grad",
            "undergraduate",
        ],
    },
    "stretch_penalty": {
        "weight": -12,
        "terms": [
            "senior",
            "staff",
            "principal",
            "phd",
            "10+ years",
            "8+ years",
            "7+ years",
        ],
    },
}

NEGATIVE_SIGNALS = {
    "weight": -18,
    "terms": [
        "robotics experience is not required",
        "robotics experience not required",
        "no robotics experience required",
        "not a robotics role",
        "non robotics",
        "backend only",
    ],
}


def score_job(job: JobPosting, profile: CandidateProfile) -> ScoreBreakdown:
    haystack = normalize(" ".join([job.title, job.company, job.location, job.description]))
    title_haystack = normalize(job.title)
    score = 0
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    reasons: list[str] = []
    gating_flags: list[str] = []

    for group_name, group in KEYWORD_GROUPS.items():
        present = [term for term in group["terms"] if term in haystack]
        if group["weight"] > 0 and present:
            score += group["weight"]
            matched_keywords.extend(present)
            reasons.append(f"{group_name} aligned through: {', '.join(sorted(set(present)))}")
        if group["weight"] > 0 and not present:
            missing_keywords.extend(group["terms"][:2])
        if group["weight"] < 0 and present:
            score += group["weight"]
            reasons.append(f"stretch signals detected: {', '.join(sorted(set(present)))}")

    negative_hits = [term for term in NEGATIVE_SIGNALS["terms"] if term in haystack]
    if negative_hits:
        score += NEGATIVE_SIGNALS["weight"]
        reasons.append(f"negative alignment signals: {', '.join(sorted(set(negative_hits)))}")

    profile_terms = collect_profile_terms(profile)
    profile_matches = [term for term in profile_terms if term in haystack]
    if profile_matches:
        bonus = min(24, len(profile_matches) * 3)
        score += bonus
        matched_keywords.extend(profile_matches)
        reasons.append(f"profile overlap bonus from: {', '.join(sorted(set(profile_matches)))}")

    preferred_title_hits = [
        title for title in profile.preferred_titles if normalize(title) in haystack
    ]
    if preferred_title_hits:
        score += 10
        reasons.append("title closely matches preferred internship targets")

    title_focus_terms = [
        term
        for term in [
            "robot",
            "robotics",
            "mechatronic",
            "mechatronics",
            "firmware",
            "embedded",
            "controls",
            "autonomy",
            "manipulation",
        ]
        if term in title_haystack
    ]
    if title_focus_terms:
        score += min(15, len(title_focus_terms) * 5)
        reasons.append(f"title-domain bonus from: {', '.join(sorted(set(title_focus_terms)))}")

    score = max(0, min(score, 100))
    decision = decide(score)

    strategy = profile.constraints.get("application_strategy", "")
    skip_cover_letter = bool(profile.constraints.get("skip_cover_letter_required", False))
    if skip_cover_letter and job.requires_cover_letter:
        decision = "skip"
        score = min(score, 39)
        gating_flags.append("cover_letter_required")
        reasons.append("volume strategy gate: skip jobs that require a cover letter")

    if strategy == "volume":
        if job.requires_resume:
            gating_flags.append("resume_ok")
        if job.requires_transcript:
            gating_flags.append("transcript_ok")
        if not job.requires_resume and not job.requires_transcript:
            reasons.append("document requirements are unclear; verify before submitting at scale")
        if job.application_method == "external":
            gating_flags.append("external_apply")
            reasons.append("application exits Handshake and may need a site-specific adapter")
        elif job.application_method == "internal":
            gating_flags.append("internal_apply")
            reasons.append("application appears to stay inside Handshake")

    if decision == "auto_apply":
        reasons.append("high confidence fit for Tarun's robotics and embedded trajectory")
    elif decision == "review":
        reasons.append("worth a manual review before applying")
    else:
        reasons.append("low alignment compared with target robotics profile")

    return ScoreBreakdown(
        score=score,
        decision=decision,
        matched_keywords=sorted(set(matched_keywords)),
        missing_keywords=sorted(set(missing_keywords))[:8],
        reasons=reasons,
        gating_flags=gating_flags,
    )


def decide(score: int) -> str:
    if score >= 65:
        return "auto_apply"
    if score >= 40:
        return "review"
    return "skip"


def collect_profile_terms(profile: CandidateProfile) -> list[str]:
    terms: list[str] = []
    terms.extend(profile.target_domains)
    terms.extend(profile.coursework)
    for values in profile.skills.values():
        terms.extend(values)
    return [normalize(term) for term in terms if term]


def normalize(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9+\-#\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return f" {lowered.strip()} "
