from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cloud_service import CloudAutomationService
from .tracking_sync import build_tracking_sync_payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a sample tracking webhook payload for the Google Apps Script sync."
    )
    parser.add_argument(
        "--jobs",
        default="data/handshake_enriched_jobs.json",
        help="Path to the JSON jobs file to process before building the webhook payload.",
    )
    parser.add_argument(
        "--out",
        help="Optional output path for the generated payload JSON.",
    )
    parser.add_argument(
        "--mark-applied",
        action="store_true",
        help="Mark eligible auto-submit jobs as applied in the emitted payload.",
    )
    parser.add_argument(
        "--execute-submissions",
        action="store_true",
        help="Ask executors to attempt submissions while building the payload.",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    jobs_path = (base_dir / args.jobs).resolve() if not Path(args.jobs).is_absolute() else Path(args.jobs)

    service = CloudAutomationService(base_dir)
    result = service.process_jobs_file(
        jobs_path,
        mark_applied=args.mark_applied,
        execute_submissions=args.execute_submissions,
    )
    payload = build_tracking_sync_payload(result)

    if args.out:
        output_path = (base_dir / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote tracking payload to {output_path}")
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
