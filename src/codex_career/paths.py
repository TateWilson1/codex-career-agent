from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    configured = os.environ.get("JOB_AGENT_DATA") or os.environ.get("CODEX_CAREER_DATA") or "user-data"
    path = Path(configured).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "career.db"


def config_path() -> Path:
    return data_dir() / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Private configuration must be a JSON object")
    return value


def save_config(value: dict[str, Any], path: Path | None = None) -> None:
    path = path or config_path()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def artifacts_dir() -> Path:
    path = data_dir() / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path
