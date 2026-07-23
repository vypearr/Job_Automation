from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from job_agent.local_submit import queue_priority, resolve_document_path


class LocalSubmitTests(unittest.TestCase):
    def test_confirmed_internal_jobs_sort_before_unknown_jobs(self):
        internal = SimpleNamespace(application_method="internal", score=20, created_at="2026-01-02")
        unknown = SimpleNamespace(application_method="unknown", score=100, created_at="2026-01-01")
        ordered = sorted([unknown, internal], key=queue_priority)
        self.assertIs(ordered[0], internal)

    def test_document_path_resolves_repo_relative_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            transcript = base_dir / "data" / "documents" / "Transcript.pdf"
            transcript.parent.mkdir(parents=True)
            transcript.write_bytes(b"%PDF-test")
            resolved = resolve_document_path(base_dir, "data/documents/Transcript.pdf")
            self.assertEqual(resolved, transcript.resolve())


if __name__ == "__main__":
    unittest.main()
