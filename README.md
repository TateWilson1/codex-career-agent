# Codex Career

Codex Career is a local-first, open-source career agent operated through a visual command center and a conversation with Codex. Give Codex your resume, preferences, a job link, or a goal; Codex runs the private local engine, asks only for information or approvals it genuinely needs, and returns understandable results and reviewable documents.

The bundled CLI is an internal deterministic tool for Codex, not the normal user interface. The local GUI shows the profile, job desk, application pipeline, exact document vault, interviews, follow-ups, and a Codex request panel in one place. Candidate data stays in the ignored `user-data/` directory, there is no service account to create, and no API key is required. Codex handles interpretation and drafting; normal code controls storage, document formatting, validation, versioning, and submission authorization.

## Open the visual command center

Open this project in Codex and say:

> Start my career command center.

Codex will install the project if necessary and launch the local interface. Developers can start the same interface with `job-agent gui`. Select **Connect** once to sign the Codex CLI in with ChatGPT. The GUI intentionally refuses API-key authentication, so agent work uses the Codex allowance from the signed-in ChatGPT plan rather than separate API billing.

See [the GUI guide](docs/GUI.md) for security, connection, and troubleshooting details.

## Use it through Codex

Open this project folder in Codex and speak naturally. You do not need to run commands, edit JSON, find database IDs, or copy approval tokens.

Start with something like:

> Set up my career agent. My resume is attached. Ask me whatever you need, then show me my profile before saving it.

After onboarding, examples include:

- “Find entry-level accounting jobs near Philadelphia or remote and explain the best matches.”
- “Import this job posting and tell me whether it is worth applying.”
- “Prepare an application for the Contoso analyst role using my verified experience.”
- “Fill this application, but stop before submitting.”
- “Show me exactly what will be submitted and any unanswered questions.”
- “Submit this application.” Codex will accept this only after showing the final audit for that specific application.
- “What applications need follow-up?”
- “Prepare me for tomorrow’s interview using the resume I actually submitted.”

Codex performs the required local commands and file operations in the background. It pauses for profile review, unsupported questions, document approval, CAPTCHA/MFA, legal or consent decisions, and the final per-application submission approval.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer only if you want Playwright MCP browser assistance
- Codex CLI or Codex desktop for the Codex-first workflow

## One-time installation

If the repository is already open in Codex, say:

> Install this project locally, run its checks, and then start onboarding me.

Codex can perform the following conventional installation internally. Developers may also run it themselves:

```text
git clone YOUR_FORK_URL codex-career
cd codex-career
python -m venv .venv
```

Activate the environment:

```text
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS or Linux
source .venv/bin/activate
```

Then install:

```text
python -m pip install -e .
```

Codex initializes the private data store during conversational onboarding. All personal data and generated artifacts are written below `user-data/`, which is ignored by Git. Advanced users may set `JOB_AGENT_DATA` to use another private directory.

## What Codex does during onboarding

Attach or identify a DOCX, PDF, TXT, or Markdown resume. Codex extracts only supported facts, asks conversational questions about missing career preferences, and shows a readable profile for correction. Nothing becomes verified evidence until you approve that profile. The original resume is then preserved separately from generated materials.

Optional presets provide editable defaults, never candidate facts. Included examples cover general entry-level, software engineering, accounting, and cybersecurity.

## Internal engine reference

The remaining command examples document the deterministic backend for contributors, troubleshooting, and automation tests. Normal users should ask Codex for the corresponding outcome instead.

## Jobs

The visual command center includes a **Sources & scoring** desk plus a **Connections** screen with direct Greenhouse, Lever, SmartRecruiters, Ashby, and USAJOBS coverage; user-controlled account alerts; freshness labels; connection health; and an explanation for every score. See [Job sources, freshness, and scoring](docs/JOB_SOURCES_AND_SCORING.md) for the source contract and the 100-point model.

Import a CSV or JSON list containing `company`, `title`, and optional `location`, `url`, `description`, and `external_id` fields:

```text
job-agent jobs import jobs.json --source saved-search
job-agent jobs add --company "Example Company" --title "Analyst" --url URL --description-file posting.txt
```

Discover jobs from a specific public ATS board:

```text
job-agent jobs discover greenhouse BOARD_TOKEN --company "Example Company"
job-agent jobs discover lever SITE_NAME --company "Example Company"
job-agent jobs scan
job-agent jobs evaluate
job-agent jobs list
job-agent jobs status 1 interested
```

URLs are normalized before hashing, so tracking query strings do not create duplicates. `scan` reads the ignored private `job_sources` configuration, rejects clearly unrelated job titles, and performs import, deduplication, evaluation, search-run recording, and new-match reporting in one command. Discovery uses the public read-only APIs documented by [Greenhouse](https://docs.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api), [SmartRecruiters](https://developers.smartrecruiters.com/docs/posting-api), [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api), and [USAJOBS](https://developer.usajobs.gov/api-reference/get-api-search); it never invokes their application endpoints. A fictional configuration shape is provided at `config/job-sources.example.json`; Codex manages the real private configuration conversationally.

## Tailor and version materials

Generate a Codex request packet for a selected job:

```text
job-agent tailor packet 1 --out user-data/job-1-tailoring.json
```

Ask Codex to return the JSON response described in that packet. Review it, then build a new immutable version:

```text
job-agent tailor build 1 user-data/job-1-proposal.json --pdf --confirm-truthful
job-agent materials approve MATERIAL_ID
```

The validator rejects unknown or unverified evidence IDs and numeric claims not present in the source evidence. DOCX and PDF files are rendered by normal code from the approved structure, so generated prose cannot alter margins, styles, sections, or file internals. Every version includes source snapshots and SHA-256 hashes.

## Track and prepare applications

```text
job-agent applications start JOB_ID MATERIAL_ID
job-agent applications show APPLICATION_ID
job-agent applications prep APPLICATION_ID interview --out user-data/interview-packet.json
job-agent applications prep APPLICATION_ID followup --out user-data/followup-packet.json
job-agent applications save-prep APPLICATION_ID interview user-data/interview-prep.json
job-agent applications save-prep APPLICATION_ID followup user-data/followup-message.json
job-agent interviews add APPLICATION_ID --stage screen --scheduled-at 2027-01-10T15:00:00Z
job-agent followups add APPLICATION_ID --kind thank-you --due-at 2027-01-11T15:00:00Z
```

Interview and follow-up packets are built from the saved job, exact material manifest, submission receipt, and event history. Saved preparation outputs are versioned in the database and returned by `job-agent applications show`.

## Browser-assisted filling

Install the free/open Playwright MCP integration and follow the approval sequence in [docs/PLAYWRIGHT.md](docs/PLAYWRIGHT.md). The short version is:

```text
job-agent answers list
job-agent answers set start_date '"2027-06-01"' --classification VERIFY --confirm-verified
job-agent answers classify user-data/fill-plan.json
job-agent automation prepare APPLICATION_ID user-data/fill-plan.json user-data/verified-answers.json --confirm-answers
job-agent automation authorize RUN_ID --token RUN_TOKEN --confirm "SUBMIT THIS APPLICATION"
job-agent automation record-submission RUN_ID --receipt user-data/submission-receipt.json
```

Preparation never grants submission permission. Codex must fill only the validated plan and stop before submit. Resume and cover-letter upload paths come from the application's exact approved material manifest; an answers file cannot replace them. The authorization command is run only after the user reviews that specific application. CAPTCHA, MFA, high-risk questions, unknown answers, and unapproved documents stop the workflow. See [docs/SAFETY.md](docs/SAFETY.md).

## Test with fictional data

```text
python -m unittest discover -s tests -v
```

The end-to-end test covers profile evidence, duplicate imports, scoring, tailoring safety, DOCX/PDF creation and extraction, version hashes, approval, exact-file checking, blocked questions, per-run submit authorization, submission history, interview preparation, and public ATS adapters without network access.

The checked-in examples are fictional and use the reserved `.test` domain. No real candidate data is included.

Run the full fictional acceptance workflow in a fresh ignored directory:

```text
python scripts/acceptance_demo.py --output user-data/acceptance-demo --approve-submit
```

`--approve-submit` is explicit approval for that synthetic fixture application only. Without it, the demo fills the form and stops before submission.

## Documentation

See [visual command center](docs/GUI.md), [installation](docs/INSTALLATION.md), [configuration](docs/CONFIGURATION.md), [privacy](docs/PRIVACY.md), [browser setup](docs/PLAYWRIGHT.md), [safety](docs/SAFETY.md), [resume templates](docs/RESUME_TEMPLATES.md), [job-source adapters](docs/JOB_SOURCE_ADAPTERS.md), [ATS adapters](docs/ATS_ADAPTERS.md), and [troubleshooting](docs/TROUBLESHOOTING.md). Developers should also read [ARCHITECTURE.md](ARCHITECTURE.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Project layout

- `src/codex_career/` - application code
- `.agents/skills/` - focused Codex workflows
- `tests/` - fictional end-to-end and safety checks
- `examples/fictional/` - public test data
- `config/` - optional integration examples
- `docs/` - safety and browser workflow
- `user-data/` - private runtime data, ignored by Git

## License and contributions

Codex Career is licensed under MIT. Keep pull requests free of personal data, preserve the submission state machine, and add a focused regression test for any safety-sensitive change.
