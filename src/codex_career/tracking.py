from __future__ import annotations

from typing import Any

from .db import Database, now
from .ids import new_id


def add_contact(db: Database, company_id: int, name: str, email: str = "", role: str = "", notes: str = "") -> dict[str, Any]:
    timestamp = now()
    with db.connect() as connection:
        if not connection.execute("SELECT 1 FROM companies WHERE id=?", (company_id,)).fetchone():
            raise ValueError(f"Company {company_id} not found")
        public_id = new_id("con")
        row_id = connection.execute(
            "INSERT INTO contacts(public_id,company_id,name,email,role,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) RETURNING id",
            (public_id, company_id, name, email, role, notes, timestamp, timestamp),
        ).fetchone()["id"]
    return {"id": row_id, "public_id": public_id}


def add_interview(db: Database, application_id: int, stage: str, scheduled_at: str | None = None, notes: str = "") -> dict[str, Any]:
    timestamp = now()
    with db.connect() as connection:
        if not connection.execute("SELECT 1 FROM applications WHERE id=?", (application_id,)).fetchone():
            raise ValueError(f"Application {application_id} not found")
        public_id = new_id("int")
        row_id = connection.execute(
            "INSERT INTO interviews(public_id,application_id,stage,scheduled_at,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?) RETURNING id",
            (public_id, application_id, stage, scheduled_at, notes, timestamp, timestamp),
        ).fetchone()["id"]
    db.event("application", application_id, "interview_scheduled", {"interview_id": public_id, "stage": stage, "scheduled_at": scheduled_at})
    return {"id": row_id, "public_id": public_id}


def add_followup(db: Database, application_id: int, kind: str, due_at: str | None = None, content: str = "") -> dict[str, Any]:
    timestamp = now()
    with db.connect() as connection:
        if not connection.execute("SELECT 1 FROM applications WHERE id=?", (application_id,)).fetchone():
            raise ValueError(f"Application {application_id} not found")
        public_id = new_id("fol")
        row_id = connection.execute(
            "INSERT INTO followups(public_id,application_id,kind,due_at,content,created_at,updated_at) VALUES(?,?,?,?,?,?,?) RETURNING id",
            (public_id, application_id, kind, due_at, content, timestamp, timestamp),
        ).fetchone()["id"]
    db.event("application", application_id, "followup_planned", {"followup_id": public_id, "kind": kind, "due_at": due_at})
    return {"id": row_id, "public_id": public_id}


def update_record_status(db: Database, table: str, record_id: int, status: str) -> None:
    allowed = {"interviews": {"scheduled", "completed", "cancelled"}, "followups": {"planned", "sent", "cancelled"}}
    if table not in allowed or status not in allowed[table]:
        raise ValueError("Invalid tracking status")
    with db.connect() as connection:
        changed = connection.execute(f"UPDATE {table} SET status=?, updated_at=? WHERE id=?", (status, now(), record_id)).rowcount
    if not changed:
        raise ValueError(f"{table[:-1].title()} {record_id} not found")


def list_records(db: Database, table: str, application_id: int | None = None) -> list[dict[str, Any]]:
    if table not in {"contacts", "interviews", "followups"}:
        raise ValueError("Invalid tracking table")
    query = f"SELECT * FROM {table}"
    values: tuple[int, ...] = ()
    if application_id is not None and table != "contacts":
        query += " WHERE application_id=?"
        values = (application_id,)
    query += " ORDER BY id DESC"
    with db.connect() as connection:
        return [dict(row) for row in connection.execute(query, values)]
