# Operations runbook

## Local development

Use `uv sync --frozen --python 3.12`, `uv run fastmcp-gateway init`, then `uv run fastmcp-gateway demo`. The generated token is in `.env`; do not paste it into GitHub or command-line arguments. On Windows the file inherits directory ACLs; restrict the project directory to its owner. On POSIX it is created with mode 0600. Stop with Ctrl+C.

If port 8000 is occupied, stop the previous server or update BOTH `GATEWAY_PORT` and the demo registry's `base_url`. `init` intentionally does not overwrite either file. `serve` does not add fictional demo routes.

## Production container

1. Review an enterprise registry, replacing placeholder origin/CIDR/paths/fields.
2. Build `docker build --target runtime -t fastmcp-gateway:0.1.0 .`.
3. Mount the approved registry read-only at `/app/config/production.toml`, and any corporate CA at a read-only path. Set `GATEWAY_CONFIG` accordingly.
4. Inject production settings from the environment/secret manager, with no development `GATEWAY_TOKEN`. Configure issuer, audience, HTTPS JWKS and explicit allowed hosts. Inject upstream headers only for approved sites.
5. Place behind TLS ingress. Bind the application only to the private container/service network. Apply the capability, read-only filesystem and resource restrictions in Compose to your orchestrator.
6. Permit narrowly scoped egress to corporate DNS, approved upstreams, identity provider and optional collector. This app does not consume environment HTTP proxies.
7. Verify health, valid/invalid JWTs, missing scopes, real TLS trust, upstream timeouts and blocked destinations.

The demo Compose file is not an enterprise deployment definition. For production, change its command to `serve`, use production settings and mount an approved registry. Health reports application lifecycle status only; it does not probe every upstream or IdP. `localhost`/`127.0.0.1` should remain in allowed hosts if using the bundled healthcheck.

## AWS deployment

The SAM template is a reviewable deployment example, not an already deployed service. It assumes existing private subnets/security groups and a Secrets Manager secret with an `authorization` key.

1. Review `config/enterprise.example.toml` for the real upstream before building the image. The template intentionally references this packaged file; change the path/name if you package a different reviewed registry. Do not place credentials in the image.
2. Build `docker build --target lambda -t fastmcp-gateway:lambda .` on x86_64, or specify `--platform linux/amd64`. Push to your own ECR repository, scanning and resolving the image to a digest.
3. Run `sam validate --lint --template-file deploy/aws/template.yaml` with AWS SAM installed.
4. Deploy using `sam deploy --guided --template-file deploy/aws/template.yaml`, supplying the ECR ImageUri, Issuer, Audience, JwksUri, GatewayHostname, UpstreamSecretArn, SubnetIds and SecurityGroupIds. CloudFormation needs permission to resolve the secret. Deployment creates billable resources and should follow your organization's release process.
5. Configure custom domain/DNS/certificate separately if used. The template also allows its generated API Gateway hostname. API Gateway and the application both validate JWTs.
6. Test POST `/mcp` using a token with the required site scope. VPC routes must reach the upstream and IdP; add NAT or appropriate endpoints only as your network policy permits.

The Secrets Manager dynamic reference resolves during deployment. Secret rotation requires a configuration update/redeploy to refresh the environment value. The app reads that environment value per call; it does not poll Secrets Manager. Use customer-managed KMS/log policies where organization policy requires them.

Only POST `/mcp` is published by the template. JSON responses fit buffered Lambda/API Gateway requests; no persistent SSE/sessions or server-initiated features are claimed. The function timeout is 28 seconds; upstream timeout is capped at 25 seconds. Cold starts and HTTP gateway quotas must be measured in the target account. Per-process quotas multiply across Lambda execution environments; use API Gateway quotas and the provided concurrency cap.

## Observability and alerting

`GATEWAY_OTLP_ENDPOINT` is the base OTLP HTTP URL; the exporter adds `/v1/traces`, `/v1/metrics`, `/v1/logs`. Unset it to disable external export. The included collector emits basic debug output; configure an approved backend, authenticated transport and retention before production.

Instrument names: `gateway.calls` counter and `gateway.duration` histogram in seconds. Labels are registered site, registered operation and a bounded outcome. Unknown identifiers become `unknown`; request IDs are random per execution. Audit logs omit caller identifiers, URLs, queries, credentials and content. If a user-level audit trail is required, add a reviewed pseudonymous identity design; it is not currently implemented.

Suggested alerts: rising `upstream_timeout`/`upstream_error`, nonzero `credential_unavailable`, sustained `busy`/`rate_limited`, and unexpected `forbidden` volume. Tune thresholds against real workload, not invented baselines. Disable raw request/body logging at proxies and model gateways too.

## Troubleshooting

| Symptom | Action |
|---|---|
| `configuration_or_input_error` | Check schema and environment; CLI suppresses raw validation values to protect secrets |
| HTTP 401 | Check bearer token, signature/issuer/audience, expiry and required subject |
| `forbidden` | Request a token with `site:<name>:read`; do not widen shared credentials |
| HTTP 400 / 403 | Check exact Host / Origin allowlists |
| `upstream_unavailable` | Check DNS policy, CIDR, route, TLS trust and response encoding/JSON |
| `credential_unavailable` | Ensure the configured upstream environment variable is injected |
| `redirect_denied` | Review and configure the final fixed endpoint; redirects remain disabled |
| `unexpected_content_type` | Verify the endpoint is data, not an SSO/login/error HTML page |
| `response_too_large` | Narrow the upstream query or reviewed response limits |
| `rate_limited` / `busy` | Reduce concurrency/rate; scale only with outer quotas in place |

No automatic retry occurs. Repeated retries by an agent may still overload an upstream; constrain agent workflows and ingress budgets.

## Release and rollback

Run local quality gates, dependency audit, build and image scan. Review registry changes like code. Pin the released image digest and archive validation evidence. Roll back by selecting the previous image and registry revision together; no database migration is necessary because the application stores no business data. Rotate credentials after an exposure and restart affected instances. Commit only synthetic fixtures, never `.env`, HAR captures or private registry files.
