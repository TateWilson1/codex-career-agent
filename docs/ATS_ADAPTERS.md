# ATS/application adapters

ATS adapters implement the browser contract: open, inspect, fill a validated plan, upload an exact approved file, stop before submit, submit only in `authorized_to_submit`, and return actual confirmation evidence. The core owns question classification, file hashes, approval binding, and status changes.

Adapters must stop on unexpected required fields, unsupported questions, CAPTCHA, MFA, security challenges, legal attestations, or changed documents. Never bypass controls. Start development against `tests/fixtures/synthetic-ats.html`; a real employer form is not an automated test target.
