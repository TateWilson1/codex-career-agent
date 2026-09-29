# Installation

Codex is the normal interface. Once this repository is open in Codex, the user can say:

> Install this project locally, verify it, and start onboarding me. My resume is attached.

Codex should create the environment, install the package, run the doctor and tests, then continue conversationally. It should not hand these commands back to the user unless local command execution is unavailable or the user asks for technical instructions.

For developers, the underlying installation is:

Install Python 3.11 or newer, clone the repository, create a virtual environment, and install the package in editable mode:

```text
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On macOS/Linux, activate with `source .venv/bin/activate`. Node.js is optional and needed only for Playwright MCP. Codex runs `job-agent doctor` after onboarding and the local test suite to verify the installation.
