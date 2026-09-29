from __future__ import annotations

import json
import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from .db import Database, now
from .materials import sha256, verify_materials
from .ids import new_id
from .safety import authorize_submission as check_submission_approval
from .safety import new_approval_token, validate_fill_plan
from .status import transition_application


def start_application(db: Database, job_id: int, material_id: int) -> int:
    verify_materials(db, material_id)
    timestamp = now()
    with db.connect() as connection:
        material = connection.execute(
            "SELECT job_id, status FROM material_sets WHERE id=?", (material_id,)
        ).fetchone()
        if not material or material["job_id"] != job_id or material["status"] != "approved":
            raise ValueError("Application requires an approved material set for this job")
        job_snapshot = dict(connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
        try:
            cursor = connection.execute(
                "INSERT INTO applications(public_id, job_id, material_set_id, status, job_snapshot_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?) RETURNING id",
                (new_id("app"), job_id, material_id, "ready_for_review", json.dumps(job_snapshot, sort_keys=True), timestamp, timestamp),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("An application already exists for this job; historical snapshots are immutable") from error
        application_id = cursor.fetchone()["id"]
        for row in connection.execute("SELECT document_id, metadata_json FROM document_versions"):
            if json.loads(row["metadata_json"]).get("material_set_id") == material_id:
                connection.execute("UPDATE documents SET application_id=? WHERE id=?", (application_id, row["document_id"]))
        connection.execute(
            "INSERT INTO application_status_history(public_id, application_id, from_status, to_status, created_at) VALUES(?,?,?,?,?)",
            (new_id("ash"), application_id, None, "ready_for_review", timestamp),
        )
    db.event("application", application_id, "started", {"material_set_id": material_id})
    return application_id


def _answer_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _verify_run_binding(db: Database, run: Any) -> tuple[int, dict[str, Any]]:
    binding = json.loads(run["audit_json"])
    with db.connect() as connection:
        application = connection.execute(
            "SELECT job_id, material_set_id FROM applications WHERE id=?", (run["application_id"],)
        ).fetchone()
        latest_answer = connection.execute(
            "SELECT version, answers_json FROM application_answers WHERE application_id=? ORDER BY version DESC LIMIT 1",
            (run["application_id"],),
        ).fetchone()
    if not application or binding["job_id"] != application["job_id"] or binding["material_set_id"] != application["material_set_id"]:
        raise PermissionError("Application materials changed; prepare and approve a new run")
    if not latest_answer or latest_answer["version"] != binding["application_answers_version"] or _answer_hash(latest_answer["answers_json"]) != binding["application_answers_sha256"]:
        raise PermissionError("Application answers changed; prepare and approve a new run")
    verify_materials(db, application["material_set_id"])
    return application["material_set_id"], binding


def prepare_automation(
    db: Database, application_id: int, plan: dict[str, Any], verified_answers: dict[str, Any],
    classification_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    token = new_approval_token()
    with db.connect() as connection:
        app = connection.execute(
            "SELECT a.id, a.job_id, a.material_set_id, a.status, m.manifest_json FROM applications a "
            "JOIN material_sets m ON m.id=a.material_set_id WHERE a.id=? AND m.status='approved'",
            (application_id,),
        ).fetchone()
        if not app:
            raise ValueError("Application is missing or has no approved materials")
        manifest = json.loads(app["manifest_json"])
        folder = Path(manifest["path"])
        names = {item["name"] for item in manifest["files"]}
        document_answers: dict[str, str] = {}
        for name in ("resume.pdf", "resume.docx"):
            if name in names:
                document_answers.setdefault("resume_path", str((folder / name).resolve()))
        for name in ("cover-letter.pdf", "cover-letter.docx", "cover-letter.txt"):
            if name in names:
                document_answers.setdefault("cover_letter_path", str((folder / name).resolve()))
        verified_answers = {**verified_answers, **document_answers}
        checked = validate_fill_plan(plan, verified_answers, classification_overrides)
        answer_version = connection.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM application_answers WHERE application_id=?", (application_id,)
        ).fetchone()[0]
        answers_json = json.dumps(verified_answers, sort_keys=True)
        connection.execute(
            "INSERT INTO application_answers(public_id, application_id, version, answers_json, created_at) VALUES(?,?,?,?,?)",
            (new_id("aa"), application_id, answer_version, answers_json, now()),
        )
        binding = {
            "application_id": application_id,
            "job_id": app["job_id"],
            "material_set_id": app["material_set_id"],
            "application_answers_version": answer_version,
            "application_answers_sha256": _answer_hash(answers_json),
            "document_hashes": {item["name"]: item["sha256"] for item in manifest["files"]},
        }
        approved_files = {item["name"]: item["sha256"] for item in manifest["files"]}
        for field in checked["fields"]:
            if field.get("type") != "file":
                continue
            path = Path(field["value"]).expanduser().resolve()
            if path.name not in approved_files or not path.is_file() or sha256(path) != approved_files[path.name]:
                checked["stops"].append({"field": field.get("label"), "reason": "file_not_in_approved_materials"})
        if checked["stops"]:
            checked["fields"] = [field for field in checked["fields"] if field.get("type") != "file"]
        cursor = connection.execute(
            "INSERT INTO automation_runs(public_id, application_id, state, plan_json, approval_token, audit_json, started_at) VALUES(?,?,?,?,?,?,?)",
            (new_id("run"), application_id, "blocked" if checked["stops"] else "ready_for_fill", json.dumps(checked, sort_keys=True), token, json.dumps(binding, sort_keys=True), now()),
        )
        run_id = cursor.lastrowid
    audit = pre_submission_audit(db, run_id)
    return {
        "run_id": run_id,
        "state": "blocked" if checked["stops"] else "ready_for_fill",
        "fill_plan": checked,
        "submission_approval_token": token,
        "pre_submission_audit": audit,
        "instruction": "Fill only listed fields. Stop before submit. Token is valid only for this run.",
    }


def pre_submission_audit(db: Database, run_id: int) -> dict[str, Any]:
    with db.connect() as connection:
        row = connection.execute(
            "SELECT r.state, r.plan_json, r.audit_json, a.public_id AS application_public_id, "
            "j.company, j.title, m.public_id AS material_public_id "
            "FROM automation_runs r JOIN applications a ON a.id=r.application_id "
            "JOIN jobs j ON j.id=a.job_id JOIN material_sets m ON m.id=a.material_set_id WHERE r.id=?",
            (run_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"Automation run {run_id} not found")
    plan = json.loads(row["plan_json"])
    binding = json.loads(row["audit_json"])
    labels = {str(item.get("answer_key", "")) for item in plan["fields"]}
    approval = "APPROVED" if row["state"] == "authorized_to_submit" else "NOT_APPROVED"
    return {
        "company": row["company"], "role": row["title"], "application_id": row["application_public_id"],
        "personal_information": "PASS" if {"name", "email"} <= labels else "VERIFY",
        "resume": row["material_public_id"], "required_fields": "PASS" if not plan["stops"] else "BLOCKED",
        "unsupported_claims": 0, "unanswered_questions": len(plan["stops"]),
        "document_hashes": binding["document_hashes"], "approval_state": approval,
        "may_submit": approval == "APPROVED" and not plan["stops"],
    }


def authorize_submission(db: Database, run_id: int, token: str, confirmation: str) -> None:
    with db.connect() as connection:
        run = connection.execute(
            "SELECT id, application_id, state, approval_token, audit_json FROM automation_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not run or run["state"] != "ready_for_fill":
            raise ValueError("Automation run is not eligible for submission")
        check_submission_approval(run["approval_token"], token, confirmation)
    material_id, binding = _verify_run_binding(db, run)
    with db.connect() as connection:
        changed = connection.execute(
            "UPDATE automation_runs SET state='authorized_to_submit', approval_token=NULL WHERE id=? AND state='ready_for_fill'",
            (run_id,),
        ).rowcount
        if changed:
            connection.execute(
                "UPDATE applications SET approved_binding_json=?, approved_at=?, updated_at=? WHERE id=?",
                (json.dumps(binding, sort_keys=True), now(), now(), run["application_id"]),
            )
    if not changed:
        raise ValueError("Automation run changed before authorization")
    transition_application(db, run["application_id"], "approved", "Explicit per-run submission approval recorded")
    db.event("application", run["application_id"], "submission_authorized", {"run_id": run_id})


def record_submission(db: Database, run_id: int, receipt: dict[str, Any]) -> None:
    with db.connect() as connection:
        run = connection.execute(
            "SELECT id, application_id, state, audit_json FROM automation_runs WHERE id=?", (run_id,)
        ).fetchone()
        if not run or run["state"] != "authorized_to_submit":
            raise PermissionError("Submission was not explicitly authorized for this run")
    material_id, _ = _verify_run_binding(db, run)
    audit = pre_submission_audit(db, run_id)
    with db.connect() as connection:
        timestamp = now()
        connection.execute(
            "UPDATE automation_runs SET state='submitted', approval_token=NULL, finished_at=? WHERE id=?",
            (timestamp, run_id),
        )
        connection.execute(
            "UPDATE applications SET status='submitted', submitted_at=?, confirmation=?, updated_at=? WHERE id=?",
            (timestamp, json.dumps(receipt, sort_keys=True), timestamp, run["application_id"]),
        )
        connection.execute(
            "INSERT INTO application_status_history(public_id, application_id, from_status, to_status, created_at) VALUES(?,?,?,?,?)",
            (new_id("ash"), run["application_id"], "approved", "submitted", timestamp),
        )
        connection.execute(
            "INSERT INTO submission_attempts(public_id, application_id, automation_run_id, state, audit_json, confirmation_json, created_at, finished_at) VALUES(?,?,?,?,?,?,?,?)",
            (new_id("sub"), run["application_id"], run_id, "submitted", json.dumps(audit, sort_keys=True), json.dumps(receipt, sort_keys=True), timestamp, timestamp),
        )
        connection.execute(
            "UPDATE material_sets SET status='submitted' WHERE id=(SELECT material_set_id FROM applications WHERE id=?)",
            (run["application_id"],),
        )
    db.event("application", run["application_id"], "submission_recorded", receipt)


def history(db: Database, application_id: int) -> dict[str, Any]:
    with db.connect() as connection:
        application = connection.execute(
            "SELECT a.*, j.company, j.title, j.description, m.version, m.manifest_json "
            "FROM applications a JOIN jobs j ON j.id=a.job_id "
            "LEFT JOIN material_sets m ON m.id=a.material_set_id WHERE a.id=?",
            (application_id,),
        ).fetchone()
        events = connection.execute(
            "SELECT event_type, data_json, created_at FROM events WHERE entity_type='application' AND entity_id=? ORDER BY id",
            (application_id,),
        ).fetchall()
        preparations = connection.execute(
            "SELECT id, kind, version, content_json, created_at FROM preparations WHERE application_id=? ORDER BY kind, version",
            (application_id,),
        ).fetchall()
        answers = connection.execute(
            "SELECT public_id, version, answers_json, created_at FROM application_answers WHERE application_id=? ORDER BY version",
            (application_id,),
        ).fetchall()
        interviews = connection.execute("SELECT * FROM interviews WHERE application_id=? ORDER BY id", (application_id,)).fetchall()
        followups = connection.execute("SELECT * FROM followups WHERE application_id=? ORDER BY id", (application_id,)).fetchall()
    if not application:
        raise ValueError(f"Application {application_id} not found")
    result = dict(application)
    result["manifest"] = json.loads(result.pop("manifest_json")) if result.get("manifest_json") else None
    result["events"] = [{**dict(row), "data": json.loads(row["data_json"])} for row in events]
    for item in result["events"]:
        item.pop("data_json")
    result["preparations"] = [
        {**dict(row), "content": json.loads(row["content_json"])} for row in preparations
    ]
    for item in result["preparations"]:
        item.pop("content_json")
    result["application_answers"] = [
        {"public_id": row["public_id"], "version": row["version"], "answers": json.loads(row["answers_json"]), "created_at": row["created_at"]}
        for row in answers
    ]
    result["interviews"] = [dict(row) for row in interviews]
    result["followups"] = [dict(row) for row in followups]
    return result


def preparation_packet(db: Database, application_id: int, kind: str) -> dict[str, Any]:
    if kind not in {"interview", "followup"}:
        raise ValueError("Preparation kind must be interview or followup")
    saved = history(db, application_id)
    return {
        "kind": kind,
        "instructions": "Use only this saved application record. Flag unknowns instead of inventing details.",
        "application": saved,
        "requested_output": (
            ["role themes", "verified STAR stories", "questions to ask", "risk areas"]
            if kind == "interview"
            else ["concise message", "specific role reference", "next-step request"]
        ),
    }


def save_preparation(db: Database, application_id: int, kind: str, content: dict[str, Any]) -> dict[str, Any]:
    if kind not in {"interview", "followup"}:
        raise ValueError("Preparation kind must be interview or followup")
    with db.connect() as connection:
        exists = connection.execute("SELECT id FROM applications WHERE id=?", (application_id,)).fetchone()
        if not exists:
            raise ValueError(f"Application {application_id} not found")
        version = connection.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM preparations WHERE application_id=? AND kind=?",
            (application_id, kind),
        ).fetchone()["version"]
        cursor = connection.execute(
            "INSERT INTO preparations(public_id, application_id, kind, version, content_json, created_at) VALUES(?,?,?,?,?,?)",
            (new_id("prep"), application_id, kind, version, json.dumps(content, sort_keys=True), now()),
        )
        preparation_id = cursor.lastrowid
    db.event("application", application_id, "preparation_saved", {"kind": kind, "version": version})
    return {"id": preparation_id, "application_id": application_id, "kind": kind, "version": version}
