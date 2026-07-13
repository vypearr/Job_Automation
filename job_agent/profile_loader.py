from __future__ import annotations

import json
from pathlib import Path

from .models import CandidateProfile


def load_profile(profile_path: str | Path) -> CandidateProfile:
    data = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    return CandidateProfile(**data)
