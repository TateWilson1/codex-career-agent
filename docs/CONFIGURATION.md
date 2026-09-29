# Configuration

Conversational setup through Codex writes `user-data/config.json`; a normal user never needs to edit it. Ask Codex to change preferences or resume settings. Advanced users may edit the file: `default_tailoring_mode` accepts `LIGHT`, `STANDARD`, or `DEEP`, and `target_resume_pages` is a positive integer. Set `JOB_AGENT_DATA` to relocate all private state. Presets may supply defaults, but answers given during setup always win.

Browser configuration is separate because browser state may contain credentials. Ask Codex to configure Playwright MCP from `config/playwright-mcp.toml.example`, or follow [PLAYWRIGHT.md](PLAYWRIGHT.md) as an advanced setup reference. Never commit authenticated browser profiles.
