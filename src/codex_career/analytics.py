from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

from .db import Database


def search_analytics(db: Database) -> dict[str, Any]:
    with db.connect() as connection:
        jobs = connection.execute("SELECT status, source, title, location FROM jobs").fetchall()
        applications = connection.execute(
            "SELECT a.id,a.status,a.submitted_at,j.title,j.location,j.source,m.template_id,m.tailoring_mode "
            "FROM applications a JOIN jobs j ON j.id=a.job_id LEFT JOIN material_sets m ON m.id=a.material_set_id"
        ).fetchall()
        evaluations = connection.execute(
            "SELECT e.factors_json FROM job_evaluations e JOIN (SELECT job_id,MAX(version) version FROM job_evaluations GROUP BY job_id) latest "
            "ON latest.job_id=e.job_id AND latest.version=e.version"
        ).fetchall()
        response_rows = connection.execute(
            "SELECT a.submitted_at,MIN(h.created_at) response_at FROM applications a JOIN application_status_history h ON h.application_id=a.id "
            "WHERE a.submitted_at IS NOT NULL AND h.to_status IN ('screening','interview','final_interview','offer','rejected') GROUP BY a.id"
        ).fetchall()
        search_runs = connection.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
    app_statuses = Counter(row["status"] for row in applications)
    submitted = sum(1 for row in applications if row["submitted_at"])
    interviews = sum(app_statuses[key] for key in ("interview", "final_interview", "offer"))
    responses = sum(app_statuses[key] for key in ("screening", "interview", "final_interview", "offer", "rejected"))
    gaps: Counter[str] = Counter()
    for row in evaluations:
        factors = json.loads(row["factors_json"])
        gaps.update(str(item) for item in factors.get("missing_requirements", []))
    response_days = [
        (datetime.fromisoformat(row["response_at"].replace("Z", "+00:00")) - datetime.fromisoformat(row["submitted_at"].replace("Z", "+00:00"))).total_seconds() / 86400
        for row in response_rows if row["response_at"]
    ]
    return {
        "jobs_discovered": len(jobs),
        "search_runs": search_runs,
        "jobs_by_source": dict(Counter(row["source"] for row in jobs)),
        "jobs_by_role": dict(Counter(row["title"] for row in jobs)),
        "jobs_by_geography": dict(Counter(row["location"] or "UNKNOWN" for row in jobs)),
        "applications": len(applications),
        "submitted": submitted,
        "interviews": interviews,
        "offers": app_statuses["offer"],
        "response_rate": round(responses / submitted, 3) if submitted else None,
        "average_response_days": round(sum(response_days) / len(response_days), 2) if response_days else None,
        "resume_variant_performance": dict(Counter(f"{row['template_id']}:{row['tailoring_mode']}" for row in applications if row["template_id"])),
        "common_gaps": [{"skill": skill, "count": count} for skill, count in gaps.most_common(10)],
        "advice_policy": "Suggestions require user approval; analytics never rewrites career goals.",
    }
