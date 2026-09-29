from __future__ import annotations

import json
import mimetypes
import os
import secrets
import shutil
import subprocess
import threading
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .db import Database
from .boards import CONNECTIONS, RECOMMENDED_SOURCES, board_registry, connection_registry
from .jobs import JOB_STATUSES, scan_sources, update_status
from .paths import load_config, save_config
from .profile import load_profile


STATIC_ROOT = Path(__file__).with_name("web")
PROMPT_PREFIX = """You are operating Codex Career from its local visual command center.
Complete the user's request end to end using the repository's AGENTS.md and internal job-agent tools.
Keep candidate claims grounded in verified evidence. Preserve immutable document and application history.
Never submit an application without explicit approval for that exact application after showing the final audit.
Do not ask the user to run internal CLI commands; return a concise, human-readable result for the GUI.

User request:
"""


def _loads(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def career_goal(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "Build a verified profile, then begin a focused search."
    goals = profile.get("preferences", {}).get("career_goals")
    if isinstance(goals, str) and goals.strip():
        return goals.strip()
    if isinstance(goals, dict):
        for key in ("next_two_to_three_years", "short_term", "long_term"):
            value = goals.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    roles = profile.get("target_roles") or []
    return f"Land a {roles[0]} role using verified experience." if roles else "Build a focused career search."


def dashboard_state(db: Database) -> dict[str, Any]:
    private_config_path = db.path.parent / "config.json"
    config = load_config(private_config_path)
    try:
        profile = load_profile(db)
    except ValueError:
        profile = None
    with db.connect() as connection:
        counts = {
            "jobs": connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE status!='archived' AND closed_at IS NULL"
            ).fetchone()[0],
            "interested": connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('interested','applying') AND closed_at IS NULL"
            ).fetchone()[0],
            "applications": connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "interviews": connection.execute(
                "SELECT COUNT(*) FROM interviews WHERE status='scheduled'"
            ).fetchone()[0],
        }
        jobs = [dict(row) for row in connection.execute(
            "SELECT id,public_id,company,title,location,location_type,employment_type,status,score,url,"
            "description,posting_date,created_at,last_seen_at,closed_at,score_json,updated_at FROM jobs "
            "ORDER BY CASE WHEN closed_at IS NOT NULL OR status='archived' THEN 1 ELSE 0 END,"
            "score DESC,updated_at DESC LIMIT 100"
        )]
        search_runs = [dict(row) for row in connection.execute(
            "SELECT source,result_count,finished_at,status,error_text "
            "FROM search_runs ORDER BY id DESC LIMIT 50"
        )]
        applications = [dict(row) for row in connection.execute(
            "SELECT a.id,a.public_id,a.status,a.submitted_at,a.next_action,a.updated_at,j.company,j.title,"
            "m.id AS material_id,m.version AS material_version,m.status AS material_status "
            "FROM applications a JOIN jobs j ON j.id=a.job_id "
            "LEFT JOIN material_sets m ON m.id=a.material_set_id ORDER BY a.updated_at DESC"
        )]
        materials = [dict(row) for row in connection.execute(
            "SELECT m.id,m.public_id,m.version,m.status,m.tailoring_mode,m.created_at,m.manifest_json,"
            "j.company,j.title FROM material_sets m JOIN jobs j ON j.id=m.job_id ORDER BY m.created_at DESC LIMIT 50"
        )]
        documents = [dict(row) for row in connection.execute(
            "SELECT dv.id,d.kind,dv.path,dv.sha256,dv.created_at,j.company,j.title "
            "FROM document_versions dv JOIN documents d ON d.id=dv.document_id "
            "LEFT JOIN jobs j ON j.id=dv.job_id WHERE d.kind IN ('resume','cover_letter') "
            "ORDER BY dv.created_at DESC LIMIT 100"
        )]
        automation = [dict(row) for row in connection.execute(
            "SELECT r.id,r.public_id,r.state,r.started_at,r.finished_at,a.id AS application_id,j.company,j.title "
            "FROM automation_runs r JOIN applications a ON a.id=r.application_id "
            "JOIN jobs j ON j.id=a.job_id ORDER BY r.started_at DESC LIMIT 50"
        )]
        interviews = [dict(row) for row in connection.execute(
            "SELECT i.id,i.stage,i.scheduled_at,i.status,i.notes,a.id AS application_id,j.company,j.title "
            "FROM interviews i JOIN applications a ON a.id=i.application_id "
            "JOIN jobs j ON j.id=a.job_id ORDER BY COALESCE(i.scheduled_at,i.created_at) DESC LIMIT 50"
        )]
        followups = [dict(row) for row in connection.execute(
            "SELECT f.id,f.kind,f.due_at,f.status,f.content,a.id AS application_id,j.company,j.title "
            "FROM followups f JOIN applications a ON a.id=f.application_id "
            "JOIN jobs j ON j.id=a.job_id ORDER BY COALESCE(f.due_at,f.created_at) DESC LIMIT 50"
        )]
        events = [dict(row) for row in connection.execute(
            "SELECT entity_type,entity_id,event_type,data_json,created_at FROM events ORDER BY id DESC LIMIT 30"
        )]
        profile_versions = [dict(row) for row in connection.execute(
            "SELECT public_id,version,source_resume_name,reviewed_at,created_at "
            "FROM profile_versions ORDER BY version DESC LIMIT 25"
        )]
        evidence_count = connection.execute("SELECT COUNT(*) FROM evidence WHERE verified=1").fetchone()[0]
        alert_rows = [dict(row) for row in connection.execute(
            "SELECT id,company,title,location,location_type,score,url,posting_date,created_at,score_json "
            "FROM jobs WHERE status!='archived' AND closed_at IS NULL AND score>=65 AND created_at>=? "
            "ORDER BY created_at DESC,score DESC LIMIT 20",
            ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(timespec="seconds"),),
        )]

    for job in jobs:
        job["evaluation"] = _loads(job.pop("score_json"), {})
    for material in materials:
        manifest = _loads(material.pop("manifest_json"), {})
        material["files"] = manifest.get("files", [])
        material["validation"] = manifest.get("validation", {})
    for event in events:
        event["data"] = _loads(event.pop("data_json"), {})
    for alert in alert_rows:
        alert["evaluation"] = _loads(alert.pop("score_json"), {})
    latest_runs = {}
    for run in search_runs:
        latest_runs.setdefault(run["source"], run)
    configured_sources = []
    stale_before = datetime.now(timezone.utc) - timedelta(minutes=20)
    for source in config.get("job_sources", []):
        source_name = f"{source.get('provider', '')}:{source.get('account', '')}"
        last_run = latest_runs.get(source_name, {})
        health = "awaiting"
        if last_run:
            health = "failed" if last_run.get("status") == "failed" else "healthy"
            try:
                checked_at = datetime.fromisoformat(str(last_run.get("finished_at", "")).replace("Z", "+00:00"))
                if health == "healthy" and checked_at.astimezone(timezone.utc) < stale_before:
                    health = "stale"
            except ValueError:
                health = "stale"
        configured_sources.append({
            "provider": source.get("provider", ""), "account": source.get("account", ""),
            "company": source.get("company", ""), "last_checked": last_run.get("finished_at"),
            "last_result_count": last_run.get("result_count"),
            "health": health, "error": last_run.get("error_text", ""),
        })
    connections = connection_registry(config)
    return {
        "profile": profile,
        "career_goal": career_goal(profile),
        "profile_versions": profile_versions,
        "verified_evidence_count": evidence_count,
        "counts": counts,
        "jobs": jobs,
        "applications": applications,
        "materials": materials,
        "documents": documents,
        "automation": automation,
        "interviews": interviews,
        "followups": followups,
        "events": events,
        "job_boards": board_registry(profile),
        "search_runs": search_runs,
        "fresh_alerts": alert_rows,
        "connections": connections,
        "configured_sources": configured_sources,
        "coverage": {
            "automatic_sources": len(configured_sources),
            "unhealthy_sources": sum(item["health"] in {"failed", "stale"} for item in configured_sources),
            "account_alerts": sum(item["state"] == "alerts_ready" for item in connections),
            "needs_setup": sum(item["state"] == "setup_required" for item in connections),
        },
    }


def subscription_status(
    execute: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    binary = shutil.which("codex")
    if not binary:
        return {"installed": False, "subscription_ready": False, "label": "Codex CLI not installed"}
    try:
        result = execute(
            [binary, "login", "status"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"installed": True, "subscription_ready": False, "label": f"Unable to check sign-in: {error}"}
    detail = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    ready = result.returncode == 0 and "chatgpt" in detail.lower()
    if ready:
        label = "Connected through ChatGPT"
    elif result.returncode == 0:
        label = "Codex is not using ChatGPT sign-in"
    else:
        label = "Sign in with ChatGPT to connect Codex"
    return {"installed": True, "subscription_ready": ready, "label": label, "detail": detail[:500]}


class CodexRunner:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runs: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        return subscription_status()

    def start_login(self) -> dict[str, str]:
        binary = shutil.which("codex")
        if not binary:
            raise ValueError("Install the Codex CLI before connecting your ChatGPT plan")
        flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        subprocess.Popen([binary, "login"], cwd=self.root, creationflags=flags)
        return {"state": "login_started", "instruction": "Finish Sign in with ChatGPT in the window that opened."}

    def start(self, prompt: str) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("Describe what you want Codex to do")
        auth = self.status()
        if not auth["subscription_ready"]:
            raise PermissionError("Connect Codex using Sign in with ChatGPT first. API-key billing is intentionally disabled.")
        with self.lock:
            if any(run["state"] == "running" for run in self.runs.values()):
                raise ValueError("Codex is already working on another request")
            run_id = uuid.uuid4().hex
            run = {"id": run_id, "state": "running", "prompt": prompt.strip(), "result": "", "events": []}
            self.runs[run_id] = run
        threading.Thread(target=self._execute, args=(run_id,), daemon=True).start()
        return dict(run)

    def get(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            if run_id not in self.runs:
                raise ValueError("Codex run not found")
            return dict(self.runs[run_id])

    def _execute(self, run_id: str) -> None:
        binary = shutil.which("codex")
        assert binary
        with self.lock:
            prompt = self.runs[run_id]["prompt"]
        environment = os.environ.copy()
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY"):
            environment.pop(key, None)
        command = [
            binary, "exec", "--json", "--sandbox", "workspace-write", "--approve-for-me",
            "-C", str(self.root), PROMPT_PREFIX + prompt,
        ]
        messages: list[str] = []
        try:
            process = subprocess.Popen(
                command, cwd=self.root, env=environment, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            )
            assert process.stdout
            for raw in process.stdout:
                line = raw.strip()
                if not line:
                    continue
                event = _loads(line, {"type": "log", "text": line})
                text = _event_text(event)
                if text:
                    messages.append(text)
                with self.lock:
                    self.runs[run_id]["events"] = (self.runs[run_id]["events"] + [event])[-80:]
            return_code = process.wait()
            result = messages[-1] if messages else "Codex finished without a text response. Refresh the dashboard to inspect changes."
            with self.lock:
                self.runs[run_id].update(state="complete" if return_code == 0 else "failed", result=result)
        except OSError as error:
            with self.lock:
                self.runs[run_id].update(state="failed", result=f"Could not start Codex: {error}")


class JobWatcher:
    def __init__(self, db: Database, interval_seconds: int = 300):
        self.db = db
        self.interval_seconds = max(60, interval_seconds)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self._status: dict[str, Any] = {
            "state": "idle", "last_scan_at": None, "next_scan_at": None,
            "last_result": None, "error": None,
        }

    def status(self) -> dict[str, Any]:
        with self.lock:
            return {**self._status, "interval_seconds": self.interval_seconds}

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()

    def trigger(self) -> dict[str, Any]:
        with self.lock:
            if self._status["state"] == "scanning":
                return {**self._status, "interval_seconds": self.interval_seconds}
            self._status.update(state="scanning", error=None, next_scan_at=None)
        threading.Thread(target=self._scan, daemon=True).start()
        return self.status()

    def _loop(self) -> None:
        self.trigger()
        while not self.stop_event.wait(self.interval_seconds):
            self.trigger()

    def _scan(self) -> None:
        try:
            config = load_config(self.db.path.parent / "config.json")
            result = scan_sources(self.db, load_profile(self.db), config.get("job_sources", []))
            error = "; ".join(f"{item['source']}: {item['error']}" for item in result["errors"]) or None
            state = "degraded" if error else "watching"
        except (OSError, RuntimeError, ValueError) as failure:
            result, error, state = None, str(failure), "failed"
        completed = datetime.now(timezone.utc)
        with self.lock:
            self._status.update(
                state=state, last_scan_at=completed.isoformat(timespec="seconds"),
                next_scan_at=(completed + timedelta(seconds=self.interval_seconds)).isoformat(timespec="seconds"),
                last_result=result, error=error,
            )


def _event_text(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    item = event.get("item")
    if isinstance(item, dict) and item.get("type") in {"agent_message", "message"}:
        return str(item.get("text") or item.get("content") or "").strip()
    if event.get("type") in {"agent_message", "message"}:
        return str(event.get("text") or event.get("content") or "").strip()
    return ""


class CareerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], db: Database, root: Path, runner: CodexRunner, watcher: JobWatcher):
        super().__init__(address, CareerHandler)
        self.db = db
        self.root = root.resolve()
        self.data_root = db.path.parent.resolve()
        self.runner = runner
        self.watcher = watcher
        self.token = secrets.token_urlsafe(32)


class CareerHandler(BaseHTTPRequestHandler):
    server: CareerServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def _json(self, value: Any, status: int = 200) -> None:
        payload = json.dumps(value, default=str).encode()
        self._headers(status, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def _authorized(self, query: dict[str, list[str]] | None = None) -> bool:
        supplied = self.headers.get("X-Career-Token") or (query or {}).get("token", [""])[0]
        return secrets.compare_digest(supplied, self.server.token)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("Request is too large")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/":
            text = (STATIC_ROOT / "index.html").read_text(encoding="utf-8").replace("__CAREER_TOKEN__", self.server.token)
            payload = text.encode()
            self._headers(200, "text/html; charset=utf-8", len(payload))
            self.wfile.write(payload)
            return
        if parsed.path.startswith("/static/"):
            name = parsed.path.removeprefix("/static/")
            if "/" in name or "\\" in name or name.startswith("."):
                self._json({"error": "Not found"}, 404)
                return
            path = STATIC_ROOT / name
            if not path.is_file():
                self._json({"error": "Not found"}, 404)
                return
            payload = path.read_bytes()
            self._headers(200, mimetypes.guess_type(path.name)[0] or "application/octet-stream", len(payload))
            self.wfile.write(payload)
            return
        if not self._authorized(query):
            self._json({"error": "Unauthorized local request"}, 403)
            return
        try:
            if parsed.path == "/api/state":
                state = dashboard_state(self.server.db)
                state["watcher"] = self.server.watcher.status()
                self._json(state)
            elif parsed.path == "/api/codex":
                self._json(self.server.runner.status())
            elif parsed.path.startswith("/api/runs/"):
                self._json(self.server.runner.get(parsed.path.rsplit("/", 1)[-1]))
            elif parsed.path.startswith("/api/documents/"):
                self._document(int(parsed.path.rsplit("/", 1)[-1]), query)
            else:
                self._json({"error": "Not found"}, 404)
        except (ValueError, PermissionError) as error:
            self._json({"error": str(error)}, 400)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._authorized():
            self._json({"error": "Unauthorized local request"}, 403)
            return
        try:
            body = self._body()
            if parsed.path == "/api/runs":
                prompt = str(body.get("prompt", "")).strip()
                if len(prompt) > 8000:
                    raise ValueError("Request must be 8,000 characters or fewer")
                self._json(self.server.runner.start(prompt), 202)
            elif parsed.path == "/api/codex/login":
                self._json(self.server.runner.start_login(), 202)
            elif parsed.path == "/api/jobs/scan":
                self._json(self.server.watcher.trigger(), 202)
            elif parsed.path == "/api/sources/recommended":
                self._json(self._install_recommended_sources(), 202)
            elif parsed.path.startswith("/api/connections/"):
                self._json(self._save_connection(parsed.path.rsplit("/", 1)[-1], body))
            elif parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/status"):
                parts = parsed.path.strip("/").split("/")
                status = str(body.get("status", ""))
                if status not in JOB_STATUSES:
                    raise ValueError("Unknown job status")
                update_status(self.server.db, int(parts[2]), status)
                self._json({"ok": True})
            else:
                self._json({"error": "Not found"}, 404)
        except (ValueError, PermissionError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, 400)

    def _save_connection(self, connection_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if connection_id not in {item["id"] for item in CONNECTIONS}:
            raise ValueError("Unknown job-board connection")
        private_config_path = self.server.db.path.parent / "config.json"
        config = load_config(private_config_path)
        if connection_id == "usajobs":
            email, api_key = str(body.get("email", "")).strip(), str(body.get("api_key", "")).strip()
            if "@" not in email or len(email) > 320:
                raise ValueError("Enter the email address used to request the USAJOBS API key")
            if len(api_key) < 8 or len(api_key) > 500:
                raise ValueError("Enter a valid USAJOBS API key")
            sources = [source for source in config.get("job_sources", []) if source.get("provider") != "usajobs"]
            for query in ("digital forensics", "incident response", "cybersecurity"):
                sources.append({
                    "provider": "usajobs", "account": query, "company": "US Federal Government",
                    "email": email, "api_key": api_key, "date_posted": 7,
                })
            config["job_sources"] = sources
        else:
            connections = config.setdefault("connections", {})
            connections[connection_id] = {"alerts_enabled": bool(body.get("alerts_enabled", True))}
        save_config(config, private_config_path)
        if connection_id == "usajobs":
            self.server.watcher.trigger()
        return next(item for item in connection_registry(config) if item["id"] == connection_id)

    def _install_recommended_sources(self) -> dict[str, Any]:
        private_config_path = self.server.db.path.parent / "config.json"
        config = load_config(private_config_path)
        sources = config.setdefault("job_sources", [])
        existing = {(source.get("provider"), source.get("account")) for source in sources}
        added = [dict(source) for source in RECOMMENDED_SOURCES if (source["provider"], source["account"]) not in existing]
        sources.extend(added)
        save_config(config, private_config_path)
        self.server.watcher.trigger()
        return {"added": len(added), "configured": len(sources), "scan": "started"}

    def _document(self, document_id: int, query: dict[str, list[str]]) -> None:
        with self.server.db.connect() as connection:
            row = connection.execute("SELECT path FROM document_versions WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise ValueError("Document not found")
        path = Path(row["path"]).resolve()
        try:
            path.relative_to(self.server.data_root)
        except ValueError as error:
            raise PermissionError("Document is outside the private data directory") from error
        if not path.is_file():
            raise ValueError("Document file is missing")
        payload = path.read_bytes()
        self._headers(200, mimetypes.guess_type(path.name)[0] or "application/octet-stream", len(payload))
        self.wfile.write(payload)


def make_server(
    db: Database, root: Path, port: int = 8765, runner: CodexRunner | None = None,
    watcher: JobWatcher | None = None,
) -> CareerServer:
    return CareerServer(("127.0.0.1", port), db, root, runner or CodexRunner(root), watcher or JobWatcher(db))


def serve(db: Database, root: Path, *, port: int = 8765, open_browser: bool = True) -> None:
    server = make_server(db, root, port)
    server.watcher.start()
    address = f"http://127.0.0.1:{server.server_port}/"
    print(f"Codex Career is running at {address}")
    print("Personal data stays local. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.35, webbrowser.open, args=(address,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCodex Career stopped.")
    finally:
        server.watcher.stop()
        server.server_close()
