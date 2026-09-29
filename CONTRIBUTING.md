# Contributing to Codex Career

Use fictional data in tests and examples. Never commit a real resume, profile, application response, browser screenshot, database, or generated artifact.

Create a virtual environment, install the project in editable mode, and run:

```text
python -m unittest discover -s tests -v
```

Keep changes local-first and dependency-light. Safety-sensitive changes must preserve the separate prepare, fill, authorize, submit, and record stages and include a regression test. Do not add direct application POST integrations or automatic CAPTCHA, MFA, legal-attestation, demographic, or high-risk-answer handling.

Pull requests should explain the user-visible behavior, safety impact, and test evidence.

Extension contracts are documented in `docs/JOB_SOURCE_ADAPTERS.md`, `docs/ATS_ADAPTERS.md`, and `docs/RESUME_TEMPLATES.md`. Keep provider parsing inside its adapter, register its declared capability, and use synthetic fixtures instead of live employer systems.
