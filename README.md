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

The daily runner now prefers these intake files in order when `JOB_AGENT_JOBS_FILE` is not set:

- `data/handshake_enriched_jobs.json`
- `data/handshake_targeted_jobs.json`
- `data/handshake_live_jobs.json`
- `handshake_selected_job_sample.json`

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

## Local queued-job submit runner

The cloud cron can now discover, score, queue, and sync jobs accurately, but true Handshake submission still needs a signed-in local browser session.

For the smoothest day-to-day use on Windows, use the helper launchers in `scripts\`:

```powershell
scripts\bootstrap_handshake_login.cmd
scripts\run_local_queue_submit.cmd 25
scripts\run_local_daily_cycle.cmd 25
```

They do three different jobs:

- `bootstrap_handshake_login.cmd` opens the persistent local Handshake browser profile so you can sign in once
- `run_local_queue_submit.cmd 25` attempts up to 25 currently queued Handshake-hosted jobs and syncs the results back to the sheet
- `run_local_daily_cycle.cmd 25` runs the full local cycle: intake refresh, queue update, local submit pass, and final full-state sheet resync

Use the local queued-job runner to submit `queued` Handshake-hosted jobs from your machine:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.local_submit --limit 15
```

The first time, a local Chromium window will open using a persistent profile under `data/handshake_browser_profile`. Sign into Handshake there once. After that, the runner can reuse that local session for future queued jobs.

Optional flags:

- `--headless` to reuse the saved browser session without opening a visible window
- `--limit 15` to cap how many queued jobs to attempt in one pass
- `--user-data-dir data/handshake_browser_profile` to choose a different persistent browser profile

The local submit runner will:

- read queued Handshake-hosted jobs from `data/state.json`
- attempt to submit them in the local browser
- change successfully submitted jobs to `applied`
- keep session-blocked jobs as `queued`
- sync updated rows back to the Google Sheet webhook

If you want one command that runs the full local cycle:

- merge the latest Handshake intake files
- score and queue jobs into local state
- run a local Handshake submit pass
- push the final full-state view back to Google Sheets

use:

```powershell
C:\Users\ttamb\AppData\Local\Programs\Python\Python313\python.exe -m job_agent.local_daily_cycle --submit-limit 25
```

or, more simply:

```powershell
scripts\run_local_daily_cycle.cmd 25
```

Optional flags:

- `--headless` after your local Handshake browser profile is already signed in
- `--submit-limit 25` to control how many queued jobs the local browser should attempt in one pass

If you want to force the entire current local state back into the sheet at once:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.sync_state_to_sheet
```

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

When present, the runner will now automatically prefer the locally prepared enriched or targeted Handshake batches over the old one-job sample file.

The current cloud result payload now includes an `application_plan` per job with:

- `next_action`
- `can_auto_submit`
- `blockers`
- `required_documents`

The current decision layer is designed to behave like this:

- Handshake internal + high-confidence + no blockers -> `full_submit`
- Handshake external -> `review_external`
- Cover letter required -> `skip`
- Unsupported document requirements -> review or skip depending on blockers

Each cloud run now also emits a compact `summary` that separates:

- `submitted_count`
- `queued_count`
- `review_count`
- `skipped_count`
- `internal_ready_count`
- `unknown_method_count`
- `submitted_target_gap`
- `qualified_volume_gap`

This makes it easier to see whether the run actually reached the true submit target, or only reached enough qualified volume.

## Spreadsheet webhook sync

The cloud runner can push processed tracking rows to a sheet webhook after each run.

Set these environment variables in Render:

- `JOB_AGENT_TRACKING_WEBHOOK_URL`
- `JOB_AGENT_TRACKING_WEBHOOK_SECRET` (optional, sent as `?secret=...`)
- `JOB_AGENT_TRACKING_TIMEOUT_SECONDS` (optional, defaults to `30`)

The runner posts a JSON payload containing:

- run metadata
- `jobs_seen`
- `jobs_written`
- `rows`, where each row includes:
  - `job_id`
  - `company`
  - `role`
  - `status`
  - `decision`
  - `score`
  - `sheet_name`
  - `sheet_row` with columns `A` through `F`

This is a good fit for a Google Apps Script web app that upserts rows into the `Applied` sheet by `job_id`.

A ready-to-paste Apps Script webhook is included at `google_apps_script/tracking_webhook.gs`. It is designed to:

- keep `Job ID` in column `G`
- update an existing row when the same `job_id` appears again
- append a new row only when the `job_id` is new
- normalize malformed statuses such as `appliedCheckin/Review` back to `applied`

To generate a sample webhook payload locally for verification:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.emit_tracking_payload --out data/tracking_webhook_sample.json
```

If you want the sample payload to mark eligible internal jobs as applied:

```powershell
& 'C:\Users\ttamb\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m job_agent.emit_tracking_payload --mark-applied --out data/tracking_webhook_applied_sample.json
```

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

Today, `queued` specifically means the job is qualified and ready, but the run still needs a signed-in live browser session before it can truly submit.

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
