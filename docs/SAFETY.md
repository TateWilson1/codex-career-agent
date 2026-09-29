# Application Automation Safety Model

Codex Career separates preparation, filling, authorization, submission, and recording into distinct states. A browser agent cannot turn a prepared plan into a recorded submission without a per-run approval transition.

## State sequence

`preparing -> ready_for_fill -> authorized_to_submit -> submitted`

A run becomes `blocked` instead of `ready_for_fill` when it encounters CAPTCHA, MFA, biometric checks, legal attestations, background or credit consent, a `USER_REQUIRED` question, a `VERIFY` answer without field-level approval, an unverified answer, a sensitive answer without explicit approval, or a file that does not match the approved material manifest. Reusable values come from the reviewed answer vault; extra per-application answers require `--confirm-answers`.

Internally, authorization requires both the unpredictable token created for that run and the exact phrase `SUBMIT THIS APPLICATION`. Codex manages the token; the user only reviews the final audit and explicitly tells Codex to submit that specific application. Authorization consumes the token, applies only to that run, and does not submit anything by itself.

## Artifact integrity

Each material version stores SHA-256 hashes for the resume, profile snapshot, job snapshot, proposal, cover letter, and PDF when generated. Approval binds those hashes plus the exact application-answer version and hash. Authorization and submission re-check the binding. If any bound input changes, the workflow stops and the user must prepare and approve a new run.

## Browser agent contract

The Playwright agent may navigate, inspect, fill fields from the validated plan, and upload the approved resume. It must not guess, bypass access controls, solve CAPTCHA, fetch MFA codes, accept legal terms, or click the final submit control before the run is authorized. After submission it records only observable confirmation data.
