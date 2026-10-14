# Development workflow for mcp-proxy

This repository is used for live MCP proxy services. Protect running processes and unrelated work.

## Before editing
- Inspect `git status --short` and relevant source/tests; never discard or overwrite existing changes.
- Identify the smallest change and tests that can prove it. Do not restart production services for routine validation.
- Read `pyproject.toml` and `uv.lock` to determine installed dependency constraints.
- For unfamiliar or changed external APIs, query Context7 using the library name and the **installed compatible major/minor version**. If Context7 has only mismatched examples, consult the checked-out dependency or official versioned source. Never silently copy a v2 API into the MCP Python SDK v1.x project.
- Do not send proprietary code, paths containing secrets, credentials, or private configuration values to documentation searches.

## Editing and review
- Prefer surgical edits. Preserve upstream attribution and licensing.
- Add or update a regression test for changed behavior, especially HTTP lifecycle, stream cancellation, connection reuse, and cleanup.
- Treat cancellations and normal HTTP disconnects separately from actual tool failures.
- Avoid introducing proxy, transport, or MCP hooks without checking existing installed plugins and duplicate-event risks.
- For large logs (>200 lines or >32 KiB), use Context Mode where available, or bounded local summaries retaining full raw logs, line numbers, and error excerpts. Do not summarize away failures.
- Use the project skill at `.cursor/skills/mcp-proxy-verification/SKILL.md`.

## Validation
- Run `pwsh -File scripts/verify-change.ps1 -Mode Quick` after editing.
- Run `pwsh -File scripts/verify-change.ps1 -Mode Full` before proposing merge or deployment.
- Validation includes Git whitespace checks, Ruff, and Pylint; full mode also runs mypy and pytest. Fail closed and disclose pre-existing failures.
- Validate in `.venv-integration` or another explicit test environment; do not sync or mutate the live `.venv` as a side effect.
- Inspect `git diff` and `git status` before any commit; never commit, push, merge, or restart without the applicable authorization.
