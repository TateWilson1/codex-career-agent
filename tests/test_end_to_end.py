from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from codex_career.applications import authorize_submission, history, preparation_packet, prepare_automation, record_submission, save_preparation, start_application
from codex_career.db import Database
from codex_career.jobs import evaluate_jobs, import_jobs, scan_sources, score_job, update_status
from codex_career.materials import approve_materials, build_materials, tailoring_packet, validate_proposal
from codex_career.profile import evidence_id, load_profile, save_profile
from codex_career.sources import ashby, greenhouse, lever, smartrecruiters, usajobs
from codex_career.tracking import add_contact, add_followup, add_interview, list_records, update_record_status


PROFILE = {
    "name": "Jordan Rivera",
    "email": "jordan.rivera@example.test",
    "phone": "555-010-2040",
    "links": ["https://example.test/jordan"],
    "target_roles": ["Security Analyst"],
    "locations": ["Remote"],
    "work_authorization": "Authorized to work in the United States",
    "skills": ["Python", "SIEM", "Incident response"],
    "experience": [
        {
            "company": "Northwind Community Lab",
            "title": "Security Operations Intern",
            "dates": "May 2025 - August 2025",
            "bullets": ["Triaged 120 simulated security alerts and documented escalation decisions."],
        }
    ],
    "education": ["BS Cybersecurity, Example State University, Expected 2027"],
    "certifications": ["CompTIA Security+"],
}

JOBS = [
    {
        "company": "Contoso Defense",
        "title": "Junior Security Analyst",
        "location": "Remote - United States",
        "url": "https://jobs.example.test/contoso/001",
        "description": "Monitor SIEM alerts and support incident response with Python.",
    },
    {
        "company": "Contoso Defense",
        "title": "Junior Security Analyst",
        "location": "Remote - United States",
        "url": "https://jobs.example.test/contoso/001?duplicate=yes",
        "description": "Updated posting text.",
    },
]


class CareerFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = Database(self.root / "career.db")
        save_profile(self.db, PROFILE)
        self.assertEqual(import_jobs(self.db, JOBS, "fixture"), {"inserted": 1, "updated": 1})
        self.assertEqual(evaluate_jobs(self.db, load_profile(self.db)), 1)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def proposal(self) -> dict:
        item_id = evidence_id("experience", PROFILE["experience"][0]["bullets"][0])
        return {
            "summary": "Security analyst with verified SIEM, incident response, and Python experience.",
            "selected_evidence": [item_id],
            "bullet_rewrites": [
                {"evidence_id": item_id, "text": "Triaged 120 simulated security alerts and documented escalation decisions."}
            ],
            "cover_letter": "I am applying for the Junior Security Analyst role using the experience documented in my resume.",
        }

    def test_complete_safe_application_flow(self) -> None:
        packet = tailoring_packet(self.db, 1, PROFILE)
        self.assertEqual(packet["job"]["company"], "Contoso Defense")
        built = build_materials(self.db, self.root / "artifacts", 1, PROFILE, self.proposal(), make_pdf=True)
        resume = Path(built["path"]) / "resume.docx"
        self.assertTrue(resume.is_file())
        self.assertTrue((Path(built["path"]) / "resume.pdf").is_file())
        self.assertEqual(built["validation"]["pdf_pages"], 1)
        self.assertGreaterEqual(built["validation"]["minimum_style_font_pt"], 9)
        self.assertEqual(built["validation"]["blank_pdf_pages"], 0)
        approve_materials(self.db, built["id"])
        application_id = start_application(self.db, 1, built["id"])
        update_status(self.db, 1, "applying")
        run = prepare_automation(
            self.db,
            application_id,
            {"fields": [
                {"label": "Name", "type": "text", "answer_key": "name"},
                {"label": "Resume", "type": "file", "answer_key": "resume_path"},
            ]},
            {"name": PROFILE["name"], "resume_path": str(resume)},
        )
        self.assertEqual(run["state"], "ready_for_fill")
        with self.assertRaises(PermissionError):
            record_submission(self.db, run["run_id"], {})
        with self.assertRaises(PermissionError):
            authorize_submission(self.db, run["run_id"], run["submission_approval_token"], "yes")
        authorize_submission(
            self.db, run["run_id"], run["submission_approval_token"], "SUBMIT THIS APPLICATION"
        )
        receipt = {"confirmation_number": "TEST-123", "screenshot": "confirmation.png"}
        record_submission(self.db, run["run_id"], receipt)
        contact = add_contact(self.db, 1, "Morgan Lee", "morgan@example.test", "Recruiter")
        interview = add_interview(self.db, application_id, "screen", "2027-01-10T15:00:00Z")
        followup = add_followup(self.db, application_id, "thank-you", "2027-01-11T15:00:00Z", "Reviewed fictional draft")
        update_record_status(self.db, "interviews", interview["id"], "completed")
        update_record_status(self.db, "followups", followup["id"], "sent")
        first_prep = save_preparation(self.db, application_id, "interview", {"questions": ["How is success measured?"]})
        second_prep = save_preparation(self.db, application_id, "interview", {"questions": ["What are the first priorities?"]})
        self.assertEqual((first_prep["version"], second_prep["version"]), (1, 2))
        saved = history(self.db, application_id)
        self.assertEqual(saved["status"], "submitted")
        self.assertEqual(saved["application_answers"][0]["answers"]["name"], PROFILE["name"])
        self.assertEqual(saved["manifest"]["files"][0]["sha256"], built["files"][0]["sha256"])
        self.assertEqual(len(saved["preparations"]), 2)
        self.assertEqual(saved["interviews"][0]["status"], "completed")
        self.assertEqual(saved["followups"][0]["status"], "sent")
        self.assertEqual(list_records(self.db, "contacts")[0]["public_id"], contact["public_id"])
        self.assertEqual(preparation_packet(self.db, application_id, "interview")["application"]["id"], application_id)
        with self.db.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0], len(built["files"]))

    def test_safety_stops_and_integrity(self) -> None:
        built = build_materials(self.db, self.root / "artifacts", 1, PROFILE, self.proposal())
        approve_materials(self.db, built["id"])
        application_id = start_application(self.db, 1, built["id"])
        run = prepare_automation(
            self.db,
            application_id,
            {"fields": [
                {"label": "MFA", "type": "mfa", "answer_key": "code"},
                {"label": "Salary", "type": "salary", "answer_key": "salary"},
            ]},
            {"code": "123456", "salary": "80000"},
        )
        self.assertEqual(run["state"], "blocked")
        reasons = {item["reason"] for item in run["fill_plan"]["stops"]}
        self.assertIn("mfa", reasons)
        self.assertIn("approval_required:salary", reasons)
        resume = Path(built["path"]) / "resume.docx"
        resume.write_bytes(resume.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "integrity"):
            start_application(self.db, 1, built["id"])

    def test_numeric_claims_cannot_be_invented(self) -> None:
        proposal = self.proposal()
        proposal["bullet_rewrites"][0]["text"] = "Triaged 900 security alerts."
        with self.assertRaisesRegex(ValueError, "numeric claims"):
            validate_proposal(self.db, proposal)

    def test_selected_project_and_leadership_evidence_render(self) -> None:
        profile = {
            **PROFILE,
            "projects": [{"name": "Forensics Lab", "dates": "2026", "bullets": ["Analyzed a forensic disk image."]}],
            "leadership": [{"organization": "Cyber Club", "title": "Captain", "dates": "2026", "bullets": ["Led incident response practice sessions."]}],
        }
        save_profile(self.db, profile)
        ids = [
            evidence_id("experience", profile["experience"][0]["bullets"][0]),
            evidence_id("projects", profile["projects"][0]["bullets"][0]),
            evidence_id("leadership", profile["leadership"][0]["bullets"][0]),
        ]
        proposal = {"summary": "Verified analyst.", "selected_evidence": ids, "bullet_rewrites": []}
        built = build_materials(self.db, self.root / "selected", 1, profile, proposal)
        text = "\n".join(paragraph.text for paragraph in Document(Path(built["path"]) / "resume.docx").paragraphs)
        self.assertIn("Projects", text)
        self.assertIn("Analyzed a forensic disk image.", text)
        self.assertIn("Leadership", text)
        self.assertIn("Led incident response practice sessions.", text)

    def test_profile_replacement_retires_stale_evidence(self) -> None:
        old_id = evidence_id("experience", PROFILE["experience"][0]["bullets"][0])
        replacement = {**PROFILE, "experience": []}
        save_profile(self.db, replacement)
        with self.db.connect() as connection:
            row = connection.execute("SELECT id FROM evidence WHERE id=?", (old_id,)).fetchone()
        self.assertIsNone(row)

    def test_public_job_source_adapters(self) -> None:
        def greenhouse_fetch(url: str):
            if url.endswith("/acme"):
                return {"name": "Acme Security"}
            return {"jobs": [{
                "id": 42,
                "title": "Security Analyst",
                "location": {"name": "Remote"},
                "absolute_url": "https://example.test/42",
                "content": "<p>Monitor &amp; investigate alerts.</p>",
            }]}

        def lever_fetch(_url: str):
            return [{
                "id": "abc",
                "text": "SOC Analyst",
                "categories": {"location": "Pittsburgh"},
                "hostedUrl": "https://example.test/abc",
                "descriptionPlain": "Investigate alerts.",
            }]

        self.assertEqual(greenhouse("acme", fetch=greenhouse_fetch)[0]["company"], "Acme Security")
        self.assertEqual(greenhouse("acme", fetch=greenhouse_fetch)[0]["description"], "Monitor & investigate alerts.")
        self.assertEqual(lever("acme", "Acme Security", fetch=lever_fetch)[0]["title"], "SOC Analyst")

        smart = smartrecruiters("acme", fetch=lambda _url: {"content": [{
            "id": "smart-1", "name": "Cybersecurity Intern", "releasedDate": "2026-09-29T10:00:00Z",
            "location": {"city": "Lexington", "region": "Kentucky", "country": "US"},
            "typeOfEmployment": {"label": "Intern"}, "ref": "https://example.test/smart-1",
        }]})
        self.assertEqual(smart[0]["location"], "Lexington, Kentucky, US")

        ashby_jobs = ashby("acme", "Acme Security", fetch=lambda _url: {"jobs": [{
            "id": "ashby-1", "title": "Incident Response Intern", "location": "Remote, US",
            "jobUrl": "https://jobs.example.test/ashby-1", "applyUrl": "https://jobs.example.test/ashby-1/apply",
            "descriptionHtml": "<p>Investigate alerts.</p>", "isListed": True,
            "compensation": {"summaryComponents": [{"compensationType": "Salary", "minValue": 60000, "maxValue": 70000, "currencyCode": "USD"}]},
        }]})
        self.assertEqual((ashby_jobs[0]["title"], ashby_jobs[0]["salary_max"]), ("Incident Response Intern", 70000))

        def usajobs_fetch(url: str, headers: dict[str, str]):
            self.assertIn("Keyword=digital+forensics", url)
            self.assertEqual(headers["Authorization-Key"], "private-test-key")
            return {"SearchResult": {"SearchResultItems": [{"MatchedObjectDescriptor": {
                "PositionID": "federal-1", "PositionTitle": "IT Cybersecurity Specialist",
                "PositionURI": "https://www.usajobs.gov/job/federal-1", "ApplyURI": ["https://apply.example.test/federal-1"],
                "OrganizationName": "Example Federal Agency", "PositionLocationDisplay": "Lexington, Kentucky",
                "PositionSchedule": [{"Name": "Full-time"}], "PublicationStartDate": "2026-09-29",
                "UserArea": {"Details": {"JobSummary": "Support incident response.", "SecurityClearance": "Not Required"}},
            }}]}}

        federal = usajobs("digital forensics", fetch=usajobs_fetch, email="jordan@example.test", api_key="private-test-key")
        self.assertEqual((federal[0]["company"], federal[0]["employment_type"]), ("Example Federal Agency", "Full-time"))

    def test_explainable_scoring_rewards_fresh_entry_fit_and_penalizes_clearance(self) -> None:
        fresh = {
            "title": "Entry-Level Digital Forensics Analyst", "description": "Use incident response, SIEM, and Python.",
            "location": "Remote - United States", "location_type": "remote", "employment_type": "Full time",
            "posting_date": "2099-01-01T00:00:00Z", "required_qualifications_json": "[]",
            "clearance_requirement": "", "travel_requirement": "",
        }
        result = score_job(fresh, PROFILE)
        self.assertGreaterEqual(result["score"], 80)
        self.assertEqual(result["freshness"], "first 24 hours")
        self.assertIn("role alignment", result["breakdown"])
        graduate = {**fresh, "title": "Cyber & Forensic Technology Consulting Analyst/Associate (2027 Graduates)"}
        self.assertEqual(score_job(graduate, PROFILE)["breakdown"]["role alignment"], 30)
        wrong_class = score_job(
            {**fresh, "title": "Cybersecurity Analyst Intern (2028 Graduates)", "required_qualifications_json": json.dumps(["Candidates graduating in 2028"])},
            {**PROFILE, "education": [{"degree": "BS Cybersecurity", "dates": "Expected December 2026"}]},
        )
        self.assertFalse(wrong_class["education_fit"])
        self.assertTrue(any("Graduate hiring window" in item["reason"] for item in wrong_class["deductions"]))
        description_match = score_job(
            {**fresh, "title": "Cybersecurity Analyst Intern", "description": "Open to candidates graduating December 2026 or May 2027."},
            {**PROFILE, "education": [{"degree": "BS Cybersecurity", "dates": "Expected December 2026"}]},
        )
        self.assertTrue(description_match["education_fit"])
        restricted = {**fresh, "title": "Senior Digital Forensics Analyst", "description": fresh["description"] + " Requires 7 years experience.", "clearance_requirement": "Active Top Secret clearance required"}
        blocked = score_job(restricted, {**PROFILE, "security_clearance": "None"})
        self.assertLess(blocked["score"], result["score"])
        self.assertGreaterEqual(len(blocked["deductions"]), 2)

    def test_configured_source_scan_imports_deduplicates_scores_and_records_runs(self) -> None:
        import_jobs(self.db, [{
            "company": "Example Security", "title": "Accounts Payable Coordinator",
            "url": "https://example.test/jobs/old-unrelated", "description": "Process invoices.",
        }], "greenhouse:example", "AUTOMATED")
        def discoverer(provider: str, account: str, company: str | None):
            self.assertEqual((provider, account, company), ("greenhouse", "example", "Example Security"))
            return [{
                "company": company, "title": "Entry-Level Security Analyst", "location": "Remote",
                "location_type": "remote", "employment_type": "Full-time",
                "posting_date": "2099-01-01T00:00:00Z", "url": "https://example.test/jobs/scan-1",
                "description": "Entry-level SIEM monitoring and incident response with Python.",
            }, {
                "company": company, "title": "Entry-Level Security Analyst", "location": "Remote",
                "posting_date": "2099-01-01T00:00:00Z", "url": "https://example.test/jobs/scan-1?duplicate=1",
                "description": "Updated entry-level SIEM monitoring and incident response with Python.",
            }, {
                "company": company, "title": "Accounts Payable Coordinator", "location": "Remote",
                "url": "https://example.test/jobs/unrelated", "description": "Process invoices.",
            }]

        result = scan_sources(
            self.db, PROFILE,
            [{"provider": "greenhouse", "account": "example", "company": "Example Security"}],
            discoverer,
        )
        self.assertEqual((result["checked"], result["inserted"], result["updated"]), (3, 1, 1))
        self.assertEqual(result["sources"][0]["relevant"], 2)
        self.assertEqual(result["archived"], 1)
        self.assertEqual(len(result["new_strong_matches"]), 1)
        with self.db.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT status FROM jobs WHERE title='Accounts Payable Coordinator'").fetchone()[0], "archived")

    def test_source_health_and_job_availability_follow_real_feed_results(self) -> None:
        source = [{"provider": "greenhouse", "account": "example", "company": "Example Security"}]
        first = {
            "company": "Example Security", "title": "Security Analyst", "location": "Remote",
            "url": "https://example.test/jobs/analyst", "description": "Monitor and investigate alerts.",
        }
        second = {
            "company": "Example Security", "title": "Incident Response Intern", "location": "Remote",
            "url": "https://example.test/jobs/intern", "description": "Support incident response.",
        }

        scan_sources(self.db, PROFILE, source, lambda *_: [first])
        scan_sources(self.db, PROFILE, source, lambda *_: [])
        with self.db.connect() as connection:
            self.assertIsNone(connection.execute(
                "SELECT closed_at FROM jobs WHERE title='Security Analyst'"
            ).fetchone()[0])
        result = scan_sources(self.db, PROFILE, source, lambda *_: [second])
        self.assertEqual(result["closed"], 0)
        result = scan_sources(self.db, PROFILE, source, lambda *_: [second])
        self.assertEqual(result["closed"], 1)
        with self.db.connect() as connection:
            self.assertIsNotNone(connection.execute(
                "SELECT closed_at FROM jobs WHERE title='Security Analyst'"
            ).fetchone()[0])

        scan_sources(self.db, PROFILE, source, lambda *_: [first, second])
        def unavailable(*_):
            raise OSError("feed unavailable")

        failed = scan_sources(self.db, PROFILE, source, unavailable)
        self.assertEqual(failed["errors"][0]["error"], "feed unavailable")
        with self.db.connect() as connection:
            self.assertIsNone(connection.execute(
                "SELECT closed_at FROM jobs WHERE title='Security Analyst'"
            ).fetchone()[0])
            run = connection.execute(
                "SELECT status,error_text FROM search_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual((run["status"], run["error_text"]), ("failed", "feed unavailable"))


if __name__ == "__main__":
    unittest.main()
