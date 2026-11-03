# SanityCloud mcp-proxy upstream 0.14.0 integration receipt

**Date:** 2026-11-03 (America/Chicago)
**Status:** CURSOR COMMANDER 0.14.0 LIVE / LOCAL AND CHATGPT CONNECTOR VERIFIED; OTHER PROXIES UNCHANGED
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

---

## 2026-11-03 Windows acceptance and packaging update

This section supersedes the earlier unverified Windows shutdown gates above.
Previous 414-pass subset and 5-deselection result remains historical, not current.

- **Full suite:** 419 passed, 5 skipped, 0 failed, 0 deselected; exit 0 (81.62 seconds).
- **Static:** mypy 14 source files passed; pylint error-only passed; Ruff targeted passed with pre-existing CPY001 and upstream SIM117 rule exclusions; `git diff --check` passed.
- **Windows subprocess:** job-object kill-on-close protection added before stdio child spawn. Failed job setup is fatal; child handle is not inherited.
- **Real force-stop proof:** candidate canary pid 333888 and packaged-wheel canary pid 47340 each spawned two descendants. Forced stop left 0 descendants and closed isolated port 18766.
- **MCP canary:** initialize + list tools + call echo_canary succeeded with the worktree build and separately with the packaged release wheel.
- **Wheel:** `mcp_proxy-0.14.0-py3-none-any.whl`, SHA256 `236EB424CA0E4A6A44CA2DB09AE37F05C493303C5F03E0F7019F3A5D1BC4FD4E`.
- **Runtime:** `X:\MCP\runtimes\mcp-proxy-0.14.0-20261103`, Python 3.14.7, dependency versions exported from the locked project environment, wheel installed non-editably.

## Operational parity blocker: Cursor Commander

- The six existing proxy services at 3020, 3022, 3030, 3072, 8140, and 8766 all returned HTTP 204 for localhost `/healthz`.
- Existing Cursor Commander `http://127.0.0.1:8766/mcp` responds to MCP initialize as `cursor-commander` version `0.1.0`.
- A real `tools/list` call fails against **the existing 0.13.0 runtime** with MCP error code 0 and an empty message.
- Reproduced with both Python 3.12.11 (existing `.venv-cursor-commander`) and Python 3.14.7 (candidate release runtime); both use MCP SDK 1.30.0.
- Tool-list baseline receipt could not be created. This is a pre-existing baseline issue, not evidence that 0.14.0 failed.
- Production Cursor Commander cutover is **HOLD** until the backend tool-list issue is reconciled or an explicitly approved alternative parity gate is documented.
- No changes were made to the running proxy, its two version-0.13.0 environments, PID record, portal launchers, or unrelated dirty portal files.
- Existing version-0.13.0 release remains the immediate rollback target.
- The installed versioned 0.14.0 runtime is staged, not actively used by any production proxy.

## Operational next action

Investigate Cursor Commander `tools/list` within its existing backend/session.
After a sound baseline is available, capture exact tool names and semantics before and after a single-service cutover.
Preserve the current portal repository's unrelated local changes and the PID-scoped stop/start launcher contracts.

---

## 2026-11-03 final operational closure (supersedes earlier HOLD)

- **Root cause established:** Cursor Commander backend's direct MCP stdio exposed six tools and passed `tools/list`. Existing mcp-proxy 0.13.0 returned MCP error code 0 with empty text for HTTP `tools/list`; isolated mcp-proxy 0.14.0 succeeded against the same backend.
- **Production configuration parity:** The managed ChatGPT bridge is enabled. With scoped bridge configuration, both isolated candidate and live 0.14.0 proxy advertise eight tools. Exact name-list fingerprint SHA256: `1e173276d77212b9576008d7c0ee6c16160556042cab6bcbb50f78977d5f14bf`.
- **Read-only MCP tool call:** `cursor_dashboard` succeeded on both candidate and live proxy; 13 recorded jobs and no jobs marked active in the dashboard snapshot.
- **Release package:** `mcp_proxy-0.14.0-py3-none-any.whl`, SHA256 `236EB424CA0E4A6A44CA2DB09AE37F05C493303C5F03E0F7019F3A5D1BC4FD4E`.
- **Release runtime:** `X:\MCP\runtimes\mcp-proxy-0.14.0-20261103` (version 0.14.0, non-editable wheel).
- **Local acceptance:** full 419-passed/5-skipped suite, mypy and pylint success, target Ruff and PowerShell 7 parse checks. Portal launcher test suite 65 passed, plus exact-host security test 7 passed.

- **First local cutover:** Portal feature commit `f65f2ae281883546004d77f35bd3d19f31588137` changed only Cursor Commander's start/stop default executable to the immutable versioned runtime. Former PID 256416 was stopped with identity-scoped service script; PID 51276 ran 0.14.0 and passed HTTP 204, eight-tool manifest parity, and dashboard call.
- **Public ingress issue:** ChatGPT Cursor Command plugin initially received HTTP 421 Misdirected Request for `https://cursor-commander.ptelectronics.net/mcp`. The release's transport security rejects unknown Host authorities with 421. This was not an authentication or backend-tool problem.
- **Narrow host fix:** Portal commit `770e3a7cc6fe8da34a0280a2dc82564825558e8a` added only `--allowed-host cursor-commander.ptelectronics.net` to the Cursor proxy launcher. DNS rebinding protection remains enabled, no wildcard trust was added, and `--pass-environment` remains prohibited.
- **Final live PID:** 629072 at `X:\MCP\runtimes\mcp-proxy-0.14.0-20261103\Scripts\mcp-proxy.exe` with exact public hostname allowlisted, port 8766, local health HTTP 204.
- **ChatGPT connector verified:** `cursor_status` responded `operational` / `trusted`, total sessions 97, recent jobs 5. `cursor_dashboard` responded `operational`, 13 jobs, zero marked active. This confirms end-to-end authenticated connector functionality.
- **Other endpoints:** 3020, 3022, 3030, 3072, and 8140 each returned HTTP 204 after the Cursor-only cutover. Port 18766 canary was closed. Other production proxy runtimes were not replaced.
- **Rollback:** The prior Cursor v0.13.0 executable and environment remain at `X:\Code\mcp-proxy\.venv-cursor-commander`. Both launchers accept the scoped `CURSOR_COMMANDER_PROXY_EXE` override. Old release and original repository remain intact.
- **Governance:** Portal `main` includes only the two approved local feature commits. Its unrelated pre-existing modifications remain untouched. No remote push, other-service restart, credential change, or Cloudflare control-plane mutation was made.

**Final service decision:** Cursor Commander release 0.14.0 ACCEPTED LIVE. Earlier local/remote blockers are resolved. No other production proxy is represented as upgraded.
