from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus


JOB_BOARDS = (
    {
        "name": "Employer Greenhouse boards",
        "kind": "automated",
        "priority": "high",
        "fit_tags": "all",
        "coverage": "Direct employer postings",
        "note": "Public official API; add an employer board token once and poll it without an account.",
        "url": "https://www.greenhouse.com/",
    },
    {
        "name": "Employer Lever boards",
        "kind": "automated",
        "priority": "high",
        "fit_tags": "all",
        "coverage": "Direct employer postings",
        "note": "Public official API; add an employer site name once and poll it without an account.",
        "url": "https://jobs.lever.co/",
    },
    {
        "name": "Employer SmartRecruiters boards",
        "kind": "automated",
        "priority": "high",
        "fit_tags": "all",
        "coverage": "Direct employer postings",
        "note": "Public Posting API; strongest for employers already known to use SmartRecruiters.",
        "url": "https://careers.smartrecruiters.com/",
    },
    {
        "name": "Employer Ashby boards",
        "kind": "automated",
        "priority": "high",
        "fit_tags": "all",
        "coverage": "Direct employer postings",
        "note": "Official public postings API with compensation data when an employer exposes it.",
        "url": "https://jobs.ashbyhq.com/",
    },
    {
        "name": "USAJOBS / DHS Cybersecurity Service",
        "kind": "key required",
        "priority": "medium",
        "fit_tags": "government federal public sector digital forensic incident response",
        "coverage": "Federal cyber and digital forensics",
        "note": "Best mission match. Automated search needs a free USAJOBS API key and email; saved searches remain available without one.",
        "url": "https://www.usajobs.gov/Search/Results?k=digital%20forensics",
    },
    {
        "name": "FBIJobs",
        "kind": "assisted",
        "priority": "medium",
        "fit_tags": "federal law enforcement investigation digital forensic",
        "coverage": "Federal digital forensics and investigations",
        "note": "Direct strategic target. Use its account alerts; Codex reviews and imports eligible external openings.",
        "url": "https://apply.fbijobs.gov/psc/ps/EMPLOYEE/HRMS/c/HRS_HRAM_FL.HRS_CG_SEARCH_FL.GBL",
    },
    {
        "name": "Handshake",
        "kind": "assisted",
        "priority": "medium",
        "fit_tags": "student internship new graduate entry level",
        "coverage": "Student, internship, and new-graduate roles",
        "note": "Excellent fit before December 2026. University sign-in prevents unattended polling; enable saved-search alerts.",
        "url": "https://app.joinhandshake.com/stu/postings",
    },
    {
        "name": "LinkedIn Jobs",
        "kind": "alerts",
        "priority": "high",
        "fit_tags": "all",
        "coverage": "Broad professional market",
        "note": "Use daily alerts and direct-employer links. No scraping or auto-submit connection is used.",
        "url": "https://www.linkedin.com/jobs/search/?keywords=digital%20forensics%20OR%20incident%20response%20OR%20SOC%20analyst&location=Kentucky%2C%20United%20States&f_TPR=r86400",
    },
    {
        "name": "Indeed",
        "kind": "alerts",
        "priority": "high",
        "fit_tags": "all",
        "coverage": "Broad local and remote market",
        "note": "Useful for Kentucky coverage. Alerts are connected through the board; canonical employer postings are preferred.",
        "url": "https://www.indeed.com/jobs?q=digital+forensics+OR+incident+response+OR+soc+analyst&l=Kentucky&fromage=1",
    },
    {
        "name": "ClearanceJobs",
        "kind": "assisted",
        "priority": "medium",
        "fit_tags": "defense security clearance",
        "coverage": "Defense and cleared cyber",
        "note": "Career-aligned, but roles requiring an active clearance are penalized because the verified profile says none.",
        "url": "https://www.clearancejobs.com/jobs",
    },
    {
        "name": "CyberSN",
        "kind": "assisted",
        "priority": "medium",
        "fit_tags": "cybersecurity security",
        "coverage": "Cybersecurity-specialist roles",
        "note": "Useful supplemental cyber source; account-gated features stay under the user's control.",
        "url": "https://cybersn.com/",
    },
    {
        "name": "Team Kentucky Careers",
        "kind": "assisted",
        "priority": "medium",
        "fit_tags": "kentucky government public sector",
        "coverage": "Kentucky public-sector roles",
        "note": "Strong location and public-service fit. Use the official portal's notifications and import matching listings.",
        "url": "https://kypersonnelcabinet.csod.com/ats/careersite/search.aspx?site=2&c=kypersonnelcabinet",
    },
)


CONNECTIONS = (
    {"id": "usajobs", "name": "USAJOBS", "mode": "api", "url": "https://developer.usajobs.gov/APIRequest/Index", "coverage": "Federal public, recent-graduate, cyber, and remote openings", "setup": "Request a free API key, then save it here with the same email address."},
    {"id": "linkedin", "name": "LinkedIn Jobs", "mode": "alerts", "url": "https://www.linkedin.com/jobs/", "coverage": "Broad employer and recruiter market", "setup": "Sign in and create immediate alerts for the saved searches you want imported."},
    {"id": "indeed", "name": "Indeed", "mode": "alerts", "url": "https://www.indeed.com/", "coverage": "Broad local, remote, and smaller-employer coverage", "setup": "Sign in and enable alerts; use the employer posting as the canonical link when available."},
    {"id": "handshake", "name": "Handshake", "mode": "alerts", "url": "https://app.joinhandshake.com/", "coverage": "Internships, university recruiting, and new-graduate roles", "setup": "Use your university sign-in and enable alerts for entry-level cybersecurity searches."},
    {"id": "clearancejobs", "name": "ClearanceJobs", "mode": "alerts", "url": "https://www.clearancejobs.com/", "coverage": "Defense and cleared cybersecurity", "setup": "Sign in and alert on roles that do not require an active clearance or can sponsor one."},
    {"id": "fbijobs", "name": "FBIJobs", "mode": "alerts", "url": "https://apply.fbijobs.gov/", "coverage": "Federal law-enforcement and cyber-investigation roles", "setup": "Create your account and official notifications; application steps remain user-controlled."},
    {"id": "kentucky", "name": "Team Kentucky Careers", "mode": "alerts", "url": "https://kypersonnelcabinet.csod.com/ats/careersite/search.aspx?site=2&c=kypersonnelcabinet", "coverage": "Kentucky state government and local public service", "setup": "Create an account and save Kentucky technology and security searches."},
    {"id": "cybersn", "name": "CyberSN", "mode": "alerts", "url": "https://cybersn.com/", "coverage": "Cybersecurity-specialist roles", "setup": "Create an account and enable matching notifications."},
)


RECOMMENDED_SOURCES = (
    {"provider": "greenhouse", "account": "atbayjobs", "company": "At-Bay"},
    {"provider": "greenhouse", "account": "charlesriverassociates", "company": "Charles River Associates"},
    {"provider": "greenhouse", "account": "surefirecyber", "company": "Surefire Cyber"},
    {"provider": "greenhouse", "account": "guidepointsecurity", "company": "GuidePoint Security"},
    {"provider": "greenhouse", "account": "accenturefederalservices", "company": "Accenture Federal Services"},
    {"provider": "greenhouse", "account": "srm", "company": "S-RM"},
    {"provider": "lever", "account": "agile-defense", "company": "Agile Defense"},
    {"provider": "lever", "account": "CYE", "company": "CYE"},
    {"provider": "lever", "account": "uvcyber", "company": "UltraViolet Cyber"},
    {"provider": "ashby", "account": "horizon3ai", "company": "Horizon3.ai"},
    {"provider": "ashby", "account": "checkout.com", "company": "Checkout.com"},
    {"provider": "ashby", "account": "miovision", "company": "Miovision"},
)


def board_registry(profile: dict[str, Any] | None = None) -> list[dict[str, str]]:
    profile_text = " ".join(str(value) for value in (
        (profile or {}).get("career_level", ""),
        *((profile or {}).get("target_roles") or []),
        *((profile or {}).get("locations") or []),
        *((profile or {}).get("preferences", {}).get("industries") or []),
    )).lower()
    primary_role = ((profile or {}).get("target_roles") or ["cybersecurity"])[0]
    location = ((profile or {}).get("locations") or [""])[0]
    output = []
    for value in JOB_BOARDS:
        board = dict(value)
        tags = board.pop("fit_tags", "")
        if tags != "all" and any(term in profile_text for term in tags.split()):
            board["priority"] = "highest" if board["name"] in {"USAJOBS / DHS Cybersecurity Service", "FBIJobs", "Handshake"} else "high"
        if board["name"] == "USAJOBS / DHS Cybersecurity Service":
            board["url"] = f"https://www.usajobs.gov/Search/Results?k={quote_plus(primary_role)}"
        elif board["name"] == "LinkedIn Jobs":
            board["url"] = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(primary_role)}&location={quote_plus(location)}&f_TPR=r86400"
        elif board["name"] == "Indeed":
            board["url"] = f"https://www.indeed.com/jobs?q={quote_plus(primary_role)}&l={quote_plus(location)}&fromage=1"
        output.append(board)
    order = {"highest": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(output, key=lambda item: (order.get(item["priority"], 9), item["name"]))


def connection_registry(config: dict[str, Any]) -> list[dict[str, Any]]:
    confirmed = config.get("connections", {})
    sources = config.get("job_sources", [])
    output = []
    for connection in CONNECTIONS:
        item = dict(connection)
        if item["id"] == "usajobs":
            source = next((source for source in sources if source.get("provider") == "usajobs"), {})
            item["state"] = "connected" if source.get("api_key") and source.get("email") else "setup_required"
            item["detail"] = "Private API credentials saved" if item["state"] == "connected" else "Free API key required"
        else:
            ready = bool(confirmed.get(item["id"], {}).get("alerts_enabled"))
            item["state"] = "alerts_ready" if ready else "setup_required"
            item["detail"] = "Official alerts confirmed" if ready else "Sign in and configure alerts"
        output.append(item)
    return output
