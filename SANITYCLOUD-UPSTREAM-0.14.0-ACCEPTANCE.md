# SanityCloud mcp-proxy upstream 0.14.0 integration receipt

**Date:** 2026-11-03 (America/Chicago)
**Status:** SOURCE INTEGRATED / VALIDATED SUBSET / PRODUCTION CUTOVER BLOCKED
**Authority:** User authorized the integration and conditional cutover; no production changes were made.
**Repository:** `X:\Code\mcp-proxy`
**Isolated worktree:** `X:\Worktrees\mcp-proxy\integrate-upstream-v0.14.0-20261103`
**Branch:** `integrate/upstream-v0.14.0-20261103`

## Verified source and isolation

- Baseline fork `main`: `5ae34551eb1638893516779c3e06322271e1450f`.
- Upstream `v0.14.0`: `cf0249103ec4996cbe725c0468f3cd73d263d96e`.
- Source: `sparfenyuk/mcp-proxy`; destination fork: `insane66613/mcp-proxy`.
- Integration took place in a separate worktree with a separate `.venv` using Python 3.14.7.
- Existing `.venv` and `.venv-cursor-commander` on the production root remain version 0.13.0.
- Original root `main` and untracked `.agents/` were not changed.
- No live service was stopped, restarted, replaced, or deployed.

## Retained fork contracts

- Privacy-safe coarse HTTP metrics instead of request URL/session ID logging.
- Uvicorn raw access logging disabled to prevent query and session token disclosure.
- Optional standalone Streamable HTTP GET policy and configurable session idle expiry.
- Session pressure bounds, cancellation, tool-output shape contracts, and bounded termination.
- Upstream 0.14.0 reconnecting sessions, initialization timeout, and transport security.
- Windows-specific test harness for duplicated subprocess pipe handles.
## Validation

- Merge conflicts: 9 conflicted files, resolved; no unmerged paths.
- Python source and tests: compileall successful.
- Mypy: `Success: no issues found in 13 source files`.
- Pylint error-only on affected runtime modules: exit 0.
- Ruff targeted sources/tests: passed with existing `CPY001` and upstream `SIM117` excluded.
- Acceptance subset: **414 passed, 5 skipped, 5 deselected**, exit 0, 59.58 seconds.
- Security tests covering secret redaction, HTTP-body limits and CLI settings passed.
- The Windows-pipe harness tests passed after replacing POSIX-only `os.dup`.

## Material unresolved gates

**Not production accepted.** The selected acceptance run excluded these functions:

1. `test_omitted_initialization_timeout_allows_delayed_initialize`
2. `test_initialization_timeout_does_not_limit_later_tool_call`
3. `test_cli_sigint_delete_shutdown_is_bounded_and_preserves_interrupt` (3 cases)

The first two expect a child shutdown receipt after force-terminating the proxy. On Windows,
`process.terminate()` is not a graceful shutdown and the child marker was absent.
The third uses POSIX-style `SIGINT` delivery to a redirected Windows subprocess;
three cases timed out rather than completing the intended bounded teardown.

These represent unverified Windows process supervision and shutdown behavior.
They must not be silently converted into passes or treated as sufficient for a live cutover.

## Release decision

- Integrate and preserve source changes locally: **authorized**.
- Production cutover: **HOLD / WATCH**.
- Deploy/restart/push: **not performed**.
- Before cutover: implement/test a native Windows controlled shutdown and child reaping
  strategy; verify SIGINT/CTRL_BREAK or equivalent console behavior through a realistic
  supervisor path; run a fully passing Windows acceptance gate, then take a service-specific
  rollback snapshot and perform a bounded canary before wider deployment.

The launcher at `X:\Code\sanity-cloud-ai-portal\scripts\start-cursor-commander-mcp-proxy.ps1`
uses `X:\Code\mcp-proxy\.venv-cursor-commander\Scripts\mcp-proxy.exe`, which must not
be redirected to the candidate until the remaining release gates pass.
