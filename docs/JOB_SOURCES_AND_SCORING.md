# Job sources, freshness, and scoring

Codex Career uses the widest safe coverage it can support without scraping private pages or bypassing a board's controls.

## Source modes

- **Automated:** Greenhouse, Lever, SmartRecruiters, and Ashby publish official job-posting APIs. An employer board identifier is enough to import and deduplicate listings.
- **Free key required:** USAJOBS exposes an official search API. It requires a free API key and the email associated with the request.
- **Alerts or assisted:** LinkedIn, Indeed, Handshake, FBIJobs, ClearanceJobs, CyberSN, Team Kentucky, and employer career pages are opened as first-party searches. Their own alerts should be enabled where available. Codex may review and import the results, but the project does not scrape authenticated pages or bypass CAPTCHA/MFA.

The Sources & scoring screen ranks these sources against the current private profile. Search URLs are generated from that profile at runtime; candidate details are not stored in application code.

The **Connections** screen distinguishes feeds the watcher truly polls from account boards that still need user setup. Users sign in on each board's official site and confirm that saved-search alerts are enabled. The app never asks for or stores those board passwords. USAJOBS is the exception: its free read-only API key is saved only in ignored private configuration and is never returned by the GUI API.

## Explainable 100-point score

| Factor | Maximum | What earns points |
|---|---:|---|
| Role alignment | 30 | The title directly matches the target role family. |
| Verified skills | 25 | Posting language matches skills in the approved profile. |
| Entry-level fit | 15 | Internship, new-graduate, entry-level, or 0–2 year expectations. |
| Location / work mode | 10 | Preferred geography, remote, or a permitted relocation case. |
| Freshness | 10 | 10 points inside 24 hours, 7 inside 72 hours, 4 inside 7 days, 1 afterward, and 2 when the source omits a date. |
| Employment type | 5 | Preferred permanent or internship employment. |
| Career direction | 5 | Work advances the user's stated industries and longer-term goals. |

An incompatible graduation-year window, active clearance absent from the verified profile, senior-level title, 3+ or 5+ years of required experience, contract-only work, and extensive travel subtract points. Unknown information remains unknown and is never filled in optimistically.

Score bands are: 80–100 excellent, 65–79 strong, 50–64 stretch, and below 50 low. A score is a prioritization aid, not a claim that a candidate is qualified or an authorization to apply.

## Continuous watch

The recommended watch asks Codex to search the configured source map every hour, import and deduplicate legitimate openings, evaluate them, and notify only when a new strong or time-sensitive match appears. This uses the user's Codex/ChatGPT allowance rather than an API key. The watch never submits an application.

For lower-cost deterministic polling, configure employer board identifiers and run `job-agent jobs scan`. It completes fetch, import, deduplication, evaluation, search-run recording, and fresh-match reporting in one command. One broken source is reported without discarding successful results from other sources. USAJOBS can be added after the user supplies its free API credentials.
