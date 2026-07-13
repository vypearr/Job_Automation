# Robotics Job Agent

This project helps Tarun find robotics, embedded, firmware, controls, and adjacent software internships or jobs.

## What it does

- Loads a candidate profile derived from the resume
- Ingests job listings from JSON, CSV, or pasted text
- Scores each job against robotics-focused requirements
- Explains why a role is a fit, a stretch, or a bad match
- Recommends one of three actions: `auto_apply`, `review`, or `skip`
- Supports a volume-first gate: skip jobs that require a cover letter
- Distinguishes `internal` vs `external` application paths
- Exports spreadsheet-ready tracking rows
- Defines adapter interfaces for LinkedIn, Indeed, and Handshake automation

## Quick start

```powershell
cd C:\Users\ttamb\Documents\Codex\2026-07-13\im\work\robotics-job-agent
python -m job_agent.cli --jobs sample_jobs.json
```

To use the bundled runtime:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.cli --jobs sample_jobs.json
```

To also export tracking rows:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.cli --jobs sample_jobs.json --tracking-out tracking_export.csv
```

To import visible Handshake card labels into structured jobs:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.cli --jobs sample_jobs.json --handshake-labels handshake_visible_cards.txt --import-json-out handshake_imported.json --tracking-out handshake_tracking.csv
```

To import visible LinkedIn or Indeed labels:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.cli --jobs sample_jobs.json --platform-labels linkedin_visible_cards.txt --import-json-out linkedin_imported.json --tracking-out linkedin_tracking.csv
```

To run the scheduled cloud worker locally:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.daily_run
```

## Input formats

### JSON

`sample_jobs.json` shows the expected schema:

```json
[
  {
    "id": "job-1",
    "title": "Robotics Software Intern",
    "company": "Example Robotics",
    "location": "San Francisco, CA",
    "url": "https://example.com/job-1",
    "description": "Build robotics software using Python, C++, ROS, Linux, sensors, and testing."
  }
]
```

### CSV

The CSV file should include these headers:

- `id`
- `title`
- `company`
- `location`
- `url`
- `description`

## Candidate profile

The current profile is stored in `profile.json` and seeded from the attached resume. Update it as you gain new projects, coursework, and target roles.

## Live account automation

The current build includes adapter placeholders for:

- LinkedIn
- Indeed
- Handshake
- Greenhouse / Lever style hosted application flows

Before I wire live automation, we should connect one source at a time and decide whether the system should:

- only recommend and prefill
- open tabs for review
- submit automatically for high-confidence matches

The current profile is configured for:

- primary platform: `handshake`
- high-confidence action: `full_submit`
- strategy: `volume`
- daily target: `15` applications
- skip jobs requiring a cover letter
- transcript path stored for transcript-required roles

## Important note

Some job sites restrict fully automated applications. This project is designed so the matching engine is reusable even when the final submission step needs a manual confirmation.

## Render deployment

The repo now includes `render.yaml` for:

- one web service for the API
- one cron service for the recurring runner

The current cron runner processes a configured jobs file and persists decisions. It does not yet perform full cloud-native browser login automation for Handshake or LinkedIn.

## Account connection guidance

- GitHub profile URLs can be stored directly in `profile.json`, but private account access still requires a signed-in browser session or an API token.
- For Handshake, prefer connecting through the Codex in-app browser session where you sign in yourself. Do not paste your password into chat.
- For LinkedIn and Indeed, start with job discovery and tracking first, then layer in site-specific apply logic carefully because application surfaces vary widely.
- A practical rollout is:
  1. signed-in Handshake session
  2. scrape/search job cards
  3. filter by fit and document requirements
  4. auto-submit only high-confidence jobs with no cover letter requirement

## Daily automation target

The intended steady-state behavior is:

- check for new Handshake postings on a recurring schedule
- score for robotics, embedded, firmware, and mechatronics fit
- skip roles requiring a cover letter
- allow resume-only and resume-plus-transcript flows
- auto-submit high-confidence jobs until the daily count reaches `15`
- write tracked jobs into the `Applied` sheet layout
- mark successfully submitted jobs with status `applied`

The main operational limitation is session freshness. If Handshake signs out, the recurring flow should stop cleanly and wait for the next signed-in session rather than guessing through authentication.

Another important limitation is application surface fragmentation:

- `internal`: the full flow stays inside Handshake
- `external`: Handshake redirects to an employer ATS or company site

That means the eventual daily automation will likely be a hybrid:

- direct automation for Handshake-native applications
- site-specific adapters for recurring external ATS targets
- fallback review queue for rare or custom employer application flows

## Spreadsheet tracking rules

When the Google Sheet is connected:

- jobs that are successfully submitted should use `applied` in the status field
- jobs marked `Apply externally` or `External application` should stay in the `Applied` sheet with `Status = Checkin/Review`
- internal Handshake jobs can be tracked in the same sheet with status transitions such as `queued`, `Checkin/Review`, and `applied`
- the current `Applied` sheet layout is:
  - `Date Applied`
  - `Company`
  - `Role`
  - `Company Description / Role Description`
  - `Reply`
  - `Status`
