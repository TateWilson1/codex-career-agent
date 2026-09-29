from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    configured = os.environ.get("JOB_AGENT_DATA") or os.environ.get("CODEX_CAREER_DATA") or "user-data"
    path = Path(configured).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "career.db"


def artifacts_dir() -> Path:
    path = data_dir() / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path
