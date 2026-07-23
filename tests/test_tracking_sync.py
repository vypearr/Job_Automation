from __future__ import annotations

import json
import socket
import unittest
from unittest.mock import patch

from job_agent.tracking_sync import TrackingSyncConfig, sync_tracking_rows


def sample_result(row_count: int) -> dict:
    return {
        "run": {"run_id": "run-test"},
        "jobs_seen": row_count,
        "jobs_written": row_count,
        "results": [
            {
                "job": {
                    "id": f"job-{index}",
                    "company": "Example",
                    "title": f"Role {index}",
                    "url": f"https://example.com/{index}",
                    "application_url": "",
                    "status": "queued",
                },
                "decision": "review",
                "score": 50,
                "sheet_row": {"B": "Example", "C": f"Role {index}", "F": "queued"},
            }
            for index in range(row_count)
        ],
    }


class FakeResponse:
    status = 200

    def __init__(self, request):
        payload = json.loads(request.data.decode("utf-8"))
        self.row_count = len(payload["rows"])

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(
            {"appended": self.row_count, "updated": 0, "processed": self.row_count}
        ).encode("utf-8")


class TrackingSyncTests(unittest.TestCase):
    def test_syncs_rows_in_bounded_batches_and_aggregates_counts(self):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(request)

        config = TrackingSyncConfig("https://example.invalid/hook", timeout_seconds=7, batch_size=2)
        with patch("job_agent.tracking_sync.request.urlopen", side_effect=fake_urlopen):
            result = sync_tracking_rows(sample_result(5), config)

        self.assertTrue(result["synced"])
        self.assertEqual(result["batch_count"], 3)
        self.assertEqual(result["processed"], 5)
        self.assertEqual(result["appended"], 5)
        self.assertEqual([json.loads(call[0].data)["batch"]["size"] for call in calls], [2, 2, 1])
        self.assertEqual([call[1] for call in calls], [7, 7, 7])

    def test_continues_after_one_batch_times_out(self):
        call_count = 0

        def fake_urlopen(request, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise socket.timeout()
            return FakeResponse(request)

        config = TrackingSyncConfig("https://example.invalid/hook", batch_size=2)
        with patch("job_agent.tracking_sync.request.urlopen", side_effect=fake_urlopen):
            result = sync_tracking_rows(sample_result(5), config)

        self.assertFalse(result["synced"])
        self.assertEqual(result["successful_batch_count"], 2)
        self.assertEqual(result["failed_batch_count"], 1)
        self.assertEqual(result["processed"], 3)
        self.assertIn("batch 2", result["error"])


if __name__ == "__main__":
    unittest.main()
