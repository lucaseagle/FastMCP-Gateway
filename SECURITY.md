# Security policy

This project is a reference implementation; no SLA, certification or independent penetration-test claim is made. The 0.1 series is the initial supported line. See [the threat model](docs/security.md) for trust boundaries and residual risks.

After publishing the repository, enable GitHub private vulnerability reporting under Settings → Code security. Report vulnerabilities through that channel when available. If it is unavailable, contact the repository owner privately and request a secure reporting channel. Do not post secrets, live exploit targets, private HAR files or sensitive business data in a public issue. No contact address is invented here.

Include affected version, impact, a minimal synthetic reproduction and suggested mitigation. If credentials were exposed, revoke/rotate them and restart affected deployments independently of the report. Use narrowly scoped test systems for security research.
