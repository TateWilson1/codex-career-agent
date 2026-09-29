from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .applications import record_submission
from .db import Database
from .materials import sha256


class ApplicationBrowser(Protocol):
    def fill(self, db: Database, run_id: int) -> dict[str, Any]: ...
    def submit(self, db: Database, run_id: int) -> dict[str, Any]: ...


@dataclass
class SyntheticATSAdapter:
    """Deterministic test adapter for the checked-in synthetic ATS contract."""

    fixture: Path
    filled: dict[str, Any] = field(default_factory=dict)
    uploaded: dict[str, str] = field(default_factory=dict)

    def fill(self, db: Database, run_id: int) -> dict[str, Any]:
        if not self.fixture.is_file():
            raise ValueError("Synthetic ATS fixture is missing")
        with db.connect() as connection:
            run = connection.execute("SELECT state, plan_json FROM automation_runs WHERE id=?", (run_id,)).fetchone()
        if not run or run["state"] not in {"ready_for_fill", "authorized_to_submit"}:
            raise PermissionError("Run is not ready for safe filling")
        plan = json.loads(run["plan_json"])
        if plan["stops"]:
            raise PermissionError("Unsupported questions require user intervention")
        for item in plan["fields"]:
            if item.get("type") == "file":
                path = Path(item["value"])
                self.uploaded[item["answer_key"]] = sha256(path)
            else:
                self.filled[item["answer_key"]] = item["value"]
        return {"filled": dict(self.filled), "uploaded": dict(self.uploaded), "stopped_before_submit": True}

    def submit(self, db: Database, run_id: int) -> dict[str, Any]:
        with db.connect() as connection:
            run = connection.execute("SELECT state FROM automation_runs WHERE id=?", (run_id,)).fetchone()
        if not run or run["state"] != "authorized_to_submit":
            raise PermissionError("Synthetic ATS submission requires explicit approval")
        receipt = {"confirmation_number": f"SYN-{run_id:04d}", "confirmation_text": "Application received", "fixture": self.fixture.name}
        record_submission(db, run_id, receipt)
        return receipt
