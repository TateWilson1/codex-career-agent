from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from codex_career.db import Database
from codex_career.gui import career_goal, dashboard_state, make_server, subscription_status
from codex_career.jobs import import_jobs
from codex_career.profile import save_profile

from test_end_to_end import JOBS, PROFILE


class FakeRunner:
    def status(self):
        return {"installed": True, "subscription_ready": True, "label": "Connected through ChatGPT"}

    def start_login(self):
        return {"state": "login_started"}

    def start(self, prompt):
        return {"id": "test-run", "state": "running", "prompt": prompt, "result": "", "events": []}

    def get(self, run_id):
        return {"id": run_id, "state": "complete", "result": "Done", "events": []}


class GuiTest(unittest.TestCase):
    def test_structured_career_goal_uses_near_term_objective(self) -> None:
        profile = {
            **PROFILE,
            "preferences": {"career_goals": {
                "long_term": "Lead investigations.",
                "next_two_to_three_years": "Build hands-on DFIR experience.",
            }},
        }
        self.assertEqual(career_goal(profile), "Build hands-on DFIR experience.")

    def test_subscription_status_accepts_chatgpt_and_rejects_api_auth(self) -> None:
        class Result:
            def __init__(self, text: str):
                self.returncode = 0
                self.stdout = text
                self.stderr = ""

        self.assertTrue(subscription_status(lambda *args, **kwargs: Result("Logged in using ChatGPT"))["subscription_ready"])
        api = subscription_status(lambda *args, **kwargs: Result("Logged in using an API key"))
        self.assertFalse(api["subscription_ready"])
        self.assertIn("not using ChatGPT", api["label"])

    def test_dashboard_state_exposes_useful_records_without_approval_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "career.db")
            save_profile(db, PROFILE)
            import_jobs(db, JOBS[:1], "fixture")
            payload = dashboard_state(db)
            self.assertEqual(payload["profile"]["name"], "Jordan Rivera")
            self.assertEqual(payload["counts"]["jobs"], 1)
            self.assertEqual(payload["jobs"][0]["company"], "Contoso Defense")
            self.assertGreaterEqual(len(payload["job_boards"]), 10)
            self.assertIn("search_runs", payload)
            self.assertNotIn("approval_token", json.dumps(payload))

    def test_local_server_requires_session_token_for_private_data(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = Database(root / "career.db")
            save_profile(db, PROFILE)
            server = make_server(db, root, port=0, runner=FakeRunner())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request("GET", "/api/state")
                self.assertEqual(connection.getresponse().status, 403)
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request("GET", "/api/state", headers={"X-Career-Token": server.token})
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["profile"]["name"], "Jordan Rivera")
                connection.close()

                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                body = json.dumps({"prompt": "Show my next action"})
                connection.request("POST", "/api/runs", body, {"Content-Type": "application/json", "X-Career-Token": server.token})
                response = connection.getresponse()
                self.assertEqual(response.status, 202)
                self.assertEqual(json.loads(response.read())["id"], "test-run")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
