"""Offline HAR inventory. No replay, credential extraction or automatic approval."""

import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from fastmcp_gateway.config import Operation, Site

_SENSITIVE = re.compile(r"token|key|auth|password|secret|session|signature|cookie|jwt", re.I)


def discover(har: dict[str, Any], origin: str, name: str) -> dict[str, Any]:
    if not isinstance(har, dict) or not isinstance(har.get("log"), dict):
        raise ValueError("Invalid HAR envelope")
    entries = har["log"].get("entries")
    if not isinstance(entries, list):
        raise ValueError("Invalid HAR entries")
    operations: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Validate the operator-provided origin before inspecting untrusted HAR entries.
    site = Site(
        name=name,
        base_url=origin,
        operations=[Operation(name="placeholder", path="/", description="placeholder")],
    )
    for entry in entries[:10000]:
        if not isinstance(entry, dict):
            continue
        request = entry.get("request", {})
        if not isinstance(request, dict) or not isinstance(request.get("url"), str):
            continue
        if request.get("method") != "GET":
            continue
        parsed = urlsplit(request.get("url", ""))
        if (
            parsed.username
            or parsed.password
            or f"{parsed.scheme}://{parsed.netloc}" != site.base_url
        ):
            continue
        if parsed.path in seen or _SENSITIVE.search(parsed.path):
            continue
        response = entry.get("response", {})
        if not isinstance(response, dict) or not isinstance(response.get("content"), dict):
            continue
        mime = response["content"].get("mimeType", "")
        if not isinstance(mime, str):
            continue
        if "json" not in mime and mime not in ("text/html", "text/plain"):
            continue
        keys = sorted(
            {
                key
                for key, _ in parse_qsl(parsed.query)
                if not _SENSITIVE.search(key) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key)
            }
        )
        try:
            op = Operation(
                name=f"read_{len(operations) + 1}",
                path=parsed.path or "/",
                description="Review endpoint purpose before approval",
                query_params=keys,
                response_format="json" if "json" in mime else "text",
            )
        except ValueError:
            continue
        seen.add(parsed.path)
        operations.append(op.model_dump())
        if len(operations) >= 100:
            break
    return {
        "development": False,
        "sites": [
            {"name": name, "base_url": site.base_url, "approved": False, "operations": operations}
        ],
    }
