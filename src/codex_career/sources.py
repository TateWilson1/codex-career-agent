from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def json_request(url: str, headers: dict[str, str] | None = None) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "codex-career/0.1", **(headers or {})})
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


def greenhouse(board: str, company: str | None = None, fetch: Callable[[str], Any] = json_request, **_: Any) -> list[dict[str, Any]]:
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


def lever(site: str, company: str | None = None, fetch: Callable[[str], Any] = json_request, **_: Any) -> list[dict[str, Any]]:
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


def smartrecruiters(company_id: str, company: str | None = None, fetch: Callable[[str], Any] = json_request, **_: Any) -> list[dict[str, Any]]:
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


def ashby(board: str, company: str | None = None, fetch: Callable[[str], Any] = json_request, **_: Any) -> list[dict[str, Any]]:
    data = fetch(f"https://api.ashbyhq.com/posting-api/job-board/{quote(board, safe='')}?includeCompensation=true")
    output = []
    for item in data.get("jobs", []):
        if item.get("isListed") is False:
            continue
        compensation = item.get("compensation") or {}
        salary = next((part for part in compensation.get("summaryComponents", []) if part.get("compensationType") == "Salary"), {})
        output.append({
            "external_id": str(item.get("id", "")),
            "company": company or board,
            "title": item.get("title", ""),
            "location": item.get("location", ""),
            "location_type": item.get("workplaceType", ""),
            "employment_type": item.get("employmentType", ""),
            "url": item.get("jobUrl", ""),
            "application_url": item.get("applyUrl", ""),
            "posting_date": item.get("publishedAt", ""),
            "description": plain_text(item.get("descriptionHtml", "")) or item.get("descriptionPlain", ""),
            "salary_min": salary.get("minValue"),
            "salary_max": salary.get("maxValue"),
            "currency": salary.get("currencyCode", ""),
        })
    return output


def usajobs(
    query: str, company: str | None = None, fetch: Callable[[str, dict[str, str]], Any] | None = None,
    **options: Any,
) -> list[dict[str, Any]]:
    email, api_key = str(options.get("email", "")).strip(), str(options.get("api_key", "")).strip()
    if not email or not api_key:
        raise ValueError("USAJOBS requires the account email and free API key")
    parameters = {
        "Keyword": query, "WhoMayApply": "Public", "DatePosted": str(options.get("date_posted", 7)),
        "ResultsPerPage": "500", "Fields": "Full",
    }
    if options.get("location"):
        parameters["LocationName"] = str(options["location"])
    if options.get("remote") is True:
        parameters["RemoteIndicator"] = "True"
    url = f"https://data.usajobs.gov/api/Search?{urlencode(parameters)}"
    headers = {"Authorization-Key": api_key, "User-Agent": email, "Host": "data.usajobs.gov"}
    data = fetch(url, headers) if fetch else json_request(url, headers)
    items = data.get("SearchResult", {}).get("SearchResultItems", [])
    output = []
    for entry in items:
        item = entry.get("MatchedObjectDescriptor", {})
        details = item.get("UserArea", {}).get("Details", {})
        pay = (item.get("PositionRemuneration") or [{}])[0]
        apply_urls = item.get("ApplyURI") or []
        output.append({
            "external_id": str(item.get("PositionID") or entry.get("MatchedObjectId", "")),
            "company": item.get("OrganizationName") or company or "US Federal Government",
            "title": item.get("PositionTitle", ""),
            "location": item.get("PositionLocationDisplay", ""),
            "employment_type": ", ".join(
                value.get("Name", "") if isinstance(value, dict) else str(value)
                for value in (item.get("PositionSchedule") or [])
            ),
            "url": item.get("PositionURI", ""),
            "application_url": apply_urls[0] if apply_urls else item.get("PositionURI", ""),
            "posting_date": item.get("PublicationStartDate", ""),
            "expires_at": item.get("ApplicationCloseDate", ""),
            "description": "\n".join(str(details.get(key, "")) for key in ("JobSummary", "MajorDuties", "Education", "Requirements", "Evaluations") if details.get(key)),
            "salary_min": pay.get("MinimumRange"),
            "salary_max": pay.get("MaximumRange"),
            "currency": "USD",
            "clearance_requirement": details.get("SecurityClearance", ""),
            "travel_requirement": details.get("TravelCode", ""),
        })
    return output


ADAPTERS: dict[str, tuple[str, Callable[..., list[dict[str, Any]]]]] = {
    "ashby": ("AUTOMATED", ashby),
    "greenhouse": ("AUTOMATED", greenhouse),
    "lever": ("AUTOMATED", lever),
    "smartrecruiters": ("AUTOMATED", smartrecruiters),
    "usajobs": ("AUTOMATED", usajobs),
}


def adapter_names() -> tuple[str, ...]:
    return tuple(sorted(ADAPTERS))


def source_capability(provider: str) -> str:
    try:
        return ADAPTERS[provider][0]
    except KeyError as error:
        raise ValueError(f"Unknown provider: {provider}") from error


def discover(provider: str, account: str, company: str | None = None, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        safe_options = {key: value for key, value in (options or {}).items() if key not in {"provider", "account", "company"}}
        return ADAPTERS[provider][1](account, company, **safe_options)
    except KeyError as error:
        raise ValueError(f"Unknown provider: {provider}") from error
