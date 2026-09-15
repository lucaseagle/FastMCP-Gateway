# Architecture and decision record

## Assumptions

Operators own the registry; callers, HAR files, DNS and website content are untrusted. Defaults target modest interactive workloads: 16 concurrent upstream calls, 60 requests/site/minute/process, 10-second timeout, 256 KiB responses. These are limits, not benchmarks or an SLA. Deployment owners supply routing, DNS, TLS ingress, identity, secret lifecycle and global quotas. One deployment is one administrative trust domain.

## ADR-001: registry and progressive discovery

Expose three MCP tools; reveal operation contracts on demand. An unrestricted URL fetcher was rejected because it grants excessive destination authority. A tool per endpoint expands initial metadata. Browser automation requires a separate browser, credential and egress isolation design. Consequence: custom dynamic paths and transformations require a reviewed adapter. HAR candidates remain unapproved until operator review.

## ADR-002: enforce policy in DNS resolution

aiohttp connects to the addresses returned by the validating resolver. Reject an entire answer set if any address is forbidden. Disable redirects, environment proxies, DNS caching and automatic cookies. Check literal IPs during registry validation. TLS uses the original hostname. A DNS preflight followed by an independent HTTP lookup was rejected because rebinding can change the second answer. Network firewalls remain necessary.

## ADR-003: independent caller and upstream identities

Use resource-server JWT verification with site scopes. Require issuer, audience, expiry and subject; validate optional nbf/iat. A dedicated server-held credential authenticates each upstream. Never forward caller tokens. Interactive login and user impersonation are outside scope. Changing an external secret normally requires redeployment/restart to update the process environment.

## ADR-004: stateless HTTP and bounded work

Use stateless Streamable HTTP and JSON responses. Single-attempt GET requests avoid retries amplifying traffic. Bound bodies before parsing; reject encoded responses. Local budgets and concurrency caps protect one process. Replicas need ingress quotas. Session resumption, sampling and long jobs need another runtime profile. Operators must verify that each GET is semantically read-only.

## ADR-005: minimize retained and exported data

No response cache, HAR persistence, database or browser session store. Export only registered IDs, fixed outcomes, durations and random request IDs. Telemetry is opt-in. Projection is not DLP: data still reaches the caller and potentially their model provider.

## Role-to-evidence mapping

| Requirement | Evidence | Boundary |
|---|---|---|
| FastMCP/server protocol | server module, real HTTP tools/resource/prompt tests | SDK owns protocol parsing |
| Async Python/Pydantic | pooled aiohttp, resolver, strict contracts | Bounded integrations, not a crawler |
| Enterprise onboarding | HAR discovery, registry, CA/credential settings | Operator approval required |
| OpenTelemetry | three signals, sanitized audit, exporter wiring tests | External backend not deployed |
| Container security | non-root, read-only Compose, capability/resource controls | Actual image checked by CI |
| Lambda/API Gateway | SAM and Lambda Web Adapter target | Not cloud-deployed during authoring |
| LangGraph/Bedrock | two-node graph and deterministic test; optional Converse | Live inference needs AWS credentials |
| CI/CD | locked dependencies, pinned actions, SCA/image gates | GitHub runs after publication |
| AgentCore/Strands | integration boundary below | No implementation claim |

## AgentCore boundary

An AgentCore-hosted agent can call the gateway through routed network access and an organization-issued token. Give it only required site scopes. AgentCore identity exchange, runtime packaging and deployment are separate tasks; the SAM template is not AgentCore support.
