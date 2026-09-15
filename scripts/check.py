"""Run the same local quality gates as CI. Requires `uv sync`."""

import subprocess
import sys

CHECKS = [
    ["ruff", "check", "src", "tests", "examples", "scripts"],
    ["ruff", "format", "--check", "src", "tests", "examples", "scripts"],
    ["mypy", "src"],
    ["bandit", "-r", "src", "-q"],
    ["pytest", "--cov=fastmcp_gateway", "--cov-report=term-missing", "--cov-fail-under=85"],
]


def main() -> int:
    for command in CHECKS:
        result = subprocess.run([sys.executable, "-m", *command], check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
