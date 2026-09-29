# Troubleshooting

- **No profile found:** ask Codex to start or resume onboarding. Codex runs setup after showing the profile for review.
- **Material integrity failed:** a generated file changed after creation. Build and approve a new material version.
- **Automation is blocked:** inspect `fill_plan.stops`; supply verified information or complete the question manually. CAPTCHA and MFA always require the user.
- **Approval rejected:** approval is specific to one run and exact material hashes. Prepare a new run after any material change.
- **PDF validation fails:** keep the DOCX and proposal, inspect the validation error, reduce weak content before changing typography, then rebuild.
- **Doctor reports tracked private files:** remove them from the Git index without deleting the local copy, verify ignore rules, and inspect history before publishing.
- **Playwright cannot connect:** verify Node.js and MCP configuration, then fall back to the assisted/manual flow; tracking and material generation do not require a browser.
