# Security Policy

## Reporting

Do not open a public issue containing candidate data, resumes, application answers, authentication details, or submission artifacts. Report a vulnerability privately to the repository maintainer through the security contact configured on the public repository.

## Supported version

Security fixes target the latest release on the default branch.

## Data model

Codex Career stores personal data locally in `user-data/` or the directory selected by `JOB_AGENT_DATA`. That path is ignored by Git, but it is not encrypted by this application. Users should rely on operating-system disk encryption and access controls. Do not place the data directory in a synced or shared location unless you accept that service's privacy model. Run `job-agent doctor` before publishing changes; it is a safeguard, not a guarantee.

Submission authorization tokens are local workflow guards, not remote authentication credentials. They prevent accidental state transitions; they do not defend against an attacker who already controls the user's machine and database.
