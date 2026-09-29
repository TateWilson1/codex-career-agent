from __future__ import annotations

from .db import Database, now
from .ids import new_id


TRANSITIONS = {
    "discovered": {"reviewing", "closed"},
    "reviewing": {"shortlisted", "closed"},
    "shortlisted": {"preparing", "withdrawn"},
    "preparing": {"ready_for_review", "withdrawn"},
    "ready_for_review": {"approved", "preparing", "withdrawn"},
    "approved": {"in_progress", "submitted", "preparing", "withdrawn"},
    "in_progress": {"submitted", "withdrawn"},
    "submitted": {"screening", "interview", "rejected", "withdrawn", "closed"},
    "screening": {"interview", "rejected", "withdrawn", "closed"},
    "interview": {"final_interview", "offer", "rejected", "withdrawn"},
    "final_interview": {"offer", "rejected", "withdrawn"},
    "offer": {"closed", "withdrawn"},
    "rejected": {"closed"},
    "withdrawn": {"closed"},
    "closed": set(),
}


def transition_application(db: Database, application_id: int, to_status: str, note: str = "") -> None:
    timestamp = now()
    with db.connect() as connection:
        row = connection.execute("SELECT status FROM applications WHERE id=?", (application_id,)).fetchone()
        if not row:
            raise ValueError(f"Application {application_id} not found")
        current = row["status"]
        if to_status not in TRANSITIONS.get(current, set()):
            raise ValueError(f"Invalid application transition: {current} -> {to_status}")
        connection.execute("UPDATE applications SET status=?, updated_at=? WHERE id=?", (to_status, timestamp, application_id))
        connection.execute(
            "INSERT INTO application_status_history(public_id, application_id, from_status, to_status, note, created_at) VALUES(?,?,?,?,?,?)",
            (new_id("ash"), application_id, current, to_status, note, timestamp),
        )
