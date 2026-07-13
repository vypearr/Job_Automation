from __future__ import annotations

from datetime import date

from .models import CandidateProfile, JobPosting, ScoreBreakdown, TrackingRow


def build_tracking_row(
    profile: CandidateProfile,
    job: JobPosting,
    score: ScoreBreakdown,
    *,
    applied: bool = False,
    applied_on: date | None = None,
) -> TrackingRow:
    applied_status = str(profile.constraints.get("applied_status_value", "applied"))
    review_status = "Checkin/Review"
    status = applied_status if applied else infer_pending_status(job, score, fallback=review_status)
    when = applied_on.isoformat() if applied_on else ""

    return TrackingRow(
        date_applied=when,
        company=job.company,
        role=job.title,
        description=job.description,
        reply="",
        status=status,
    )


def infer_pending_status(job: JobPosting, score: ScoreBreakdown, *, fallback: str) -> str:
    if job.application_method == "external":
        return fallback
    if score.decision == "skip":
        return "Checkin/Review"
    if score.decision == "review":
        return "Checkin/Review"
    return "queued"


def target_sheet_name(profile: CandidateProfile, job: JobPosting, score: ScoreBreakdown) -> str:
    external_action = str(profile.constraints.get("external_apply_action", "applied_sheet_checkin_review"))
    if job.application_method == "external" and external_action == "applied_sheet_checkin_review":
        return "Applied"
    return "Applied"


def build_sheet_row_map(row: TrackingRow) -> dict[str, str]:
    return {
        "A": row.date_applied,
        "B": row.company,
        "C": row.role,
        "D": row.description,
        "E": row.reply,
        "F": row.status,
    }


def tracking_headers() -> list[str]:
    return [
        "Date Applied",
        "Company",
        "Role",
        "Company Description / Role Description",
        "Reply",
        "Status",
    ]


def tracking_values(row: TrackingRow) -> list[str]:
    return [
        row.date_applied,
        row.company,
        row.role,
        row.description,
        row.reply,
        row.status,
    ]
