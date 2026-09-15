# Contributing

Use Python 3.12+ and uv. Run `uv sync --frozen --extra agent`, then `uv run python scripts/check.py`. Run `uv run pip-audit --skip-editable` and `uv build` before proposing a release.

Keep changes localized. Add a failing behavior test before changing an execution/security boundary, then verify it passes. Test observable interfaces; mock DNS and external exporters only at those boundaries. Use local HTTP fixtures, not public-site scraping, in CI. Never commit real HARs, credentials or private business records.

New connectors need data-owner approval, proof of read-only behavior, exact destination/path/parameter scope, safe projections, failure cases and a synthetic fixture. Avoid new dependencies without explaining why existing components cannot meet the need. Update the threat model when introducing authority such as writes, browser execution, proxying or user impersonation.

Pull requests should state the concrete behavior change, tests executed and remaining limits. Run containers as non-root; deployment approval belongs to the infrastructure owner. Do not publish scan results as security certification.
