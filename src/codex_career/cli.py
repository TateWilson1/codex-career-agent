from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .applications import authorize_submission, history, pre_submission_audit, preparation_packet, prepare_automation, record_submission, save_preparation, start_application
from .answers import classify_answers, list_answers, save_answer, verified_answers
from .analytics import search_analytics
from .db import Database
from .doctor import run_doctor
from .jobs import JOB_STATUSES, evaluate_jobs, import_jobs, read_jobs, record_search_run, scan_sources, update_status
from .materials import approve_materials, build_materials, tailoring_packet
from .paths import artifacts_dir, config_path, data_dir, database_path, load_config
from .profile import extract_resume_text, load_profile, onboarding_packet, preserve_resume, resume_hints, save_profile
from .sources import adapter_names, discover, source_capability
from .status import TRANSITIONS, transition_application
from .tracking import add_contact, add_followup, add_interview, list_records, update_record_status


def read_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def output(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def interactive_profile(hints: dict[str, Any]) -> dict[str, Any]:
    def ask(label: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        return input(f"{label}{suffix}: ").strip() or default

    def items(label: str, default: list[str] | None = None) -> list[str]:
        return [item.strip() for item in ask(label, ", ".join(default or [])).split(",") if item.strip()]

    return {
        "name": ask("Name", hints.get("name", "")),
        "email": ask("Email", hints.get("email", "")),
        "phone": ask("Phone", hints.get("phone", "")),
        "target_roles": items("Target roles, comma-separated", hints.get("target_roles")),
        "career_field": ask("Career field", hints.get("career_field", "")),
        "career_level": ask("Career level or seniority", hints.get("career_level", "")),
        "locations": items("Preferred locations, comma-separated", hints.get("locations")),
        "work_authorization": ask("Work authorization"),
        "skills": items("Verified skills, comma-separated"),
        "links": items("Professional links, comma-separated"),
        "experience": [],
        "education": [],
        "certifications": [],
        "preferences": {
            "work_modes": items("Preferred work modes (remote, hybrid, on-site)"),
            "radius_miles": ask("Geographic radius in miles"),
            "relocation": ask("Relocation preference"),
            "employment_types": items("Employment types (full-time, internship, contract, etc.)"),
            "salary": ask("Salary preference (optional)"),
            "travel": ask("Travel preference"),
            "sponsorship": ask("Sponsorship needs"),
            "industries": items("Preferred industries"),
            "companies": items("Preferred companies"),
            "hard_exclusions": items("Hard exclusions"),
            "career_goals": ask("Optional career goals"),
        },
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="job-agent", description="Local-first career management")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create the private data store")

    for name in ("setup", "onboard"):
        onboard = commands.add_parser(name, help="Create or replace the career profile")
        onboard.add_argument("--resume", type=Path)
        onboard.add_argument("--answers", type=Path)
        onboard.add_argument("--confirm-reviewed", action="store_true")
        onboard.add_argument("--preset", help="Preset name from presets/ or a JSON path")
    packet_command = commands.add_parser("onboarding-packet", help="Prepare a resume for fact-only Codex extraction")
    packet_command.add_argument("resume", type=Path)
    packet_command.add_argument("--out", type=Path, required=True)

    profile_command = commands.add_parser("profile", help="Review the current profile and its versions")
    profile_sub = profile_command.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("show")
    profile_sub.add_parser("versions")

    jobs = commands.add_parser("jobs", help="Import, evaluate, and list jobs")
    jobs_sub = jobs.add_subparsers(dest="jobs_command", required=True)
    jobs_import = jobs_sub.add_parser("import")
    jobs_import.add_argument("path", type=Path)
    jobs_import.add_argument("--source", default="manual")
    jobs_add = jobs_sub.add_parser("add", help="Add a pasted/manual job without fetching its URL")
    jobs_add.add_argument("--company", required=True)
    jobs_add.add_argument("--title", required=True)
    jobs_add.add_argument("--url", default="")
    jobs_add.add_argument("--location", default="")
    description_group = jobs_add.add_mutually_exclusive_group(required=True)
    description_group.add_argument("--description")
    description_group.add_argument("--description-file", type=Path)
    jobs_discover = jobs_sub.add_parser("discover")
    jobs_discover.add_argument("provider", choices=adapter_names())
    jobs_discover.add_argument("account", help="Public board token or site name")
    jobs_discover.add_argument("--company")
    jobs_evaluate = jobs_sub.add_parser("evaluate")
    jobs_evaluate.add_argument("job_id", nargs="?", type=int)
    jobs_sub.add_parser("scan", help="Scan every automated source in the private configuration")
    jobs_show = jobs_sub.add_parser("show")
    jobs_show.add_argument("job_id", type=int)
    jobs_status = jobs_sub.add_parser("status")
    jobs_status.add_argument("job_id", type=int)
    jobs_status.add_argument("status", choices=sorted(JOB_STATUSES))
    jobs_list = jobs_sub.add_parser("list")
    jobs_list.add_argument("--status")

    tailor = commands.add_parser("tailor", help="Prepare and validate tailoring work")
    tailor_sub = tailor.add_subparsers(dest="tailor_command", required=True)
    packet = tailor_sub.add_parser("packet")
    packet.add_argument("job_id", type=int)
    packet.add_argument("--out", type=Path)
    packet.add_argument("--mode", choices=("LIGHT", "STANDARD", "DEEP"), default="STANDARD")
    build = tailor_sub.add_parser("build")
    build.add_argument("job_id", type=int)
    build.add_argument("proposal", type=Path)
    build.add_argument("--pdf", action="store_true")
    build.add_argument("--confirm-truthful", action="store_true")

    materials = commands.add_parser("materials", help="Approve immutable application materials")
    materials_sub = materials.add_subparsers(dest="materials_command", required=True)
    approve = materials_sub.add_parser("approve")
    approve.add_argument("material_id", type=int)

    applications = commands.add_parser("applications", help="Track applications and saved history")
    applications_sub = applications.add_subparsers(dest="applications_command", required=True)
    applications_sub.add_parser("list")
    start = applications_sub.add_parser("start")
    start.add_argument("job_id", type=int)
    start.add_argument("material_id", type=int)
    show = applications_sub.add_parser("show")
    show.add_argument("application_id", type=int)
    prep = applications_sub.add_parser("prep")
    prep.add_argument("application_id", type=int)
    prep.add_argument("kind", choices=("interview", "followup"))
    prep.add_argument("--out", type=Path)
    save_prep = applications_sub.add_parser("save-prep")
    save_prep.add_argument("application_id", type=int)
    save_prep.add_argument("kind", choices=("interview", "followup"))
    save_prep.add_argument("content", type=Path)
    app_status = applications_sub.add_parser("status")
    app_status.add_argument("application_id", type=int)
    app_status.add_argument("status", choices=sorted(TRANSITIONS))
    app_status.add_argument("--note", default="")

    automation = commands.add_parser("automation", help="Prepare safe browser-assisted filling")
    automation_sub = automation.add_subparsers(dest="automation_command", required=True)
    prepare = automation_sub.add_parser("prepare")
    prepare.add_argument("application_id", type=int)
    prepare.add_argument("plan", type=Path)
    prepare.add_argument("answers", type=Path, nargs="?")
    prepare.add_argument("--confirm-answers", action="store_true", help="Confirm the supplied per-application answers were reviewed")
    authorize = automation_sub.add_parser("authorize")
    authorize.add_argument("run_id", type=int)
    authorize.add_argument("--token", required=True)
    authorize.add_argument("--confirm", required=True)
    submit = automation_sub.add_parser("record-submission")
    submit.add_argument("run_id", type=int)
    submit.add_argument("--receipt", type=Path, required=True)
    audit = automation_sub.add_parser("audit")
    audit.add_argument("run_id", type=int)
    commands.add_parser("doctor", help="Check privacy, configuration, and local storage safeguards")
    commands.add_parser("analytics", help="Summarize search outcomes and recurring gaps")
    gui = commands.add_parser("gui", help="Open the local visual career command center")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")

    answers = commands.add_parser("answers", help="Manage reviewed reusable application answers").add_subparsers(dest="answers_command", required=True)
    answers.add_parser("list")
    answer_set = answers.add_parser("set")
    answer_set.add_argument("answer_key")
    answer_set.add_argument("value", help="A JSON value or plain string")
    answer_set.add_argument("--classification", choices=("AUTO", "VERIFY", "USER_REQUIRED"), default="VERIFY")
    answer_set.add_argument("--confirm-verified", action="store_true")
    answer_classify = answers.add_parser("classify")
    answer_classify.add_argument("fields", type=Path)

    contacts = commands.add_parser("contacts", help="Track recruiter and company contacts").add_subparsers(dest="contacts_command", required=True)
    contacts.add_parser("list")
    contact_add = contacts.add_parser("add")
    contact_add.add_argument("company_id", type=int)
    contact_add.add_argument("--name", required=True)
    contact_add.add_argument("--email", default="")
    contact_add.add_argument("--role", default="")
    contact_add.add_argument("--notes", default="")

    interviews = commands.add_parser("interviews", help="Track interview stages and schedules").add_subparsers(dest="interviews_command", required=True)
    interview_list = interviews.add_parser("list")
    interview_list.add_argument("--application-id", type=int)
    interview_add = interviews.add_parser("add")
    interview_add.add_argument("application_id", type=int)
    interview_add.add_argument("--stage", required=True)
    interview_add.add_argument("--scheduled-at")
    interview_add.add_argument("--notes", default="")
    interview_status = interviews.add_parser("status")
    interview_status.add_argument("interview_id", type=int)
    interview_status.add_argument("status", choices=("scheduled", "completed", "cancelled"))

    followups = commands.add_parser("followups", help="Track application follow-ups and deadlines").add_subparsers(dest="followups_command", required=True)
    followup_list = followups.add_parser("list")
    followup_list.add_argument("--application-id", type=int)
    followup_add = followups.add_parser("add")
    followup_add.add_argument("application_id", type=int)
    followup_add.add_argument("--kind", required=True)
    followup_add.add_argument("--due-at")
    followup_add.add_argument("--content", default="")
    followup_status = followups.add_parser("status")
    followup_status.add_argument("followup_id", type=int)
    followup_status.add_argument("status", choices=("planned", "sent", "cancelled"))
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    db = Database(database_path())
    try:
        if args.command == "init":
            output({"database": str(db.path), "artifacts": str(artifacts_dir())})
        elif args.command in {"setup", "onboard"}:
            hints: dict[str, Any] = {}
            if args.preset:
                preset_path = Path(args.preset)
                if not preset_path.is_file():
                    preset_path = Path(__file__).resolve().parents[2] / "presets" / f"{args.preset}.json"
                hints.update(read_json(str(preset_path)))
            if args.resume:
                hints.update(resume_hints(extract_resume_text(args.resume)))
            if args.answers and not args.confirm_reviewed:
                raise ValueError("Importing a profile file requires --confirm-reviewed")
            payload = read_json(str(args.answers)) if args.answers else interactive_profile(hints)
            payload = {**hints, **payload}
            payload.pop("resume_text", None)
            payload.pop("questions_for_user", None)
            saved = save_profile(db, payload, source=args.resume.name if args.resume else "onboarding")
            resume_path = preserve_resume(args.resume, data_dir()) if args.resume else None
            private_config_path = config_path()
            if not private_config_path.exists():
                private_config_path.write_text(json.dumps({"default_tailoring_mode": "STANDARD", "target_resume_pages": 1, "job_sources": []}, indent=2) + "\n", encoding="utf-8")
            output({"profile": saved, "original_resume": str(resume_path) if resume_path else None, "config": str(private_config_path)})
        elif args.command == "onboarding-packet":
            value = onboarding_packet(args.resume)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
            output({"packet": str(args.out), "resume": str(args.resume)})
        elif args.command == "profile":
            with db.connect() as connection:
                if args.profile_command == "versions":
                    rows = connection.execute("SELECT public_id,version,source_resume_name,reviewed_at,created_at FROM profile_versions ORDER BY version DESC").fetchall()
                    output([dict(row) for row in rows])
                else:
                    evidence = connection.execute("SELECT id,public_id,kind,statement,tags_json,provenance_json FROM evidence WHERE verified=1 ORDER BY kind,id").fetchall()
                    output({"profile": load_profile(db), "verified_evidence": [{**dict(row), "tags": json.loads(row["tags_json"]), "provenance": json.loads(row["provenance_json"])} for row in evidence]})
        elif args.command == "jobs":
            if args.jobs_command == "import":
                output(import_jobs(db, read_jobs(args.path), args.source))
            elif args.jobs_command == "add":
                description = args.description_file.read_text(encoding="utf-8") if args.description_file else args.description
                output(import_jobs(db, [{"company": args.company, "title": args.title, "url": args.url, "location": args.location, "description": description}], "manual"))
            elif args.jobs_command == "discover":
                source = f"{args.provider}:{args.account}"
                found = discover(args.provider, args.account, args.company)
                result = import_jobs(db, found, source, source_capability(args.provider))
                record_search_run(db, source, {"account": args.account, "company": args.company}, len(found))
                output({"discovered": len(found), **result})
            elif args.jobs_command == "evaluate":
                output({"evaluated": evaluate_jobs(db, load_profile(db), args.job_id)})
            elif args.jobs_command == "scan":
                output(scan_sources(db, load_profile(db), load_config().get("job_sources", [])))
            elif args.jobs_command == "show":
                with db.connect() as connection:
                    row = connection.execute("SELECT * FROM jobs WHERE id=?", (args.job_id,)).fetchone()
                    evaluations = connection.execute("SELECT public_id,version,factors_json,score,created_at FROM job_evaluations WHERE job_id=? ORDER BY version", (args.job_id,)).fetchall()
                if not row:
                    raise ValueError(f"Job {args.job_id} not found")
                output({"job": dict(row), "evaluations": [{**dict(item), "factors": json.loads(item["factors_json"])} for item in evaluations]})
            elif args.jobs_command == "status":
                update_status(db, args.job_id, args.status)
                output({"job_id": args.job_id, "status": args.status})
            else:
                with db.connect() as connection:
                    query = "SELECT id, company, title, location, status, score, url FROM jobs"
                    values: tuple[str, ...] = ()
                    if args.status:
                        query += " WHERE status=?"
                        values = (args.status,)
                    query += " ORDER BY score DESC, id DESC"
                    output([dict(row) for row in connection.execute(query, values)])
        elif args.command == "tailor":
            if args.tailor_command == "packet":
                value = tailoring_packet(db, args.job_id, load_profile(db), args.mode)
                if args.out:
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
                output(value)
            else:
                if not args.confirm_truthful:
                    raise ValueError("Building tailored materials requires --confirm-truthful after human review")
                output(
                    build_materials(
                        db,
                        artifacts_dir(),
                        args.job_id,
                        load_profile(db),
                        read_json(str(args.proposal)),
                        make_pdf=args.pdf,
                    )
                )
        elif args.command == "materials":
            approve_materials(db, args.material_id)
            output({"approved": args.material_id})
        elif args.command == "applications":
            if args.applications_command == "start":
                output({"application_id": start_application(db, args.job_id, args.material_id)})
            elif args.applications_command == "list":
                with db.connect() as connection:
                    rows = connection.execute(
                        "SELECT a.id, a.public_id, j.company, j.title, a.status, a.submitted_at, a.next_action, j.source "
                        "FROM applications a JOIN jobs j ON j.id=a.job_id ORDER BY a.updated_at DESC"
                    ).fetchall()
                output([dict(row) for row in rows])
            elif args.applications_command == "show":
                output(history(db, args.application_id))
            elif args.applications_command == "status":
                transition_application(db, args.application_id, args.status, args.note)
                output({"application_id": args.application_id, "status": args.status})
            elif args.applications_command == "save-prep":
                output(save_preparation(db, args.application_id, args.kind, read_json(str(args.content))))
            else:
                value = preparation_packet(db, args.application_id, args.kind)
                if args.out:
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
                output(value)
        elif args.command == "automation":
            if args.automation_command == "prepare":
                supplied: dict[str, Any] = {}
                if args.answers:
                    if not args.confirm_answers:
                        raise ValueError("Supplied application answers require --confirm-answers after review")
                    supplied = read_json(str(args.answers))
                config = load_config()
                output(prepare_automation(db, args.application_id, read_json(str(args.plan)), {**verified_answers(db), **supplied}, config.get("classification_overrides", {})))
            elif args.automation_command == "authorize":
                authorize_submission(db, args.run_id, args.token, args.confirm)
                output({"run_id": args.run_id, "state": "authorized_to_submit", "instruction": "User approval recorded. Submit once, then record the receipt."})
            elif args.automation_command == "record-submission":
                record_submission(db, args.run_id, read_json(str(args.receipt)))
                output({"recorded": args.run_id})
            else:
                output(pre_submission_audit(db, args.run_id))
        elif args.command == "doctor":
            report = run_doctor(Path.cwd(), data_dir(), db)
            output(report)
            return 0 if report["status"] == "PASS" else 2
        elif args.command == "analytics":
            output(search_analytics(db))
        elif args.command == "gui":
            from .gui import serve

            serve(db, Path.cwd(), port=args.port, open_browser=not args.no_open)
        elif args.command == "answers":
            if args.answers_command == "list":
                output(list_answers(db))
            elif args.answers_command == "classify":
                fields = read_json(str(args.fields)).get("fields", [])
                output(classify_answers(fields, set(verified_answers(db)), load_config().get("classification_overrides", {})))
            else:
                if not args.confirm_verified:
                    raise ValueError("Saving a reusable answer requires --confirm-verified")
                try:
                    value = json.loads(args.value)
                except json.JSONDecodeError:
                    value = args.value
                output(save_answer(db, args.answer_key, value, args.classification, "user-confirmed CLI"))
        elif args.command == "contacts":
            output(list_records(db, "contacts") if args.contacts_command == "list" else add_contact(db, args.company_id, args.name, args.email, args.role, args.notes))
        elif args.command == "interviews":
            if args.interviews_command == "list":
                output(list_records(db, "interviews", args.application_id))
            elif args.interviews_command == "add":
                output(add_interview(db, args.application_id, args.stage, args.scheduled_at, args.notes))
            else:
                update_record_status(db, "interviews", args.interview_id, args.status)
                output({"interview_id": args.interview_id, "status": args.status})
        elif args.command == "followups":
            if args.followups_command == "list":
                output(list_records(db, "followups", args.application_id))
            elif args.followups_command == "add":
                output(add_followup(db, args.application_id, args.kind, args.due_at, args.content))
            else:
                update_record_status(db, "followups", args.followup_id, args.status)
                output({"followup_id": args.followup_id, "status": args.status})
        return 0
    except (ValueError, RuntimeError, PermissionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
