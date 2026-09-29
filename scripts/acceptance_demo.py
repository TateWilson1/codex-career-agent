from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_career.applications import authorize_submission, history, pre_submission_audit, preparation_packet, prepare_automation, save_preparation, start_application
from codex_career.browser import SyntheticATSAdapter
from codex_career.analytics import search_analytics
from codex_career.db import Database
from codex_career.jobs import evaluate_jobs, import_jobs
from codex_career.materials import approve_materials, build_materials
from codex_career.profile import load_profile, onboarding_packet, preserve_resume, save_profile
from codex_career.status import transition_application
from codex_career.tracking import add_contact, add_followup, add_interview


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fully fictional Codex Career acceptance flow")
    parser.add_argument("--output", type=Path, default=Path("user-data/acceptance-demo"))
    parser.add_argument("--approve-submit", action="store_true", help="Explicitly approve submission to the synthetic ATS fixture")
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        raise SystemExit(f"Refusing to overwrite existing demo directory: {root}")
    root.mkdir(parents=True)
    project = Path(__file__).resolve().parents[1]
    examples = project / "examples" / "fictional"
    db = Database(root / "career.db")
    (root / "config.json").write_text(
        json.dumps({"default_tailoring_mode": "STANDARD", "target_resume_pages": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    resume_source = project / "tests" / "fixtures" / "fictional-resume.txt"
    packet = onboarding_packet(resume_source)
    profile = read(examples / "profile.json")
    save_profile(db, profile, "fictional-acceptance-demo")
    original = preserve_resume(resume_source, root)
    (root / "profile.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    imported = import_jobs(db, read(examples / "jobs.json"), "fictional-fixture")
    evaluated = evaluate_jobs(db, load_profile(db))
    material = build_materials(db, root / "documents", 1, profile, read(examples / "proposal.json"), make_pdf=True)
    approve_materials(db, material["id"])
    application_id = start_application(db, 1, material["id"])
    answers = {"name": profile["name"], "email": profile["email"]}
    run = prepare_automation(db, application_id, read(examples / "fill-plan.json"), answers)
    browser = SyntheticATSAdapter(project / "tests" / "fixtures" / "synthetic-ats.html")
    fill_result = browser.fill(db, run["run_id"])
    submitted = False
    receipt = None
    approved_audit = None
    submitted_history = None
    if args.approve_submit:
        authorize_submission(db, run["run_id"], run["submission_approval_token"], "SUBMIT THIS APPLICATION")
        approved_audit = pre_submission_audit(db, run["run_id"])
        receipt = browser.submit(db, run["run_id"])
        submitted = True
        submitted_history = history(db, application_id)
        add_contact(db, 1, "Morgan Lee", "morgan.lee@example.test", "Fictional recruiter")
        add_interview(db, application_id, "screen", "2027-01-10T15:00:00Z", "Synthetic interview record")
        add_followup(db, application_id, "thank-you", "2027-01-11T15:00:00Z", "Fictional reviewed draft")
        transition_application(db, application_id, "interview", "Fictional acceptance demo progression")
    interview = preparation_packet(db, application_id, "interview")
    save_preparation(db, application_id, "interview", {"questions": ["How is success measured in the first 90 days?"], "source": "saved application snapshot"})
    report = {
        "setup": True, "onboarding_packet": packet, "profile_reviewed": True, "original_resume": str(original), "jobs": imported,
        "evaluated": evaluated, "material": material, "layout_validation": material["validation"],
        "application_id": application_id, "pre_submission_audit": run["pre_submission_audit"], "approved_audit": approved_audit,
        "browser_fill": fill_result, "submitted": submitted, "receipt": receipt,
        "submitted_history": submitted_history, "exact_application_history": history(db, application_id),
        "interview_packet": interview, "analytics": search_analytics(db),
    }
    report_path = root / "acceptance-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(report_path)
    if not args.approve_submit:
        print("Stopped before submission. Re-run in a new output directory with --approve-submit for the synthetic ATS only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
