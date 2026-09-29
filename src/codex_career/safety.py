from __future__ import annotations

import secrets
from typing import Any

from .answers import classify_answers

STOP_FIELD_TYPES = {"captcha", "mfa", "biometric", "credit_check", "background_consent", "legal_attestation"}
SENSITIVE_FIELD_TYPES = {"demographic", "disability", "veteran", "salary", "sponsorship", "criminal_history"}


def validate_fill_plan(plan: dict[str, Any], verified_answers: dict[str, Any], overrides: dict[str, str] | None = None) -> dict[str, Any]:
    safe_fields = []
    stops = []
    fields = classify_answers(plan.get("fields", []), set(verified_answers), overrides)
    for field in fields:
        kind = field.get("type", "text")
        key = field.get("answer_key")
        if kind in STOP_FIELD_TYPES:
            stops.append({"field": field.get("label", key), "reason": kind})
            continue
        if kind in SENSITIVE_FIELD_TYPES and not field.get("explicitly_approved"):
            stops.append({"field": field.get("label", key), "reason": f"approval_required:{kind}"})
            continue
        if field["classification"] == "USER_REQUIRED":
            stops.append({"field": field.get("label", key), "reason": "user_required"})
            continue
        if field["classification"] == "VERIFY" and not field.get("explicitly_approved"):
            stops.append({"field": field.get("label", key), "reason": "verification_required"})
            continue
        if key not in verified_answers:
            stops.append({"field": field.get("label", key), "reason": "unverified_answer"})
            continue
        safe_fields.append({**field, "value": verified_answers[key]})
    return {"fields": safe_fields, "stops": stops, "may_submit": False}


def new_approval_token() -> str:
    return secrets.token_urlsafe(24)


def authorize_submission(expected_token: str | None, supplied_token: str, confirmation: str) -> None:
    if not expected_token or not secrets.compare_digest(expected_token, supplied_token):
        raise PermissionError("Submission approval token is missing or invalid")
    if confirmation != "SUBMIT THIS APPLICATION":
        raise PermissionError("Exact per-application confirmation is required")
