# Visual command center

The local GUI makes Codex Career usable without internal commands or database IDs. It reads the same private SQLite database and versioned artifact directory as the conversational workflow.

From the project folder, ask Codex to start the career command center. For developer use, the equivalent command is:

```text
job-agent gui
```

The browser opens to `http://127.0.0.1:8765`. The server binds only to the loopback interface, uses a per-launch session token for private requests, sends a restrictive content-security policy, and never exposes `user-data/` as a static directory.

## Connect Codex without API billing

Select **Connect** in the sidebar and finish **Sign in with ChatGPT** in the window that opens. The GUI checks `codex login status` and enables agent runs only when the CLI reports ChatGPT authentication. API-key authentication is rejected, and API-key environment variables are removed from child runs.

Work performed from the GUI therefore uses the signed-in user's Codex allowance and normal plan limits. It does not create an API key or API billing account.

## Safety model

The GUI can ask Codex to discover jobs, evaluate matches, propose profile changes, prepare versioned materials, and continue browser-assisted applications. It does not add a bypass around the existing workflow:

- Profile and base-resume facts remain review-gated and versioned.
- AI-generated content cannot edit DOCX/PDF formatting directly.
- Exact generated documents remain hash-bound to an application.
- CAPTCHA, MFA, legal attestations, unknown answers, and unsupported fields stop the browser workflow.
- Final submission still requires an explicit approval for that exact application after its final audit.

## Troubleshooting

- **Codex CLI not installed:** install the official Codex CLI, restart the GUI, and select Connect.
- **Not using ChatGPT sign-in:** run the Connect flow again and select ChatGPT rather than an API key.
- **Port already in use:** use `job-agent gui --port 8877`.
- **Browser did not open:** visit the local address printed in the terminal. The server can also be started with `--no-open`.
