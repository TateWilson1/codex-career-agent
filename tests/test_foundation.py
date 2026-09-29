from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from codex_career.answers import classify_question, list_answers, save_answer, verified_answers
from codex_career.applications import authorize_submission, prepare_automation, start_application
from codex_career.db import Database
from codex_career.doctor import run_doctor
from codex_career.jobs import evaluate_jobs, import_jobs, normalize_job
from codex_career.materials import approve_materials, build_materials
from codex_career.migrations import MIGRATION_1
from codex_career.profile import evidence_id, onboarding_packet, preserve_resume, save_profile
from codex_career.status import transition_application
from codex_career.safety import validate_fill_plan

from test_end_to_end import JOBS, PROFILE


class FoundationTest(unittest.TestCase):
    def test_resume_import_packet_and_original_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            resume = root / "candidate.txt"
            resume.write_text("Jordan Rivera\nPython and SQL\n", encoding="utf-8")
            packet = onboarding_packet(resume)
            preserved = preserve_resume(resume, root / "private")
            self.assertEqual(packet["resume_file"], resume.name)
            self.assertIn("Jordan Rivera", packet["resume_text"])
            self.assertIn("only facts explicitly present", packet["instructions"][0])
            self.assertEqual(preserved.read_bytes(), resume.read_bytes())

    def test_empty_and_legacy_databases_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            fresh = Database(Path(folder) / "fresh.db")
            self.assertEqual(fresh.schema_version, 2)
            with fresh.connect() as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"profile_versions", "job_evaluations", "document_versions", "submission_attempts"} <= tables)

            legacy_path = Path(folder) / "legacy.db"
            with closing(sqlite3.connect(legacy_path)) as connection:
                connection.executescript(MIGRATION_1)
                connection.execute(
                    "INSERT INTO jobs(fingerprint, source, company, title, created_at, updated_at) VALUES('x','manual','Example','Role','t','t')"
                )
                connection.commit()
            legacy = Database(legacy_path)
            self.assertEqual(legacy.schema_version, 2)
            with legacy.connect() as connection:
                self.assertTrue(connection.execute("SELECT public_id FROM jobs").fetchone()[0].startswith("job_"))

    def test_profile_versions_and_original_job_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            save_profile(db, PROFILE)
            save_profile(db, {**PROFILE, "target_roles": ["SOC Analyst"]})
            import_jobs(db, JOBS[:1], "fixture")
            with db.connect() as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM profile_versions").fetchone()[0], 2)
                row = connection.execute("SELECT public_id, original_content FROM jobs").fetchone()
            self.assertTrue(row["public_id"].startswith("job_"))
            self.assertEqual(json.loads(row["original_content"])["company"], "Contoso Defense")

    def test_job_normalization_persists_full_fields_and_source_contract(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            raw = {
                "external_id": "abc", "company": "Example Works", "title": "Analyst",
                "company_url": "https://example.test", "location": "Remote", "location_type": "remote",
                "employment_type": "full-time", "salary_min": "70000", "salary_max": 90000,
                "currency": "USD", "url": "https://jobs.example.test/a", "application_url": "https://apply.example.test/a",
                "description": "Analyze data.", "responsibilities": ["Analyze data"],
                "required_qualifications": ["Python", "CPA license"], "preferred_qualifications": ["SQL"],
                "clearance_requirement": "None", "work_authorization_requirement": "US authorization", "travel_requirement": "10%",
            }
            self.assertEqual(normalize_job(raw)["salary_min"], 70000)
            import_jobs(db, [raw], "fixture:board", "ASSISTED")
            with db.connect() as connection:
                job = connection.execute("SELECT * FROM jobs").fetchone()
                source = connection.execute("SELECT * FROM job_sources").fetchone()
                company = connection.execute("SELECT * FROM companies").fetchone()
            self.assertEqual((job["salary_min"], job["location_type"], job["application_url"]), (70000, "remote", raw["application_url"]))
            self.assertEqual(json.loads(job["required_qualifications_json"]), ["Python", "CPA license"])
            self.assertEqual(source["capability"], "ASSISTED")
            self.assertEqual(company["url"], raw["company_url"])
            save_profile(db, PROFILE)
            evaluate_jobs(db, PROFILE)
            with db.connect() as connection:
                factors = json.loads(connection.execute("SELECT factors_json FROM job_evaluations").fetchone()[0])
            self.assertIn("Python", factors["matched_requirements"])
            self.assertEqual(factors["missing_requirements"], ["CPA license"])

    def test_source_refresh_preserves_original_and_enriched_fields(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            original = {
                "company": "Example Works", "title": "Security Analyst",
                "url": "https://jobs.example.test/security", "application_url": "https://apply.example.test/security",
                "description": "Original posting.", "required_qualifications": ["Python"], "salary_min": 70000,
            }
            import_jobs(db, [original], "fixture:board", "AUTOMATED")
            import_jobs(db, [{
                "company": "Example Works", "title": "Security Analyst",
                "url": original["url"], "description": "Updated public description.",
            }], "fixture:board", "AUTOMATED")
            with db.connect() as connection:
                job = connection.execute("SELECT * FROM jobs").fetchone()
            self.assertEqual(job["description"], "Updated public description.")
            self.assertEqual(job["application_url"], original["application_url"])
            self.assertEqual(job["salary_min"], 70000)
            self.assertEqual(json.loads(job["required_qualifications_json"]), ["Python"])
            self.assertEqual(json.loads(job["original_content"])["description"], "Original posting.")

    def test_answer_classification_is_conservative(self) -> None:
        self.assertEqual(classify_question("email", verified=True), "AUTO")
        self.assertEqual(classify_question("expected_graduation", verified=True), "AUTO")
        self.assertEqual(classify_question("salary", verified=True), "VERIFY")
        self.assertEqual(classify_question("security_clearance", verified=True), "VERIFY")
        self.assertEqual(classify_question("anything", "legal_attestation", verified=True), "USER_REQUIRED")
        self.assertEqual(classify_question("unknown", verified=False), "USER_REQUIRED")
        plan = validate_fill_plan({"fields": [{"label": "Unknown", "answer_key": "unknown"}]}, {"unknown": "invented"})
        self.assertEqual(plan["stops"][0]["reason"], "user_required")

    def test_answer_vault_requires_explicit_classification_and_returns_verified_values(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            save_answer(db, "start_date", "2027-06-01", "VERIFY", "test review")
            self.assertEqual(verified_answers(db)["start_date"], "2027-06-01")
            self.assertEqual(list_answers(db)[0]["classification"], "VERIFY")

    def test_structured_profile_builds_tagged_verified_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            profile = {
                **PROFILE,
                "projects": [{"name": "Lab", "bullets": ["Built a fictional packet analyzer."], "tags": ["python", "networking"]}],
                "leadership": [{"name": "Club Lead", "bullets": ["Led a fictional security club."], "tags": ["leadership"]}],
                "licenses": ["Fictional License"],
                "awards": ["Example Award"],
            }
            save_profile(db, profile, "reviewed-fixture")
            with db.connect() as connection:
                project = connection.execute("SELECT * FROM evidence WHERE kind='projects'").fetchone()
                kinds = {row[0] for row in connection.execute("SELECT DISTINCT kind FROM evidence")}
            self.assertEqual(json.loads(project["tags_json"]), ["python", "networking"])
            self.assertEqual(json.loads(project["provenance_json"])["source"], "reviewed-fixture")
            self.assertTrue({"education", "licenses", "awards", "projects", "leadership"} <= kinds)

    def test_invalid_application_state_transition_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            with db.connect() as connection:
                connection.execute(
                    "INSERT INTO jobs(public_id,fingerprint,source,company,title,created_at,updated_at) VALUES('job_test','f','manual','Example','Role','t','t')"
                )
                connection.execute(
                    "INSERT INTO applications(public_id,job_id,status,created_at,updated_at) VALUES('app_test',1,'ready_for_review','t','t')"
                )
            with self.assertRaisesRegex(ValueError, "Invalid"):
                transition_application(db, 1, "submitted")

    def test_approval_is_bound_to_exact_material_set(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Database(root / "career.db")
            save_profile(db, PROFILE)
            import_jobs(db, JOBS[:1], "fixture")
            item = evidence_id("experience", PROFILE["experience"][0]["bullets"][0])
            proposal = {"summary": "Verified analyst.", "selected_evidence": [item], "bullet_rewrites": [{"evidence_id": item, "text": PROFILE["experience"][0]["bullets"][0]}]}
            first = build_materials(db, root / "artifacts", 1, PROFILE, proposal)
            second = build_materials(db, root / "artifacts", 1, PROFILE, proposal)
            approve_materials(db, first["id"])
            approve_materials(db, second["id"])
            app_id = start_application(db, 1, first["id"])
            with self.assertRaisesRegex(ValueError, "immutable"):
                start_application(db, 1, second["id"])
            run = prepare_automation(db, app_id, {"fields": [{"label": "Name", "answer_key": "name"}]}, {"name": PROFILE["name"]})
            with db.connect() as connection:
                connection.execute("UPDATE applications SET material_set_id=? WHERE id=?", (second["id"], app_id))
            with self.assertRaisesRegex(PermissionError, "changed"):
                authorize_submission(db, run["run_id"], run["submission_approval_token"], "SUBMIT THIS APPLICATION")

    def test_approval_is_bound_to_exact_answer_version(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Database(root / "career.db")
            save_profile(db, PROFILE)
            import_jobs(db, JOBS[:1], "fixture")
            item = evidence_id("experience", PROFILE["experience"][0]["bullets"][0])
            proposal = {"summary": "Verified analyst.", "selected_evidence": [item], "bullet_rewrites": [{"evidence_id": item, "text": PROFILE["experience"][0]["bullets"][0]}]}
            material = build_materials(db, root / "artifacts", 1, PROFILE, proposal)
            approve_materials(db, material["id"])
            app_id = start_application(db, 1, material["id"])
            run = prepare_automation(db, app_id, {"fields": [{"label": "Name", "answer_key": "name"}]}, {"name": PROFILE["name"]})
            with db.connect() as connection:
                connection.execute("UPDATE application_answers SET answers_json='{}' WHERE application_id=?", (app_id,))
            with self.assertRaisesRegex(PermissionError, "answers changed"):
                authorize_submission(db, run["run_id"], run["submission_approval_token"], "SUBMIT THIS APPLICATION")

    def test_privacy_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".gitignore").write_text("user-data/\n.env\ncredentials/\ntokens/\nbrowser-profiles/\n", encoding="utf-8")
            data = root / "user-data"
            data.mkdir()
            (data / "config.json").write_text('{"default_tailoring_mode":"STANDARD"}', encoding="utf-8")
            report = run_doctor(root, data, Database(data / "career.db"))
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["safeguard_not_guarantee"])
            (data / "config.json").write_text('{"default_tailoring_mode":"IMPOSSIBLE"}', encoding="utf-8")
            self.assertEqual(run_doctor(root, data, Database(data / "career.db"))["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
