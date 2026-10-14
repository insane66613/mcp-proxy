---
name: mcp-proxy-verification
description: Apply a careful change-and-validation workflow to mcp-proxy, including Context7 version matching, Pylint, integration tests, and MCP lifecycle regressions.
---

# Verified mcp-proxy edits

Use this skill for fixes, enhancements, upstream PR preparation, and release work inside this repository.

1. **Scope:** inspect Git status, affected files, `pyproject.toml`, tests, and running-service risks. Do not overwrite someone else's dirty working tree.
2. **Docs:** check the installed MCP Python SDK constraint first (`mcp>=1.27.1,<2` at this repository's initial configuration). Query Context7 only when changing uncertain third-party API calls. Reject v2-only examples for v1 code; use official v1 sources or installed package definitions.
3. **Patch:** change only required functions. Maintain backward compatibility unless the request authorizes breaking changes. Do not add long-lived watchers, duplicate hooks, or automatic production restarts.
4. **Regression:** add tests reproducing the original defect and tests for concurrent requests, early cancellation, shutdown cleanup, and recovery where relevant. Avoid asserting that an HTTP stream cancellation proves a tool failure.
5. **Check:** run `pwsh -File scripts/verify-change.ps1 -Mode Quick`; for release/merge run `pwsh -File scripts/verify-change.ps1 -Mode Full`. Review any logs the runner identifies. Pylint must run after Python modifications.
6. **Output control:** prefer short targeted reads. For outputs >200 lines or >32 KiB, use existing Context Mode tools where the host has them; otherwise preserve full logs and show bounded errors plus a path. Record any measured byte reduction as an approximation, never measured token savings.
7. **Review:** inspect diff and unchanged files; report pass/fail separately for Ruff, Pylint, mypy, pytest, and Git checks. Explain pre-existing issues without claiming validation succeeded.
8. **Deliver:** do not commit, push, merge, publish, or restart a service without authorization. No hidden changes to Cursor global MCP registrations or production credentials.
