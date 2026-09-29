from __future__ import annotations

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1), data_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL, statement TEXT NOT NULL,
    verified INTEGER NOT NULL CHECK (verified IN (0, 1)), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
    external_id TEXT, company TEXT NOT NULL, title TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'discovered',
    score INTEGER, score_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS material_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES jobs(id), version INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'submitted')),
    manifest_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(job_id, version)
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
    material_set_id INTEGER REFERENCES material_sets(id), status TEXT NOT NULL, submitted_at TEXT,
    confirmation TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS automation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER NOT NULL REFERENCES applications(id),
    state TEXT NOT NULL, plan_json TEXT NOT NULL, approval_token TEXT, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS preparations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER NOT NULL REFERENCES applications(id),
    kind TEXT NOT NULL CHECK (kind IN ('interview', 'followup')), version INTEGER NOT NULL,
    content_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(application_id, kind, version)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
    event_type TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

MIGRATION_2 = """
ALTER TABLE evidence ADD COLUMN public_id TEXT;
ALTER TABLE evidence ADD COLUMN provenance_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE evidence ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE evidence ADD COLUMN updated_at TEXT;

ALTER TABLE jobs ADD COLUMN public_id TEXT;
ALTER TABLE jobs ADD COLUMN original_content TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN company_id INTEGER REFERENCES companies(id);
ALTER TABLE jobs ADD COLUMN job_source_id INTEGER REFERENCES job_sources(id);
ALTER TABLE jobs ADD COLUMN company_url TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN application_url TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN location_type TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE jobs ADD COLUMN employment_type TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN salary_min INTEGER;
ALTER TABLE jobs ADD COLUMN salary_max INTEGER;
ALTER TABLE jobs ADD COLUMN currency TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN posting_date TEXT;
ALTER TABLE jobs ADD COLUMN expires_at TEXT;
ALTER TABLE jobs ADD COLUMN responsibilities_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE jobs ADD COLUMN required_qualifications_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE jobs ADD COLUMN preferred_qualifications_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE jobs ADD COLUMN clearance_requirement TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN work_authorization_requirement TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN travel_requirement TEXT NOT NULL DEFAULT '';

ALTER TABLE material_sets ADD COLUMN public_id TEXT;
ALTER TABLE material_sets ADD COLUMN profile_version_id INTEGER REFERENCES profile_versions(id);
ALTER TABLE material_sets ADD COLUMN template_id TEXT NOT NULL DEFAULT 'classic-ats';
ALTER TABLE material_sets ADD COLUMN template_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE material_sets ADD COLUMN tailoring_mode TEXT NOT NULL DEFAULT 'standard';
ALTER TABLE material_sets ADD COLUMN structured_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE applications ADD COLUMN public_id TEXT;
ALTER TABLE applications ADD COLUMN job_snapshot_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE applications ADD COLUMN approved_binding_json TEXT;
ALTER TABLE applications ADD COLUMN approved_at TEXT;
ALTER TABLE applications ADD COLUMN next_action TEXT NOT NULL DEFAULT '';
ALTER TABLE applications ADD COLUMN notes TEXT NOT NULL DEFAULT '';

ALTER TABLE automation_runs ADD COLUMN public_id TEXT;
ALTER TABLE automation_runs ADD COLUMN audit_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE preparations ADD COLUMN public_id TEXT;

CREATE TABLE profile_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, version INTEGER NOT NULL UNIQUE,
    data_json TEXT NOT NULL, source_resume_name TEXT, source_resume_sha256 TEXT,
    reviewed_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, normalized_name TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE job_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, adapter TEXT NOT NULL,
    external_key TEXT NOT NULL, capability TEXT NOT NULL CHECK (capability IN ('AUTOMATED','ASSISTED','MANUAL_ONLY')),
    metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, UNIQUE(adapter, external_key)
);
CREATE TABLE job_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, job_id INTEGER NOT NULL REFERENCES jobs(id),
    from_status TEXT, to_status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE job_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, job_id INTEGER NOT NULL REFERENCES jobs(id),
    profile_version_id INTEGER REFERENCES profile_versions(id), version INTEGER NOT NULL,
    factors_json TEXT NOT NULL, score INTEGER, created_at TEXT NOT NULL, UNIQUE(job_id, version)
);
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, application_id INTEGER REFERENCES applications(id),
    kind TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, document_id INTEGER NOT NULL REFERENCES documents(id),
    version INTEGER NOT NULL, job_id INTEGER REFERENCES jobs(id), profile_version_id INTEGER REFERENCES profile_versions(id),
    template_id TEXT NOT NULL, template_version INTEGER NOT NULL, tailoring_mode TEXT NOT NULL,
    path TEXT NOT NULL, sha256 TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
    UNIQUE(document_id, version)
);
CREATE TABLE answer_vault (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, answer_key TEXT NOT NULL UNIQUE,
    value_json TEXT NOT NULL, classification TEXT NOT NULL CHECK (classification IN ('AUTO','VERIFY','USER_REQUIRED')),
    verified INTEGER NOT NULL CHECK (verified IN (0,1)), provenance TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE application_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, application_id INTEGER NOT NULL REFERENCES applications(id),
    version INTEGER NOT NULL, answers_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(application_id, version)
);
CREATE TABLE application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE,
    application_id INTEGER NOT NULL REFERENCES applications(id), from_status TEXT, to_status TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, company_id INTEGER REFERENCES companies(id),
    name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE,
    application_id INTEGER NOT NULL REFERENCES applications(id), stage TEXT NOT NULL, scheduled_at TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE,
    application_id INTEGER NOT NULL REFERENCES applications(id), kind TEXT NOT NULL, due_at TEXT,
    status TEXT NOT NULL DEFAULT 'planned', content TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
    query_json TEXT NOT NULL, result_count INTEGER NOT NULL DEFAULT 0, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE submission_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, public_id TEXT NOT NULL UNIQUE,
    application_id INTEGER NOT NULL REFERENCES applications(id), automation_run_id INTEGER REFERENCES automation_runs(id),
    state TEXT NOT NULL, audit_json TEXT NOT NULL, confirmation_json TEXT, created_at TEXT NOT NULL, finished_at TEXT
);

CREATE UNIQUE INDEX idx_evidence_public_id ON evidence(public_id);
CREATE UNIQUE INDEX idx_jobs_public_id ON jobs(public_id);
CREATE UNIQUE INDEX idx_material_sets_public_id ON material_sets(public_id);
CREATE UNIQUE INDEX idx_applications_public_id ON applications(public_id);
CREATE UNIQUE INDEX idx_automation_runs_public_id ON automation_runs(public_id);
CREATE UNIQUE INDEX idx_preparations_public_id ON preparations(public_id);
"""

MIGRATIONS = [(1, MIGRATION_1), (2, MIGRATION_2)]

