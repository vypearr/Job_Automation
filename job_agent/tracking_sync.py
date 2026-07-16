from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import socket
from urllib import parse
from urllib import error, request


@dataclass
class TrackingSyncConfig:
    webhook_url: str
    secret: str = ""
    timeout_seconds: int = 30


def parse_tracking_sync_response(response_text: str) -> dict[str, Any]:
    text = str(response_text or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_tracking_sync_config() -> TrackingSyncConfig | None:
    webhook_url = os.getenv("JOB_AGENT_TRACKING_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return None

    timeout_raw = os.getenv("JOB_AGENT_TRACKING_TIMEOUT_SECONDS", "30").strip()
    try:
        timeout_seconds = max(1, int(timeout_raw))
    except ValueError:
        timeout_seconds = 30

    return TrackingSyncConfig(
        webhook_url=webhook_url,
        secret=os.getenv("JOB_AGENT_TRACKING_WEBHOOK_SECRET", "").strip(),
        timeout_seconds=timeout_seconds,
    )


def build_tracking_sync_payload(result: dict[str, Any]) -> dict[str, Any]:
    run = dict(result.get("run", {}))
    rows: list[dict[str, Any]] = []

    for item in result.get("results", []):
        job = dict(item.get("job", {}))
        rows.append(
            {
                "job_id": job.get("id", ""),
                "company": job.get("company", ""),
                "role": job.get("title", ""),
                "job_url": job.get("url", ""),
                "application_url": job.get("application_url", ""),
                "sheet_name": "Applied",
                "status": job.get("status", ""),
                "decision": item.get("decision", ""),
                "score": item.get("score", 0),
                "sheet_row": dict(item.get("sheet_row", {})),
                "synced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            }
        )

    return {
        "run": run,
        "jobs_seen": result.get("jobs_seen", 0),
        "jobs_written": result.get("jobs_written", 0),
        "summary": dict(result.get("summary", {})),
        "rows": rows,
    }


def sync_tracking_rows(result: dict[str, Any], config: TrackingSyncConfig | None = None) -> dict[str, Any]:
    config = config or load_tracking_sync_config()
    if config is None:
        return {"enabled": False, "synced": False, "reason": "tracking webhook not configured"}

    payload = build_tracking_sync_payload(result)
    body = json.dumps(payload).encode("utf-8")
    webhook_url = config.webhook_url
    if config.secret:
        separator = "&" if "?" in webhook_url else "?"
        webhook_url = f"{webhook_url}{separator}secret={parse.quote(config.secret)}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "robotics-job-agent/0.1",
    }

    req = request.Request(webhook_url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as resp:
            response_text = resp.read().decode("utf-8", errors="replace")
            parsed = parse_tracking_sync_response(response_text)
            return {
                "enabled": True,
                "synced": True,
                "status_code": getattr(resp, "status", 200),
                "response_text": response_text[:1000],
                "row_count": len(payload["rows"]),
                "appended": int(parsed.get("appended", 0) or 0),
                "updated": int(parsed.get("updated", 0) or 0),
                "processed": int(parsed.get("processed", 0) or 0),
            }
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        return {
            "enabled": True,
            "synced": False,
            "status_code": exc.code,
            "error": response_text[:1000] or str(exc),
            "row_count": len(payload["rows"]),
        }
    except error.URLError as exc:
        return {
            "enabled": True,
            "synced": False,
            "error": str(exc.reason),
            "row_count": len(payload["rows"]),
        }
    except TimeoutError:
        return {
            "enabled": True,
            "synced": False,
            "error": f"tracking webhook timed out after {config.timeout_seconds}s",
            "row_count": len(payload["rows"]),
        }
    except socket.timeout:
        return {
            "enabled": True,
            "synced": False,
            "error": f"tracking webhook timed out after {config.timeout_seconds}s",
            "row_count": len(payload["rows"]),
        }
