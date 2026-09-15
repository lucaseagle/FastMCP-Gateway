# Threat model and security review

Assets: service credentials, private-network reachability, business data, registry integrity, availability, audit integrity and caller identity. Trust operators and reviewed configuration; distrust agent inputs, HAR entries, DNS and website payloads.

The installed OWASP MCP server review skill guided this authoring-agent review. It is not an independent security audit.

## Tool risk matrix

| Surface | Classification | Authority |
|---|---|---|
| list_sites | READ-ONLY | Authorized connector names |
| list_operations | READ-ONLY | Approved operation metadata for an authorized site |
| execute | READ-ONLY, NETWORK | Approved fixed GET with server-held credential |
| Resource/prompt | READ-ONLY | Static policy or bounded user content |
| CLI | LOCAL OPERATOR, NETWORK | OS user with registry and secret access |
| HAR importer | LOCAL READ | Parse a bounded file; never replay requests |

## Controls and evidence

| Threat | Control |
|---|---|
| SSRF/metadata | Fixed origin/path, literal-IP checks, validated DNS, explicit private CIDRs, no redirects |
| DNS rebinding | The checked answer set is passed directly to the connection; mixed answers fail closed |
| Confused deputy | Check site scope before network access; never forward caller tokens |
| Host/Origin abuse | Explicit hostnames/origins; no wildcard defaults |
| Bad JWTs | RS256, issuer/audience, required expiry/subject, optional nbf/iat; signed-token tests |
| Resource exhaustion | Bounded incoming/outgoing bytes, read/total timeouts, concurrency/site budgets |
| Decompression bombs | Request identity encoding and reject encoded responses |
| Credential retention | No cookie jar, cache or imported credentials; missing credentials fail closed |
| Error/log leakage | Fixed error codes; bounded audit fields; no payloads, queries or tokens |
| Tool poisoning | Operator-owned registry; no dynamic code, shell or browser execution |
| Supply chain | Lockfile, SCA, SHA-pinned actions, Trivy and dependency updates |

Tests cover adversarial addresses/DNS, JWTs, redirect/chunked/malformed/slow responses, authorization, real MCP calls and audit boundaries. See validation evidence for the executed suite.

## Residual risks

1. GET may mutate a badly designed upstream. Operator review must verify semantics.
2. Authorized output may contain sensitive nested values or secrets. Top-level projection is not a general redaction/DLP system.
3. Prompt injection remains possible in retrieved data. HTML extraction and `untrusted` flags do not enforce a boundary inside an LLM.
4. A service account may over-authorize callers. Use connectors with appropriate dataset scope and separate deployments for separate trust domains.
5. Per-site budgets are per process, not per user/cluster. A caller may exhaust another caller's site budget. Configure ingress quotas and concurrency limits when hosting outside the provided CLI.
6. JWKS and OTLP endpoints are operator-owned and may intentionally be internal. Control egress, CA trust, log retention and collector access.
7. Application network checks supplement a firewall. General proxy support, mTLS client certificates and transparent SSO/token refresh are absent.
8. Scans are point-in-time. All image inputs are digest-pinned, but require organization approval and ongoing updates; passing skill audits do not certify the application.
9. Target-environment Docker, AWS, IdP, intranet and Bedrock tests remain necessary.

## Deployment acceptance

Review endpoint semantics/data with the owner; provision least-privilege secrets; require TLS ingress; restrict direct container access; test issuer/audience/scopes and key rotation; set egress/global quotas; verify CA trust; set audit retention/alerts; build and scan the actual image; perform a targeted security assessment before business-sensitive use.
