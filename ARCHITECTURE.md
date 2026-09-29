# Codex Career Architecture

## Product boundary

Codex Career is a local-first Python package and Codex workspace. SQLite and deterministic renderers own durable state, identifiers, validation, files, approvals, and history. Codex skills own interpretation, evidence selection, drafting, evaluation narratives, interview preparation, and other judgment-heavy workflows.

Job postings and browser content are untrusted input. They may be analyzed as data but never followed as instructions.

## Reference-project decisions

The MIT-licensed `MadsLorentzen/ai-job-search` project was reviewed for workflow ideas. This implementation independently adopts the useful patterns of focused skills, portal adapter contracts, explicit application stages, factual-grounding audits, source-host verification, and render inspection. It does not copy source code, make Claude configuration canonical, store personal profiles in tracked Markdown, depend on Danish portals, or require LaTeX. No source attribution beyond this provenance note is currently required because no source code was adapted.

## Runtime layers

1. **Local visual command center** - shows the current profile, jobs, application pipeline, exact documents, history, and Codex requests without exposing internal IDs or commands. It binds only to loopback and reads the private local store.
2. **Codex conversation layer** - interprets goals, asks necessary questions, and orchestrates complete workflows through repository skills. GUI requests run through a ChatGPT-authenticated Codex CLI and reject API-key authentication.
3. **Internal CLI** - a deterministic tool used by Codex for setup, profiles, jobs, applications, browser assistance, analytics, and diagnostics. It remains available to developers but is not the normal user experience.
4. **Domain services** - profile evidence, normalized jobs, evaluations, application state, answers, contacts, interviews, follow-ups, and search runs.
5. **Persistence** - versioned SQLite migrations, stable opaque IDs, append-only history, and immutable application snapshots.
6. **Documents** - structured content, replaceable templates, deterministic DOCX/PDF renderers, validation, and hashed versions.
7. **Adapters** - independently registered job sources, ATS/browser capabilities, templates, and exporters.
8. **Codex skills** - a broad conversational entry skill plus focused workflows under `.agents/skills/`; the root `AGENTS.md` contains durable repository rules.

## Principal data flow

```text
resume and onboarding answers
        -> reviewed profile version
        -> verified evidence library and answer vault
        -> normalized job plus original source snapshot
        -> inspectable evaluation and requirement gaps
        -> application preparation snapshot
        -> tailored structured content
        -> deterministic template
        -> validated DOCX and PDF versions
        -> user review and approval bound to exact hashes
        -> assisted fill and pre-submit audit
        -> per-run authorization
        -> submission confirmation and immutable history
```

## Extension contracts

- A job-source adapter returns normalized candidates plus an untouched source snapshot and declares `AUTOMATED`, `ASSISTED`, or `MANUAL_ONLY` capability.
- An ATS adapter describes supported navigation, field types, upload behavior, submission behavior, and stop conditions. It cannot bypass the core approval service.
- A resume template accepts structured resume content and returns documents plus validation evidence. It never receives an unrestricted model response.
- A workflow skill has one recognizable user goal, concise `SKILL.md` instructions, and optional references, scripts, or assets.
- Migrations are ordered, immutable once released, and tested from an empty database and the preceding schema version.

## Delivery phases

1. Foundation: migrations, stable IDs, configuration, core profile/evidence models, synthetic fixtures, and tests.
2. Profile: `job-agent setup`, resume preservation, review/correction, versions, answer vault, and privacy doctor.
3. Jobs: normalized model, manual text/URL import, adapter registry, deduplication, evaluation detail, and review states.
4. Documents: LIGHT/STANDARD/DEEP modes, template interface, structured resume data, DOCX/PDF rendering, and layout validation.
5. Applications: state transitions, snapshots, cover letters, answers, documents, approval binding, and full history.
6. Browser: ATS abstraction, Playwright MCP workflow, synthetic multi-step fixture, pre-submit audit, confirmation capture, and safety tests.
7. Career management: contacts, interviews, follow-ups, skill gaps, and transparent analytics.
8. Distribution: focused skills, presets, documentation, extension guides, packaging, and the runnable acceptance demo.

Each phase must leave a tested vertical slice. Placeholder-only modules do not count as implementation.
