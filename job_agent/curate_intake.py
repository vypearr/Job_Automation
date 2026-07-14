from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ingest import load_jobs
from .intake_filters import select_targeted_jobs, target_match_score
from .profile_loader import load_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter a broad jobs batch into a robotics-targeted intake set.")
    parser.add_argument("--jobs", required=True, help="Path to the source jobs JSON or CSV file.")
    parser.add_argument("--profile", default="profile.json", help="Path to the candidate profile JSON file.")
    parser.add_argument("--out", required=True, help="Output JSON path for the curated jobs batch.")
    parser.add_argument("--min-match-score", type=int, default=2, help="Minimum target-match score to keep a job.")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    jobs = load_jobs(args.jobs)
    curated = select_targeted_jobs(jobs, profile, min_match_score=args.min_match_score)

    rows = []
    for job in curated:
        row = dict(job.__dict__)
        row["target_match_score"] = target_match_score(job, profile)
        rows.append(row)

    output_path = Path(args.out)
    output_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "source_jobs": len(jobs),
                "curated_jobs": len(curated),
                "min_match_score": args.min_match_score,
                "output_path": str(output_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
