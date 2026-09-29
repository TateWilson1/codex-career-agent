from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen


def json_request(url: str) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "codex-career/0.1"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def plain_text(value: str) -> str:
    text = value
    for marker in ("</p>", "</li>", "<br>", "<br/>", "<br />"):
        text = text.replace(marker, "\n")
    output = []
    inside = False
    for character in text:
        if character == "<":
            inside = True
        elif character == ">":
            inside = False
        elif not inside:
            output.append(character)
    return "\n".join(line.strip() for line in html.unescape("".join(output)).splitlines() if line.strip())


def greenhouse(board: str, company: str | None = None, fetch: Callable[[str], Any] = json_request) -> list[dict[str, Any]]:
    token = quote(board, safe="")
    board_data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}")
    data = fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    company_name = company or board_data.get("name") or board
    return [
        {
            "external_id": str(item["id"]),
            "company": company_name,
            "title": item["title"],
            "location": item.get("location", {}).get("name", ""),
            "url": item.get("absolute_url", ""),
            "posting_date": item.get("first_published") or item.get("updated_at", ""),
            "description": plain_text(item.get("content", "")),
        }
        for item in data.get("jobs", [])
    ]


def lever(site: str, company: str | None = None, fetch: Callable[[str], Any] = json_request) -> list[dict[str, Any]]:
    data = fetch(f"https://api.lever.co/v0/postings/{quote(site, safe='')}?mode=json")
    def timestamp(value: Any) -> str:
        try:
            return datetime.fromtimestamp(int(value) / 1000, timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""

    return [
        {
            "external_id": str(item["id"]),
            "company": company or site,
            "title": item["text"],
            "location": item.get("categories", {}).get("location", ""),
            "location_type": item.get("workplaceType", ""),
            "employment_type": item.get("categories", {}).get("commitment", ""),
            "url": item.get("hostedUrl", ""),
            "application_url": item.get("applyUrl", ""),
            "posting_date": timestamp(item.get("createdAt")),
            "salary_min": (item.get("salaryRange") or {}).get("min"),
            "salary_max": (item.get("salaryRange") or {}).get("max"),
            "currency": (item.get("salaryRange") or {}).get("currency", ""),
            "description": item.get("descriptionPlain") or plain_text(item.get("description", "")),
        }
        for item in data
    ]


def smartrecruiters(company_id: str, company: str | None = None, fetch: Callable[[str], Any] = json_request) -> list[dict[str, Any]]:
    token = quote(company_id, safe="")
    data = fetch(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100")
    output = []
    for item in data.get("content", []):
        location = item.get("location") or {}
        output.append({
            "external_id": str(item.get("id", "")),
            "company": company or item.get("company", {}).get("name") or company_id,
            "title": item.get("name", ""),
            "location": ", ".join(part for part in (location.get("city"), location.get("region"), location.get("country")) if part),
            "employment_type": item.get("typeOfEmployment", {}).get("label", ""),
            "posting_date": item.get("releasedDate", ""),
            "url": item.get("ref", "") or f"https://careers.smartrecruiters.com/{token}",
            "description": plain_text(item.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")),
        })
    return output


ADAPTERS: dict[str, tuple[str, Callable[..., list[dict[str, Any]]]]] = {
    "greenhouse": ("AUTOMATED", greenhouse),
    "lever": ("AUTOMATED", lever),
    "smartrecruiters": ("AUTOMATED", smartrecruiters),
}


def adapter_names() -> tuple[str, ...]:
    return tuple(sorted(ADAPTERS))


def source_capability(provider: str) -> str:
    try:
        return ADAPTERS[provider][0]
    except KeyError as error:
        raise ValueError(f"Unknown provider: {provider}") from error


def discover(provider: str, account: str, company: str | None = None) -> list[dict[str, Any]]:
    try:
        return ADAPTERS[provider][1](account, company)
    except KeyError as error:
        raise ValueError(f"Unknown provider: {provider}") from error
