from __future__ import annotations

from .apply_pipeline import (
    GenericHostedAdapter,
    HandshakeAdapter,
    IndeedAdapter,
    LinkedInAdapter,
)


def detect_platform(url: str, source: str = "") -> str:
    lowered_url = url.lower()
    lowered_source = source.lower()

    if "linkedin.com" in lowered_url or "linkedin" in lowered_source:
        return "linkedin"
    if "indeed.com" in lowered_url or "indeed" in lowered_source:
        return "indeed"
    if "handshake" in lowered_url or "handshake" in lowered_source:
        return "handshake"
    return "generic_hosted"


def select_adapter_for_job(job, adapters: dict[str, object]):
    platform = detect_platform(job.url, job.source)
    return adapters.get(platform, adapters["generic_hosted"])
