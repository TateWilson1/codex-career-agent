from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_career.applications import authorize_submission, history, prepare_automation, start_application
from codex_career.browser import SyntheticATSAdapter
from codex_career.db import Database
from codex_career.jobs import import_jobs
from codex_career.materials import approve_materials, build_materials, sha256
from codex_career.profile import evidence_id, save_profile

from test_end_to_end import JOBS, PROFILE


class BrowserFixtureTest(unittest.TestCase):
    def test_synthetic_ats_requires_bound_approval_and_records_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Database(root / "career.db")
            save_profile(db, PROFILE)
            import_jobs(db, JOBS[:1], "fixture")
            ev = evidence_id("experience", PROFILE["experience"][0]["bullets"][0])
            proposal = {"summary": "Verified analyst.", "selected_evidence": [ev], "bullet_rewrites": [{"evidence_id": ev, "text": PROFILE["experience"][0]["bullets"][0]}]}
            material = build_materials(db, root / "artifacts", 1, PROFILE, proposal)
            approve_materials(db, material["id"])
            app_id = start_application(db, 1, material["id"])
            unapproved_resume = root / "unapproved-resume.pdf"
            unapproved_resume.write_text("tampered", encoding="utf-8")
            run = prepare_automation(db, app_id, {"fields": [
                {"label": "Name", "answer_key": "name"},
                {"label": "Email", "answer_key": "email"},
                {"label": "Resume", "answer_key": "resume_path", "type": "file"},
            ]}, {"name": PROFILE["name"], "email": PROFILE["email"], "resume_path": str(unapproved_resume)})
            resume_field = next(field for field in run["fill_plan"]["fields"] if field["answer_key"] == "resume_path")
            approved_resume = Path(resume_field["value"])
            self.assertNotEqual(approved_resume, unapproved_resume)
            self.assertIn(approved_resume.name, {"resume.pdf", "resume.docx"})
            adapter = SyntheticATSAdapter(Path(__file__).parent / "fixtures" / "synthetic-ats.html")
            filled = adapter.fill(db, run["run_id"])
            self.assertEqual(filled["filled"]["name"], PROFILE["name"])
            self.assertEqual(filled["uploaded"]["resume_path"], sha256(approved_resume))
            with self.assertRaises(PermissionError):
                adapter.submit(db, run["run_id"])
            authorize_submission(db, run["run_id"], run["submission_approval_token"], "SUBMIT THIS APPLICATION")
            receipt = adapter.submit(db, run["run_id"])
            self.assertTrue(receipt["confirmation_number"].startswith("SYN-"))
            saved = history(db, app_id)
            self.assertEqual(saved["status"], "submitted")
            self.assertIn(receipt["confirmation_number"], saved["confirmation"])

    def test_unsupported_question_blocks_fixture_fill(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Database(root / "career.db")
            save_profile(db, PROFILE)
            import_jobs(db, JOBS[:1], "fixture")
            ev = evidence_id("experience", PROFILE["experience"][0]["bullets"][0])
            proposal = {"summary": "Verified analyst.", "selected_evidence": [ev], "bullet_rewrites": [{"evidence_id": ev, "text": PROFILE["experience"][0]["bullets"][0]}]}
            material = build_materials(db, root / "artifacts", 1, PROFILE, proposal)
            approve_materials(db, material["id"])
            app_id = start_application(db, 1, material["id"])
            run = prepare_automation(db, app_id, {"fields": [{"label": "Attestation", "answer_key": "attest", "type": "legal_attestation"}]}, {"attest": True})
            adapter = SyntheticATSAdapter(Path(__file__).parent / "fixtures" / "synthetic-ats.html")
            with self.assertRaises(PermissionError):
                adapter.fill(db, run["run_id"])


if __name__ == "__main__":
    unittest.main()
