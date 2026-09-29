from __future__ import annotations

import json
import importlib.util
import re
import shutil
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Any

from .db import Database


REQUIRED_IGNORES = ("user-data/", ".env", "credentials/", "tokens/", "browser-profiles/")
SENSITIVE_SUFFIXES = {".docx", ".pdf", ".db", ".sqlite", ".pem", ".key"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "api_token": re.compile(r"(?:github_pat_|ghp_|sk-)[A-Za-z0-9_-]{16,}"),
    "non_fixture_email": re.compile(r"\b[\w.+-]+@(?!example\.test\b)[\w.-]+\.[A-Za-z]{2,}\b"),
}


def run_doctor(project_root: Path, data_root: Path, db: Database) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    ignore_path = project_root / ".gitignore"
    ignore_text = ignore_path.read_text(encoding="utf-8") if ignore_path.is_file() else ""
    missing = [item for item in REQUIRED_IGNORES if item not in ignore_text]
    checks.append({"name": "privacy_ignores", "status": "PASS" if not missing else "FAIL", "details": missing})

    tracked: list[str] = []
    try:
        result = subprocess.run(
            ["git", "ls-files"], cwd=project_root, text=True, capture_output=True, timeout=5, check=False
        )
        tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        suspects = [
            item for item in tracked
            if item.startswith(("user-data/", "data/", "credentials/", "tokens/", "browser-profiles/"))
            or (Path(item).suffix.lower() in SENSITIVE_SUFFIXES and not item.startswith("examples/"))
        ]
        checks.append({"name": "tracked_private_files", "status": "PASS" if not suspects else "FAIL", "details": suspects})
        indicators = []
        for item in tracked:
            path = project_root / item
            if not path.is_file() or path.stat().st_size > 200_000:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            indicators.extend({"path": item, "indicator": name} for name, pattern in SECRET_PATTERNS.items() if pattern.search(content))
        checks.append({"name": "tracked_secret_indicators", "status": "PASS" if not indicators else "FAIL", "details": indicators})
    except (OSError, subprocess.SubprocessError) as error:
        checks.append({"name": "tracked_private_files", "status": "WARN", "details": str(error)})

    try:
        with closing(sqlite3.connect(db.path)) as connection:
            connection.execute("SELECT 1").fetchone()
        checks.append({"name": "database", "status": "PASS", "details": {"path": str(db.path), "schema": db.schema_version}})
    except sqlite3.Error as error:
        checks.append({"name": "database", "status": "FAIL", "details": str(error)})

    config_path = data_root / "config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if config.get("default_tailoring_mode", "STANDARD") not in {"LIGHT", "STANDARD", "DEEP"}:
                raise ValueError("default_tailoring_mode must be LIGHT, STANDARD, or DEEP")
            pages = config.get("target_resume_pages", 1)
            if not isinstance(pages, int) or pages < 1:
                raise ValueError("target_resume_pages must be a positive integer")
            checks.append({"name": "configuration", "status": "PASS", "details": str(config_path)})
        except (json.JSONDecodeError, ValueError) as error:
            checks.append({"name": "configuration", "status": "FAIL", "details": str(error)})
    else:
        checks.append({"name": "configuration", "status": "WARN", "details": "Run job-agent setup to create config.json"})

    missing_modules = [name for name in ("docx", "pypdf", "reportlab") if importlib.util.find_spec(name) is None]
    checks.append({"name": "python_dependencies", "status": "PASS" if not missing_modules else "FAIL", "details": missing_modules})
    node = shutil.which("node")
    mcp_example = project_root / "config" / "playwright-mcp.toml.example"
    browser_status = "PASS" if node and mcp_example.is_file() else "WARN"
    checks.append({"name": "browser_mcp", "status": browser_status, "details": {"node": node, "config_example": str(mcp_example) if mcp_example.is_file() else None}})

    status = "FAIL" if any(item["status"] == "FAIL" for item in checks) else "PASS"
    return {"status": status, "safeguard_not_guarantee": True, "checks": checks}
