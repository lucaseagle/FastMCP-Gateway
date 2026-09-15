# Validation evidence

Authoring environment: Windows, CPython 3.12.14. Executed 2026-09-15. Results are point-in-time; no external deployment success is implied.

| Check | Observed result |
|---|---|
| `python scripts/check.py` | Exit 0 |
| Ruff lint and formatting | Passed |
| Strict mypy | Passed for all 9 source modules |
| Bandit | Passed with no findings |
| pytest with optional agent dependencies | **68 passed**, no skipped tests |
| Source coverage | **91.63%**, above the 85% gate |
| Real HTTP MCP → gateway → local upstream | Passed, including discovery, execution, resource, prompt and denied site |
| CLI and standalone MCP client against running demo | Returned the expected fictional ThinkPad record |
| JWT validation | Valid signed token accepted; bad issuer/audience/expiry/subject/nbf/iat rejected |
| DNS/network policy | Private/default-deny, metadata, special addresses and mixed DNS-answer tests passed |
| OTLP wiring | All three SDK signal pipelines exercised using in-memory exporter substitutes |
| Dependency audit, including optional agent dependencies | No known vulnerabilities reported by pip-audit; local editable package excluded |
| Package build | Wheel and source distribution built successfully |
| Deployment files | YAML syntax parsed; this is not SAM semantic/deployment validation |
| Container inputs | Python, uv and Lambda Adapter availability verified; registry digests pinned |

The suite currently emits two non-failing dependency deprecation warnings: Starlette's AnyIO BlockingPortal alias and the OpenTelemetry SDK LoggingHandler (which recommends the separate logging instrumentation package). No warning suppression has been added. Plan that migration when upgrading telemetry dependencies.

Not executed in this environment: Docker build/runtime/Trivy (Docker unavailable), GitHub-hosted CI, AWS SAM deployment, real enterprise JWKS rotation, corporate VPN/CA integration, external OTLP collector export, live AWS Bedrock invocation, Python 3.13 CI matrix. These are provided as reproducible configurations/examples and require target-environment verification.

No public website was scraped for integration tests. Fixtures are synthetic; network tests use local HTTP servers. No numerical claims about MCP versus CLI token savings, production throughput, latency or agent accuracy are made.

The project is left local without Git metadata or a commit, as requested. Use the README's setup commands and publish it to your own repository when ready; keep `.env`, private configuration, real HAR captures and local environments excluded.
