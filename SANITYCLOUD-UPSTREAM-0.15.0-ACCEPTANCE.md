# SanityCloud mcp-proxy v0.15.0 integration acceptance

**Date:** 2026-11-20, updated 2026-11-21 (America/Chicago)
**Status:** LOCAL WINDOWS AND LINUX ACCEPTANCE PASS; PRODUCTION NOT PROMOTED
**Repository:** `insane66613/mcp-proxy` PR #4, branch `integrate/upstream-v0.15.0-20261120`
**Baseline:** fork main `2c9baec6a60d7c2350df730416654474a21319b2`
**Upstream release:** `sparfenyuk/mcp-proxy` v0.15.0, `b3dc6de`

## Repair and new coverage

- Post-startup stdin EOF has a two-second bounded application drain. If local request work remains stuck, it is cancelled inside an application-specific scope before the upstream session is disposed.
- Startup EOF still cancels immediately. The input stream retains EOF across the proxy-construction / application-run scheduling boundary.
- Ordinary application exceptions are re-raised as the original exception object outside the AnyIO task group, avoiding exception-group wrapping. Own-scope EOF cancellation and external SIGINT remain distinct.
- Normal HTTP requests retain configured SDK timeouts. SDK HTTP DELETE retains its separate five-second request/body deadline and cleanup grace.
- Regression tests cover hung app work, cooperative drain, non-EOF long requests, early EOF, exception preservation, external cancellation, stuck reconnect ownership, and real subprocess EOF/SIGINT with an in-flight tool call.
- Windows EOF, POSIX SIGINT and genuine POSIX stdin EOF with pending tool calls are covered, including an exactly-one-DELETE assertion. No test was skipped or modified solely to suppress a demonstrated source defect.
- The thirteen inherited Ruff findings were cleared with narrow annotations/docstrings/diagnostic-script formatting, without changing runtime behavior.

## Local acceptance

- Windows Python 3.14.7: **475 passed, 18 skipped, 7 warnings**, zero failures; `scripts/verify-change.ps1 -Mode Full` reported **zero failed gates**.
- Ubuntu/WSL Python 3.14.4: **491 passed, 9 skipped, 7 warnings**, zero failures with explicit source `PYTHONPATH` for subprocess parity.
- Ruff (repository-wide), Ruff format, Mypy (14 source files), Pylint errors-only and Git diff checks all passed.
- Windows full-gate log: `X:\MCP\mcp-proxy-pr4-20261121-reconnect-full-gates.log`.
- Linux full-suite log: `X:\MCP\mcp-proxy-pr4-20261121-linux-reconnect-full.log`.
- Wheel: `X:\MCP\releases\mcp-proxy-0.15.0-20261120-exception-safe\mcp_proxy-0.15.0-py3-none-any.whl`
- Wheel SHA256: `5F7A499303EA9788D92C845364A3F391598314C59CA70E6DD0BC298A40932E3F`.
- Isolated runtime: `X:\MCP\runtimes\mcp-proxy-0.15.0-20261120-candidate`, installed non-editably.
- Packaged canary: MCP initialize + list-tools + echo tool call passed at `127.0.0.1:18766`; candidate listener and processes 0 after shutdown.

## Release controls

- Production port `3072` still returned HTTP 204 after candidate cleanup. Installed v0.14.0 runtime and rollback remain preserved.
- No production promotion, Cloudflare changes, or service restart was performed.
- The upstream session-limit PR #264 is separate, open, and not included in this candidate.
- This validation does not claim all Python 3.10-3.13 versions, all Linux distributions, or the production service-specific canary/rollback rehearsal.
- Do not treat a mergeable GitHub PR as production acceptance. Keep the production cutover held until the service-specific launcher, authenticated tool manifest, rollback, and traffic-parity gates are verified.
- GitHub Actions and GitHub automated code reviews were not requested or relied upon.


## AiGentAI Copilot residual-risk reconciliation — 2026-11-21

Independent [Microsoft Copilot Think deeper review](https://copilot.cloud.microsoft/chat/conversation/ce2e91ad-9641-4fb0-bd40-126537f1d536) of commit `a980a91` recommended **ACCEPT SOURCE**, **PRODUCTION HOLD**. Follow-up deliberately avoids speculative runtime changes and instead tests the remaining source-level uncertainties.

- **F-3 watcher failure:** injected a failing EOF event observer and verified the unexpected error remains observable in a task-group exception, rather than being silently suppressed. This is deliberate error accounting, not a newly proven runtime defect.
- **F-4 EOF cancellation cleanup error:** blocked application teardown raises an exact sentinel exception in `finally` after EOF cancellation. Verified the exact original exception reaches the caller. Ordinary EOF still exits cleanly.
- **F-6 reconnect DELETE generations:** extended the real reverse-client CLI subprocess test with an upstream that returns an HTTP 404 for generation A, then reinitializes generation B, holds B's tool request and closes stdin. The test asserts exactly one generation-B DELETE, at most one generation-A DELETE, two distinct initializations, bounded process exit and no remaining connection handlers. This is specific scenario coverage, not a mathematical guarantee for every possible reconnect.
- **F-11 workflow predicate:** removed one redundant upstream-repository comparison from each of the two `Clean Docker cache` job conditions. No workflow ran or was requested.

**Updated final local validation:** Windows **475 passed, 18 skipped** and Ubuntu/WSL **491 passed, 9 skipped**, zero failures on both. Repository Full gate reports zero failed Git, Ruff, Ruff formatting, Pylint, Mypy and pytest checks. Logs are listed above. Both test suites retain seven dependency deprecation warnings. No production source modules changed relative to the independently reviewed `a980a91` commit; the previously pinned wheel SHA-256 remains the accepted runtime artifact.

**Residual limits:** Unexpected multi-task failures can legitimately yield an AnyIO exception group, the two-second EOF grace deliberately cancels unfinished work, and other untested reconnect interleavings may differ. Python 3.10–3.13 and other Linux distributions were not tested. Source acceptance does not satisfy service-specific authenticated gateway, manifest, rollback, and managed-supervisor promotion gates.


## Independent follow-up review and F-12 closure — 2026-11-21

The AiGentAI Microsoft Copilot Think deeper review of `ca9d9b683dd1bc2af11ab713679a267b5980ca5b` is at [the saved Copilot conversation](https://copilot.cloud.microsoft/chat/conversation/a79af193-2d54-4c72-98e7-95700b933bf4). Its **CONDITIONAL ACCEPT SOURCE** finding identified a **test-only** assertion weakness: an extra HTTP DELETE with an empty or unexpected session ID could pass the original count checks.

The amended reconnect test now explicitly limits all DELETE keys to generation A or generation B, requires exactly one B DELETE, at most one A DELETE, and checks the total equals that allowed set. The normal single-generation test additionally requires a mapping exactly equal to its expected session ID and count. The previous tautological sum-of-all-counts check was removed.

**Verified after correction:** Windows real subprocess CLI shutdown matrix 7 passed and Ubuntu/WSL corresponding matrix 14 passed, both zero failures. Repository-wide Ruff and formatting remained clean. No production source module or authentication/transport behavior was modified. This closes F-12 for the tested scenario, without claiming universal correctness for arbitrary reconnect interleavings. GitHub Actions and automated GitHub PR review were not invoked.
