# SanityCloud mcp-proxy v0.15.0 integration acceptance

**Date:** 2026-11-20 (America/Chicago)
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

- Windows Python 3.14.7: **472 passed, 18 skipped, 7 warnings**, zero failures; `scripts/verify-change.ps1 -Mode Full` reported **zero failed gates**.
- Ubuntu/WSL Python 3.14.4: **487 passed, 9 skipped, 7 warnings**, zero failures with explicit source `PYTHONPATH` for subprocess parity.
- Ruff (repository-wide), Ruff format, Mypy (14 source files), Pylint errors-only and Git diff checks all passed.
- Windows full-gate log: `X:\MCP\mcp-proxy-pr4-exception-fix-full-gates.log`.
- Linux full-suite log: `X:\MCP\mcp-proxy-pr4-exception-fix-linux-full.log`.
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
