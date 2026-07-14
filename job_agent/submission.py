from __future__ import annotations

import os
from dataclasses import dataclass, field

from .apply_pipeline import ApplicationPlan
from .models import CandidateProfile, JobPosting


@dataclass
class SubmissionAttempt:
    attempted: bool
    submitted: bool
    status: str
    notes: list[str] = field(default_factory=list)


class SubmissionExecutor:
    platform_name = "base"

    def submit(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        plan: ApplicationPlan,
    ) -> SubmissionAttempt:
        if not plan.can_auto_submit:
            return SubmissionAttempt(
                attempted=False,
                submitted=False,
                status="not_eligible",
                notes=["Job is not eligible for automatic submission."],
            )
        return SubmissionAttempt(
            attempted=False,
            submitted=False,
            status="unsupported_platform",
            notes=["Automatic submission is not implemented for this platform."],
        )


class HandshakeSubmissionExecutor(SubmissionExecutor):
    platform_name = "handshake"

    def submit(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        plan: ApplicationPlan,
    ) -> SubmissionAttempt:
        if not plan.can_auto_submit:
            return SubmissionAttempt(
                attempted=False,
                submitted=False,
                status="not_eligible",
                notes=["Handshake job is not eligible for automatic submission."],
            )
        if job.application_method != "internal":
            return SubmissionAttempt(
                attempted=False,
                submitted=False,
                status="external_review_required",
                notes=["Handshake job redirects externally and must stay in review."],
            )

        session_mode = os.getenv("JOB_AGENT_HANDSHAKE_SESSION_MODE", "").strip().lower()
        if session_mode != "connected":
            return SubmissionAttempt(
                attempted=False,
                submitted=False,
                status="browser_session_required",
                notes=[
                    "Handshake internal submission is enabled in logic but still needs a live signed-in browser session.",
                    "Cloud cron can score and queue the job, but it cannot complete the click-through submission alone yet.",
                ],
            )

        return SubmissionAttempt(
            attempted=False,
            submitted=False,
            status="executor_not_implemented",
            notes=[
                "A live Handshake session is declared connected, but the browser-driven submitter is not implemented yet.",
            ],
        )


class GenericSubmissionExecutor(SubmissionExecutor):
    platform_name = "generic_hosted"
