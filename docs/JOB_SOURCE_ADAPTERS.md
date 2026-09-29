# Job-source adapters

An adapter returns normalized dictionaries accepted by `import_jobs`: `company` and `title` are required; source/external ID, location, URLs, dates, description, qualifications, work mode, compensation, clearance, authorization, and travel fields should be retained when available. Preserve original provider content.

Register the adapter in `sources.ADAPTERS` with its callable and capability: `AUTOMATED`, `ASSISTED`, or `MANUAL_ONLY`. Use supported APIs or feeds; do not assume scraping permission. Provider-specific parsing stays in the adapter. Core deduplication, persistence, and evaluation remain provider-neutral. Add fixture-based tests without live network dependencies.

Bundled automated adapters cover Greenhouse, Lever, SmartRecruiters, Ashby, and USAJOBS. USAJOBS credentials belong only in ignored private configuration; dashboard state and logs must never return its API key.
