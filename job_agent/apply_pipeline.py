from __future__ import annotations

from dataclasses import dataclass

from .models import CandidateProfile, JobPosting, ScoreBreakdown


@dataclass
class ApplicationPlan:
    job_id: str
    company: str
    title: str
    decision: str
    notes: list[str]
    platform_name: str = "base"


class JobPlatformAdapter:
    platform_name = "base"

    def create_application_plan(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        score: ScoreBreakdown,
    ) -> ApplicationPlan:
        notes = [
            f"Prepare resume for {job.title} at {job.company}.",
            f"Decision from scorer: {score.decision} ({score.score}/100).",
            f"Application method: {job.application_method}.",
            f"Gates: {', '.join(score.gating_flags) if score.gating_flags else 'none'}.",
            "Live submission is not implemented in the base adapter.",
        ]
        return ApplicationPlan(
            job_id=job.id,
            company=job.company,
            title=job.title,
            decision=score.decision,
            notes=notes,
            platform_name=self.platform_name,
        )


class LinkedInAdapter(JobPlatformAdapter):
    platform_name = "linkedin"

    def create_application_plan(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        score: ScoreBreakdown,
    ) -> ApplicationPlan:
        plan = super().create_application_plan(profile, job, score)
        plan.notes.append("LinkedIn flow should prefer Easy Apply and avoid roles requiring custom cover letters.")
        return plan


class HandshakeAdapter(JobPlatformAdapter):
    platform_name = "handshake"

    def create_application_plan(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        score: ScoreBreakdown,
    ) -> ApplicationPlan:
        plan = super().create_application_plan(profile, job, score)
        plan.notes.append("Handshake flow can track internal applications directly and send external ones to Checkin/Review.")
        return plan


class IndeedAdapter(JobPlatformAdapter):
    platform_name = "indeed"

    def create_application_plan(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        score: ScoreBreakdown,
    ) -> ApplicationPlan:
        plan = super().create_application_plan(profile, job, score)
        plan.notes.append("Indeed flow should prefer native apply flows and queue external redirects for review.")
        return plan


class GenericHostedAdapter(JobPlatformAdapter):
    platform_name = "generic_hosted"
