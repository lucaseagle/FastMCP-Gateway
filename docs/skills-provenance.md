# Development skill provenance

Checked on 2026-09-15. Only the following skills were installed from skills.sh, after the detail page showed PASS for **Gen Agent Trust Hub**, **Socket** and **Snyk**. CLI assessments agreed: Safe / 0 alerts / Low Risk.

| Installed skill | Source | Gen | Socket | Snyk |
|---|---|---|---|---|
| MCP server review | [OWASP](https://www.skills.sh/owasp/secure-agent-playbook/mcp-server-review) | PASS | PASS | PASS |
| Python testing patterns | [wshobson/agents](https://www.skills.sh/wshobson/agents/python-testing-patterns) | PASS | PASS | PASS |

Installation commands:

```bash
npx skills add https://github.com/owasp/secure-agent-playbook --skill mcp-server-review --agent codex --yes
npx skills add https://github.com/wshobson/agents --skill python-testing-patterns --agent codex --yes
```

The local copies live under `.agents/skills/` and are ignored in Git; source paths and computed content hashes are recorded in `skills-lock.json`. OWASP was installed before application implementation. The testing skill was found and installed before the expanded integration/boundary-test pass; the existing local TDD skill guided earlier tests.

The similarly relevant `prefecthq/fastmcp/reviewing-code` page showed three PASS verdicts, but installation found that the repository had renamed the skill. No unverified replacement was installed. FastMCP skills with Snyk WARN were not installed.

These are point-in-time third-party assessments of development instructions, not application penetration tests or a supply-chain guarantee. CLI installs track repository content; the recorded hashes identify the local snapshots, but the provider pages do not establish a cryptographic binding between their audited revision and those snapshots. Recheck all three providers before any update. No claim of such a binding is made.

Upstream skill instructions referenced OWASP `plays/mcp-server-review.md`, which was not bundled with the installed skill; the full supplied SKILL.md procedure was followed. The direct upstream path returned 404, so no unseen supplementary procedure is claimed as reviewed.
