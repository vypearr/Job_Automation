from __future__ import annotations

from dataclasses import dataclass, field

from .models import CandidateProfile, JobPosting, ScoreBreakdown


@dataclass
class ApplicationPlan:
    job_id: str
    company: str
    title: str
    decision: str
    notes: list[str]
    next_action: str = "review"
    can_auto_submit: bool = False
    blockers: list[str] = field(default_factory=list)
    required_documents: list[str] = field(default_factory=list)
    platform_name: str = "base"


class JobPlatformAdapter:
    platform_name = "base"

    def create_application_plan(
        self,
        profile: CandidateProfile,
        job: JobPosting,
        score: ScoreBreakdown,
    ) -> ApplicationPlan:
        required_documents = collect_required_documents(job)
        blockers = collect_blockers(profile, job, score)
        notes = [
            f"Prepare resume for {job.title} at {job.company}.",
            f"Decision from scorer: {score.decision} ({score.score}/100).",
            f"Application method: {job.application_method}.",
            f"Gates: {', '.join(score.gating_flags) if score.gating_flags else 'none'}.",
            f"Required documents: {', '.join(required_documents) if required_documents else 'none detected'}.",
            "Live submission remains adapter-specific and should respect the user's cover-letter skip rule.",
        ]
        return ApplicationPlan(
            job_id=job.id,
            company=job.company,
            title=job.title,
            decision=score.decision,
            notes=notes,
            next_action=infer_next_action(job, score, blockers),
            can_auto_submit=False,
            blockers=blockers,
            required_documents=required_documents,
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
        if plan.decision == "auto_apply" and job.application_method == "internal" and not plan.blockers:
            plan.next_action = "review_easy_apply"
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
        if plan.decision == "auto_apply" and job.application_method == "internal" and not plan.blockers:
            plan.can_auto_submit = True
            plan.next_action = str(profile.constraints.get("high_confidence_action", "full_submit"))
            plan.notes.append("Eligible for Handshake-native full submission once a signed-in session is available.")
        elif job.application_method == "external":
            plan.next_action = "review_external"
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
        if plan.decision == "auto_apply" and job.application_method == "internal" and not plan.blockers:
            plan.next_action = "review_native_apply"
        return plan


class GenericHostedAdapter(JobPlatformAdapter):
    platform_name = "generic_hosted"


def collect_required_documents(job: JobPosting) -> list[str]:
    documents: list[str] = []
    if job.requires_resume:
        documents.append("resume")
    if job.requires_transcript:
        documents.append("transcript")
    if job.requires_cover_letter:
        documents.append("cover_letter")
    return documents


def collect_blockers(profile: CandidateProfile, job: JobPosting, score: ScoreBreakdown) -> list[str]:
    blockers: list[str] = []
    allowed_documents = {
        str(value).strip().lower()
        for value in profile.constraints.get("allowed_required_documents", [])
        if str(value).strip()
    }
    required_documents = collect_required_documents(job)
    disallowed_documents = [
        document for document in required_documents if document not in allowed_documents and document != "cover_letter"
    ]
    if job.requires_cover_letter and bool(profile.constraints.get("skip_cover_letter_required", False)):
        blockers.append("cover_letter_required")
    if disallowed_documents:
        blockers.append(f"unsupported_documents:{','.join(disallowed_documents)}")
    if score.decision == "skip":
        blockers.append("score_below_threshold")
    if job.application_method == "external":
        blockers.append("external_application")
    return blockers


def infer_next_action(job: JobPosting, score: ScoreBreakdown, blockers: list[str]) -> str:
    if score.decision == "skip":
        return "skip"
    if "cover_letter_required" in blockers:
        return "skip"
    if job.application_method == "external":
        return "review_external"
    if score.decision == "auto_apply" and not blockers:
        return "prepare_submit"
    return "review"
