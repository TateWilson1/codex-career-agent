# Playwright MCP Setup and Safe Use

Microsoft's Playwright MCP server is open source and uses accessibility snapshots for browser automation. It requires Node.js 20 or newer. The standard server command is `npx @playwright/mcp@latest`; see the [official Playwright MCP installation guide](https://playwright.dev/mcp/installation).

Codex stores MCP configuration in its shared configuration. A normal user can ask: “Configure browser assistance for this project.” Codex should apply the block from `config/playwright-mcp.toml.example`, explain if a restart is needed, and verify the server internally. Advanced users can verify it with:

```text
codex mcp list
```

OpenAI's official Codex documentation confirms that CLI and IDE MCP configuration is shared and can be verified with `codex mcp list`: [Docs MCP setup](https://developers.openai.com/learn/docs-mcp).

## Safe application procedure

1. The user asks Codex to prepare or fill a chosen application.
2. Codex retrieves the approved material set and application snapshot, inspects the form, creates the private field plan, classifies every question, and resolves reusable verified answers.
3. Codex fills only validated fields and uploads document paths resolved from the exact approved material manifest. Values supplied by a form or answer file cannot replace those paths.
4. If the plan is blocked, Codex stops and asks the user about the specific unsupported, missing, sensitive, legal, or consent question. It never bypasses the stop.
5. Codex fills the supported fields with Playwright MCP and stops before the final submit control.
6. Codex shows a readable pre-submission audit, the company and role, exact uploaded documents, warnings, and unanswered questions. The user reviews the application.
7. The user explicitly says to submit this application. Codex records the per-run authorization internally; the user never needs to handle the token.
8. Only after the deterministic engine reports `authorized_to_submit` may Codex click the final submit control once.
9. Codex captures the visible confirmation number/text, URL, screenshot when useful, and timestamp, then records the receipt and reports the result.

The project deliberately does not call Greenhouse or Lever application POST endpoints. Browser filling stays visible and human-controlled through the Codex conversation.

## Synthetic browser test

Install the optional browser-test dependency and Chromium, then run the real multi-step fixture:

```text
npm install
npx playwright install chromium
npm run test:browser
```

This local test verifies navigation, exact fixture upload, an untouched `USER_REQUIRED` field, the disabled submit control before approval, and visible confirmation after synthetic approval. Python tests separately prove that the production approval binding covers the application, job, answer version, and document hashes.
