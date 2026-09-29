from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .db import Database, now
from .ids import new_id


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def contains_phrase(text: str, phrase: str) -> bool:
    phrase = normalized(phrase)
    return bool(phrase) and f" {phrase} " in f" {normalized(text)} "


def fingerprint(job: dict[str, Any], source: str = "manual") -> str:
    url = job.get("url", "").split("?", 1)[0].rstrip("/")
    external = str(job.get("external_id", "")).strip()
    identity = url or (f"{source}|{external}" if external else "|".join(
        normalized(str(job.get(k, ""))) for k in ("company", "title", "location", "posting_date", "description")
    ))
    return hashlib.sha256(identity.encode()).hexdigest()


def normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    def text(key: str) -> str:
        return str(raw.get(key, "") or "").strip()

    def number(key: str) -> int | None:
        value = raw.get(key)
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError as error:
            raise ValueError(f"{key} must be numeric") from error

    def items(key: str) -> str:
        value = raw.get(key, [])
        if isinstance(value, str):
            value = [value] if value.strip() else []
        if not isinstance(value, list):
            raise ValueError(f"{key} must be a list or string")
        return json.dumps(value, sort_keys=True)

    job = {key: text(key) for key in (
        "external_id", "company", "title", "company_url", "location", "location_type",
        "employment_type", "currency", "url", "application_url", "posting_date", "expires_at",
        "description", "clearance_requirement", "work_authorization_requirement", "travel_requirement",
    )}
    job.update(
        salary_min=number("salary_min"), salary_max=number("salary_max"),
        responsibilities_json=items("responsibilities"),
        required_qualifications_json=items("required_qualifications"),
        preferred_qualifications_json=items("preferred_qualifications"),
    )
    return job


def read_jobs(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data["jobs"]
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    raise ValueError("Jobs import must be JSON or CSV")


def import_jobs(db: Database, jobs: Iterable[dict[str, Any]], source: str, capability: str = "MANUAL_ONLY") -> dict[str, int]:
    if capability not in {"AUTOMATED", "ASSISTED", "MANUAL_ONLY"}:
        raise ValueError("Invalid source capability")
    inserted = updated = 0
    timestamp = now()
    with db.connect() as connection:
        adapter, _, external_key = source.partition(":")
        external_key = external_key or source
        source_row = connection.execute(
            "SELECT id FROM job_sources WHERE adapter=? AND external_key=?", (adapter, external_key)
        ).fetchone()
        if source_row:
            job_source_id = source_row["id"]
        else:
            job_source_id = connection.execute(
                "INSERT INTO job_sources(public_id,adapter,external_key,capability,created_at) VALUES(?,?,?,?,?) RETURNING id",
                (new_id("src"), adapter, external_key, capability, timestamp),
            ).fetchone()["id"]
        for raw in jobs:
            if not raw.get("company") or not raw.get("title"):
                raise ValueError("Every job needs company and title")
            job = normalize_job(raw)
            mark = fingerprint(job, source)
            company_key = normalized(job["company"])
            company_row = connection.execute("SELECT id FROM companies WHERE normalized_name=?", (company_key,)).fetchone()
            if company_row:
                company_id = company_row["id"]
                if job["company_url"]:
                    connection.execute("UPDATE companies SET url=?, updated_at=? WHERE id=?", (job["company_url"], timestamp, company_id))
            else:
                company_id = connection.execute(
                    "INSERT INTO companies(public_id,normalized_name,name,url,created_at,updated_at) VALUES(?,?,?,?,?,?) RETURNING id",
                    (new_id("co"), company_key, job["company"], job["company_url"], timestamp, timestamp),
                ).fetchone()["id"]
            existing = connection.execute("SELECT * FROM jobs WHERE fingerprint=?", (mark,)).fetchone()
            values = {
                **job, "company_id": company_id, "job_source_id": job_source_id,
                "original_content": json.dumps(raw, sort_keys=True, default=str), "updated_at": timestamp,
            }
            if existing:
                for key, value in list(values.items()):
                    if key == "original_content":
                        values[key] = existing[key]
                    elif value in (None, "", "[]") and existing[key] not in (None, "", "[]"):
                        values[key] = existing[key]
                assignments = ",".join(f"{key}=?" for key in values)
                connection.execute(f"UPDATE jobs SET {assignments} WHERE id=?", (*values.values(), existing["id"]))
                updated += 1
            else:
                values.update(public_id=new_id("job"), fingerprint=mark, source=source, created_at=timestamp)
                columns = ",".join(values)
                placeholders = ",".join("?" for _ in values)
                connection.execute(
                    f"INSERT INTO jobs({columns}) VALUES({placeholders})", tuple(values.values())
                )
                inserted += 1
    return {"inserted": inserted, "updated": updated}


def score_job(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    haystack = " ".join((job.get("title", ""), job.get("description", ""), job.get("location", "")))
    skills = [str(skill) for skill in profile.get("skills", [])]
    matched = [skill for skill in skills if contains_phrase(haystack, skill)]
    required = json.loads(job.get("required_qualifications_json") or "[]")
    profile_text = json.dumps(profile, sort_keys=True)
    matched_requirements = [item for item in required if contains_phrase(profile_text, str(item)) or any(contains_phrase(str(item), skill) for skill in skills)]
    missing_requirements = [item for item in required if item not in matched_requirements]
    title = normalized(job.get("title", ""))
    description = normalized(job.get("description", ""))
    location = normalized(job.get("location", ""))
    target_match = any(contains_phrase(title, role) or contains_phrase(role, title) for role in profile.get("target_roles", []))
    location_match = any(contains_phrase(location, place) for place in profile.get("locations", []))
    preferences = profile.get("preferences", {})
    if "digital forensic" in title or "dfir" in title or ("forensic" in title and "cyber" in title):
        role_points = 30
    elif "incident response" in title:
        role_points = 27
    elif any(term in title for term in ("soc analyst", "security analyst", "cybersecurity analyst", "cyber analyst")):
        role_points = 23
    elif any(term in title for term in ("iam", "identity", "grc", "security engineer")):
        role_points = 16
    elif target_match:
        role_points = 20
    else:
        role_points = 4 if any(term in description for term in ("digital forensic", "incident response", "security operations")) else 0

    skill_points = min(25, len(matched) * 3)
    experience_text = f"{title} {description}"
    senior = bool(re.search(r"\b(senior|sr|lead|principal|manager|director)\b", title))
    years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s*(?:-|to\s*\d+\s*)?years?", experience_text)]
    minimum_years = max(years, default=0)
    entry_language = any(term in experience_text for term in ("entry level", "entry-level", "new graduate", "recent graduate", "internship", "intern "))
    experience_points = 15 if entry_language else (10 if minimum_years <= 2 and not senior else (4 if minimum_years <= 3 else 0))

    remote = "remote" in f"{location} {normalized(job.get('location_type', ''))}"
    kentucky = any(term in location for term in ("kentucky", "lexington", "richmond ky", "louisville", "frankfort"))
    location_points = 10 if remote or location_match else (8 if kentucky else (4 if preferences.get("relocation") else 0))
    employment = normalized(job.get("employment_type", ""))
    contract_only = "contract" in employment or "contract only" in description
    employment_points = 5 if any(term in employment for term in ("full time", "intern")) else (2 if not employment else 0)
    mission_points = 5 if any(term in f"{title} {description}" for term in ("forensic", "incident response", "investigation", "government", "public sector", "law enforcement", "defense", "security operations")) else 0

    age_hours: float | None = None
    posting_date = str(job.get("posting_date") or "").strip()
    if posting_date:
        try:
            parsed = datetime.fromisoformat(posting_date.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600)
        except ValueError:
            age_hours = None
    if age_hours is None:
        freshness_points, freshness = 2, "date unknown"
    elif age_hours <= 24:
        freshness_points, freshness = 10, "first 24 hours"
    elif age_hours <= 72:
        freshness_points, freshness = 7, "2–3 days old"
    elif age_hours <= 168:
        freshness_points, freshness = 4, "4–7 days old"
    else:
        freshness_points, freshness = 1, "older than 7 days"

    deductions: list[dict[str, Any]] = []
    education_text = json.dumps(profile.get("education", []), sort_keys=True).lower()
    expected_years = set(re.findall(r"expected[^0-9]{0,30}(20\d{2})", education_text))
    graduation_items = [job.get("title", ""), *required, *re.split(r"[\n.!?]", job.get("description", ""))]
    graduation_requirements = " ".join(
        str(item) for item in graduation_items
        if any(term in normalized(str(item)) for term in ("graduate", "graduating", "degree candidate"))
    )
    eligible_graduation_years = set(re.findall(r"20\d{2}", graduation_requirements))
    education_fit: bool | str = "UNKNOWN"
    if expected_years and eligible_graduation_years:
        education_fit = bool(expected_years & eligible_graduation_years)
        if not education_fit:
            deductions.append({
                "reason": f"Graduate hiring window lists {', '.join(sorted(eligible_graduation_years))}; verified graduation is {', '.join(sorted(expected_years))}",
                "points": 25,
            })
    clearance = normalized(job.get("clearance_requirement", "")) or description
    if profile.get("security_clearance", "").lower() == "none" and re.search(r"active\s+(?:top secret|ts|secret)|current\s+(?:top secret|ts|secret)", clearance):
        deductions.append({"reason": "Requires an active clearance not in the verified profile", "points": 20})
    if minimum_years >= 5:
        deductions.append({"reason": f"Requests at least {minimum_years} years of experience", "points": 20})
    elif minimum_years >= 3:
        deductions.append({"reason": f"Requests at least {minimum_years} years of experience", "points": 8})
    if senior:
        deductions.append({"reason": "Title signals a senior-level role", "points": 12})
    if contract_only:
        deductions.append({"reason": "Contract work is lower priority", "points": 8})
    travel_text = normalized(job.get("travel_requirement", ""))
    if any(term in travel_text for term in ("extensive", "frequent", "50", "75", "100")):
        deductions.append({"reason": "Travel appears greater than the stated preference", "points": 8})

    breakdown = {
        "role alignment": role_points,
        "verified skills": skill_points,
        "entry-level fit": experience_points,
        "location / work mode": location_points,
        "employment type": employment_points,
        "career direction": mission_points,
        "freshness": freshness_points,
    }
    score = max(0, min(100, sum(breakdown.values()) - sum(item["points"] for item in deductions)))
    recommendation = "excellent" if score >= 80 else "strong" if score >= 65 else "stretch" if score >= 50 else "low"
    weights = {"role": 30, "skills": 25, "experience": 15, "location": 10, "employment": 5, "mission": 5, "freshness": 10}
    location_type = str(job.get("location_type", "unknown"))
    preferred_modes = [normalized(str(item)) for item in preferences.get("work_modes", [])]
    remote_fit: bool | None = None if not preferred_modes or location_type == "unknown" else normalized(location_type) in preferred_modes
    preferred_types = [normalized(str(item)) for item in preferences.get("employment_types", [])]
    employment_fit: bool | str = "UNKNOWN" if not preferred_types or not job.get("employment_type") else normalized(str(job["employment_type"])) in preferred_types
    desired_salary = preferences.get("minimum_salary") or preferences.get("salary_min")
    salary_fit: bool | str = "UNKNOWN"
    if desired_salary and job.get("salary_max") is not None:
        salary_fit = int(job["salary_max"]) >= int(desired_salary)
    return {
        "score": score,
        "weights": weights,
        "breakdown": breakdown,
        "deductions": deductions,
        "recommendation": recommendation,
        "freshness": freshness,
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "strong_matches": matched,
        "matched_requirements": matched_requirements,
        "partial_matches": [],
        "missing_requirements": missing_requirements,
        "target_role_fit": target_match,
        "location_fit": location_match,
        "remote_fit": remote_fit,
        "employment_type_fit": employment_fit,
        "salary_fit": salary_fit,
        "education_fit": education_fit,
        "experience_level_fit": not senior and minimum_years <= 2,
        "transferable_experience": [],
        "clearance_concern": job.get("clearance_requirement") or None,
        "work_authorization_concern": job.get("work_authorization_requirement") or None,
        "travel_expectation": job.get("travel_requirement") or None,
        "notes": ["UNKNOWN means the posting or verified profile does not provide enough information."],
    }


def evaluate_jobs(db: Database, profile: dict[str, Any], job_id: int | None = None) -> int:
    count = 0
    with db.connect() as connection:
        rows = connection.execute("SELECT * FROM jobs" if job_id is None else "SELECT * FROM jobs WHERE id=?", () if job_id is None else (job_id,)).fetchall()
        if job_id is not None and not rows:
            raise ValueError(f"Job {job_id} not found")
        profile_version = connection.execute("SELECT id FROM profile_versions ORDER BY version DESC LIMIT 1").fetchone()
        for row in rows:
            result = score_job(dict(row), profile)
            connection.execute(
                "UPDATE jobs SET score=?, score_json=?, updated_at=? WHERE id=?",
                (result["score"], json.dumps(result, sort_keys=True), now(), row["id"]),
            )
            version = connection.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM job_evaluations WHERE job_id=?", (row["id"],)
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO job_evaluations(public_id, job_id, profile_version_id, version, factors_json, score, created_at) VALUES(?,?,?,?,?,?,?)",
                (new_id("eval"), row["id"], profile_version["id"] if profile_version else None, version, json.dumps(result, sort_keys=True), result["score"], now()),
            )
            count += 1
    return count


def record_search_run(db: Database, source: str, query: dict[str, Any], result_count: int) -> None:
    timestamp = now()
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO search_runs(public_id,source,query_json,result_count,started_at,finished_at) VALUES(?,?,?,?,?,?)",
            (new_id("search"), source, json.dumps(query, sort_keys=True), result_count, timestamp, timestamp),
        )


def scan_sources(
    db: Database,
    profile: dict[str, Any],
    sources: list[dict[str, Any]],
    discoverer: Callable[[str, str, str | None], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    from .sources import discover, source_capability

    if not sources:
        raise ValueError("No automated job sources are configured")
    configured_discoverer = discoverer
    started = now()
    summary: dict[str, Any] = {"sources": [], "checked": 0, "inserted": 0, "updated": 0, "archived": 0, "errors": []}
    role_terms = {
        "cyber", "security", "forensic", "incident response", "soc", "threat", "vulnerability",
        "identity", "iam", "grc", "governance risk", "information assurance", "digital evidence",
    }
    for entry in sources:
        provider = str(entry.get("provider", "")).strip().lower()
        account = str(entry.get("account", "")).strip()
        company = str(entry.get("company", "")).strip() or None
        if not provider or not account:
            summary["errors"].append({"source": provider or "unknown", "error": "provider and account are required"})
            continue
        source = f"{provider}:{account}"
        try:
            found = configured_discoverer(provider, account, company) if configured_discoverer else discover(provider, account, company, entry)
            relevant = [job for job in found if any(contains_phrase(str(job.get("title", "")), term) for term in role_terms)]
            result = import_jobs(db, relevant, source, source_capability(provider))
            record_search_run(db, source, {"account": account, "company": company}, len(found))
            summary["sources"].append({"source": source, "checked": len(found), "relevant": len(relevant), **result})
            for key in ("checked", "inserted", "updated"):
                summary[key] += len(found) if key == "checked" else result[key]
            with db.connect() as connection:
                stale = connection.execute(
                    "SELECT id,title FROM jobs WHERE source=? AND status='discovered'", (source,)
                ).fetchall()
            for row in stale:
                if not any(contains_phrase(row["title"], term) for term in role_terms):
                    update_status(db, row["id"], "archived")
                    summary["archived"] += 1
        except (OSError, RuntimeError, ValueError) as error:
            summary["errors"].append({"source": source, "error": str(error)})
    if summary["sources"]:
        evaluate_jobs(db, profile)
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT id,company,title,location,score,url,score_json FROM jobs "
            "WHERE created_at>=? AND score>=65 ORDER BY score DESC,id DESC", (started,)
        ).fetchall()
    summary["new_strong_matches"] = [
        {**{key: row[key] for key in ("id", "company", "title", "location", "score", "url")},
         "freshness": json.loads(row["score_json"] or "{}").get("freshness", "date unknown")}
        for row in rows
    ]
    return summary


JOB_STATUSES = {"discovered", "interested", "applying", "applied", "interviewing", "rejected", "withdrawn", "archived"}


def update_status(db: Database, job_id: int, status: str) -> None:
    if status not in JOB_STATUSES:
        raise ValueError(f"Invalid job status: {status}")
    timestamp = now()
    with db.connect() as connection:
        current = connection.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        changed = connection.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, timestamp, job_id)).rowcount
        if changed:
            connection.execute(
                "INSERT INTO job_status_history(public_id, job_id, from_status, to_status, created_at) VALUES(?,?,?,?,?)",
                (new_id("jsh"), job_id, current["status"] if current else None, status, timestamp),
            )
    if not changed:
        raise ValueError(f"Job {job_id} not found")
    db.event("job", job_id, "status_changed", {"status": status})
