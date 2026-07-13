from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .apply_pipeline import GenericHostedAdapter, HandshakeAdapter, IndeedAdapter, LinkedInAdapter
from .handshake_import import export_jobs_to_json, load_handshake_labels, parse_handshake_labels
from .ingest import load_jobs
from .multi_source_import import (
    detect_label_source,
    export_jobs_to_json as export_multi_source_json,
    load_labels,
    parse_indeed_labels,
    parse_linkedin_labels,
)
from .platforms import select_adapter_for_job
from .profile_loader import load_profile
from .scoring import score_job
from .tracking import build_tracking_row, tracking_headers, tracking_values


def main() -> None:
    parser = argparse.ArgumentParser(description="Score jobs for a robotics-focused student profile.")
    parser.add_argument("--jobs", required=True, help="Path to a JSON or CSV file of jobs.")
    parser.add_argument(
        "--handshake-labels",
        help="Optional path to a plain text file of visible Handshake card labels to import.",
    )
    parser.add_argument(
        "--platform-labels",
        help="Optional path to visible LinkedIn or Indeed labels in `Title | Company | Location` format.",
    )
    parser.add_argument(
        "--profile",
        default="profile.json",
        help="Path to the candidate profile JSON file.",
    )
    parser.add_argument(
        "--tracking-out",
        help="Optional CSV path for spreadsheet-ready tracking rows.",
    )
    parser.add_argument(
        "--import-json-out",
        help="Optional JSON path to save imported Handshake labels as structured jobs.",
    )
    args = parser.parse_args()

    profile = load_profile(args.profile)
    jobs = load_input_jobs(args)

    linkedin = LinkedInAdapter()
    handshake = HandshakeAdapter()
    indeed = IndeedAdapter()
    generic = GenericHostedAdapter()
    adapters = {
        "linkedin": linkedin,
        "handshake": handshake,
        "indeed": indeed,
        "generic_hosted": generic,
    }

    print(f"Candidate: {profile.name} | {profile.major} | GPA {profile.gpa}")
    print(f"Jobs loaded: {len(jobs)}")
    print("-" * 80)
    tracking_rows: list[list[str]] = []

    for job in jobs:
        score = score_job(job, profile)
        adapter = select_adapter_for_job(job, adapters)
        plan = adapter.create_application_plan(profile, job, score)
        tracking_row = build_tracking_row(profile, job, score)
        tracking_rows.append(tracking_values(tracking_row))

        print(f"{job.title} @ {job.company}")
        print(f"Location: {job.location}")
        print(f"URL: {job.url}")
        print(f"Score: {score.score}/100 | Decision: {score.decision}")
        print(f"Apply path: {job.application_method or 'unknown'}")
        print(
            "Docs: "
            f"resume={'yes' if job.requires_resume else 'no'}, "
            f"transcript={'yes' if job.requires_transcript else 'no'}, "
            f"cover_letter={'yes' if job.requires_cover_letter else 'no'}"
        )
        print("Why:")
        for reason in score.reasons:
            print(f"  - {reason}")
        if score.missing_keywords:
            print(f"Missing signals: {', '.join(score.missing_keywords)}")
        if score.gating_flags:
            print(f"Gates: {', '.join(score.gating_flags)}")
        print(f"Adapter: {adapter.platform_name}")
        for note in plan.notes:
            print(f"  * {note}")
        print("-" * 80)

    if args.tracking_out:
        write_tracking_csv(args.tracking_out, tracking_rows)
        print(f"Tracking export: {args.tracking_out}")


def write_tracking_csv(path: str, rows: list[list[str]]) -> None:
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(tracking_headers())
        writer.writerows(rows)


def load_input_jobs(args: argparse.Namespace) -> list:
    if args.handshake_labels:
        labels = load_handshake_labels(args.handshake_labels)
        jobs = parse_handshake_labels(labels)
        if args.import_json_out:
            export_jobs_to_json(args.import_json_out, jobs)
        return jobs
    if args.platform_labels:
        labels = load_labels(args.platform_labels)
        source = detect_label_source(args.platform_labels)
        if source == "linkedin":
            jobs = parse_linkedin_labels(labels)
        elif source == "indeed":
            jobs = parse_indeed_labels(labels)
        else:
            jobs = []
        if args.import_json_out:
            export_multi_source_json(args.import_json_out, jobs)
        return jobs
    return load_jobs(args.jobs)


if __name__ == "__main__":
    main()
