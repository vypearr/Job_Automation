from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .cloud_store import JsonStateStore, append_run
from .models import JobPosting, ScoreBreakdown
from .profile_loader import load_profile
from .tracking import build_sheet_row_map, build_tracking_row
from .tracking_sync import sync_tracking_rows


def sync_state_to_sheet(
    *,
    base_dir: Path,
    profile_path: str = "profile.json",
    state_path: str = "data/state.json",
) -> dict:
    profile = load_profile(base_dir / profile_path)
    state_store = JsonStateStore(base_dir / state_path)
    state = state_store.load()

    results = []
    for stored in state.jobs:
        applied = str(stored.status).strip().lower() == str(
            profile.constraints.get("applied_status_value", "applied")
        ).strip().lower()
        status_override = None if applied else stored.status
        tracking_row = build_tracking_row(
            profile,
            JobPosting(
                id=stored.id,
                title=stored.title,
                company=stored.company,
                location=stored.location,
                url=stored.url,
                description=stored.description,
                source=stored.source,
                application_method=stored.application_method,
                application_url=stored.application_url,
                requires_cover_letter=stored.requires_cover_letter,
                requires_transcript=stored.requires_transcript,
                requires_resume=stored.requires_resume,
            ),
            ScoreBreakdown(score=stored.score, decision=stored.decision),
            applied=applied,
            status_override=status_override,
        )
        results.append(
            {
                "job": asdict(stored),
                "decision": stored.decision,
                "score": stored.score,
                "sheet_row": build_sheet_row_map(tracking_row),
            }
        )

    run = append_run(
        state,
        jobs_seen=len(state.jobs),
        jobs_written=len(results),
        notes=["Manual full-state sheet resync executed from local state."],
    )
    state_store.save(state)

    payload = {
        "jobs_seen": len(state.jobs),
        "jobs_written": len(results),
        "run": asdict(run),
        "summary": {
            "total_jobs": len(state.jobs),
            "applied_count": sum(1 for job in state.jobs if str(job.status).strip().lower() == "applied"),
            "queued_count": sum(1 for job in state.jobs if str(job.status).strip().lower() == "queued"),
            "review_count": sum(1 for job in state.jobs if str(job.status).strip() == "Checkin/Review"),
        },
        "results": results,
    }
    payload["tracking_sync"] = sync_tracking_rows(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Push the current local state.json view back into the Google Sheet.")
    parser.add_argument("--profile", default="profile.json", help="Path to the candidate profile JSON file.")
    parser.add_argument("--state", default="data/state.json", help="Path to the local state JSON file.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    payload = sync_state_to_sheet(
        base_dir=base_dir,
        profile_path=args.profile,
        state_path=args.state,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
