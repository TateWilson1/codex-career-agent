from __future__ import annotations

from typing import Any
import json

from .db import Database, now
from .ids import new_id


AUTO_KEYS = {"name", "email", "phone", "location", "education", "employment", "certifications", "expected_graduation", "work_authorization", "resume_path", "cover_letter_path"}
VERIFY_KEYS = {"salary", "relocation", "start_date", "travel", "sponsorship", "security_clearance", "technical_question"}


def classify_question(answer_key: str, field_type: str = "text", *, verified: bool = False) -> str:
    if field_type in {"legal_attestation", "consent", "demographic", "disability", "veteran", "criminal_history"}:
        return "USER_REQUIRED"
    if answer_key in AUTO_KEYS and verified:
        return "AUTO"
    if answer_key in VERIFY_KEYS:
        return "VERIFY"
    return "USER_REQUIRED"


def classify_answers(fields: list[dict[str, Any]], verified_keys: set[str], overrides: dict[str, str] | None = None) -> list[dict[str, Any]]:
    overrides = overrides or {}
    if set(overrides.values()) - {"AUTO", "VERIFY", "USER_REQUIRED"}:
        raise ValueError("Classification overrides must be AUTO, VERIFY, or USER_REQUIRED")
    return [
        {**field, "classification": overrides.get(str(field.get("answer_key", "")), classify_question(
            str(field.get("answer_key", "")), str(field.get("type", "text")),
            verified=field.get("answer_key") in verified_keys,
        ))}
        for field in fields
    ]


def save_answer(db: Database, key: str, value: Any, classification: str, provenance: str) -> dict[str, Any]:
    if classification not in {"AUTO", "VERIFY", "USER_REQUIRED"}:
        raise ValueError("Invalid answer classification")
    timestamp = now()
    public_id = new_id("ans")
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO answer_vault(public_id,answer_key,value_json,classification,verified,provenance,updated_at) VALUES(?,?,?,?,1,?,?) "
            "ON CONFLICT(answer_key) DO UPDATE SET value_json=excluded.value_json,classification=excluded.classification,verified=1,provenance=excluded.provenance,updated_at=excluded.updated_at",
            (public_id, key, json.dumps(value, sort_keys=True), classification, provenance, timestamp),
        )
    return {"answer_key": key, "classification": classification, "verified": True}


def verified_answers(db: Database) -> dict[str, Any]:
    with db.connect() as connection:
        rows = connection.execute("SELECT answer_key,value_json FROM answer_vault WHERE verified=1").fetchall()
    return {row["answer_key"]: json.loads(row["value_json"]) for row in rows}


def list_answers(db: Database) -> list[dict[str, Any]]:
    with db.connect() as connection:
        rows = connection.execute("SELECT public_id,answer_key,value_json,classification,verified,provenance,updated_at FROM answer_vault ORDER BY answer_key").fetchall()
    return [{**dict(row), "value": json.loads(row["value_json"])} for row in rows]
