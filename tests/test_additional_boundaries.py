import asyncio
import json
import logging

import pytest
from aiohttp import web

from fastmcp_gateway.config import GatewayConfig
from fastmcp_gateway.gateway import Gateway, GatewayError


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("compressed", "encoded_response_denied"),
        ("mime", "unexpected_content_type"),
        ("malformed", "upstream_unavailable"),
        ("shape", "unexpected_response_shape"),
        ("chunked", "response_too_large"),
        ("slow", "upstream_timeout"),
    ],
)
async def test_upstream_failure_modes_are_bounded(kind, expected):
    async def handler(request):
        if kind == "compressed":
            return web.Response(body=b"compressed", headers={"Content-Encoding": "gzip"})
        if kind == "mime":
            return web.Response(text="not JSON")
        if kind == "malformed":
            return web.Response(body=b"{broken", content_type="application/json")
        if kind == "shape":
            return web.json_response([1, 2])
        if kind == "slow":
            await asyncio.sleep(0.2)
            return web.json_response([])
        response = web.StreamResponse(headers={"Content-Type": "application/json"})
        await response.prepare(request)
        await response.write(b"x" * 2048)
        await response.write_eof()
        return response

    app = web.Application()
    app.router.add_get("/data", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    config = GatewayConfig.model_validate(
        {
            "development": True,
            "timeout_seconds": 0.1,
            "max_response_bytes": 1024,
            "sites": [
                {
                    "name": "test",
                    "base_url": f"http://127.0.0.1:{port}",
                    "allowed_networks": ["127.0.0.1/32"],
                    "operations": [
                        {"name": "read", "path": "/data", "description": "Read", "fields": ["id"]}
                    ],
                }
            ],
        }
    )
    try:
        async with Gateway(config) as gateway:
            with pytest.raises(GatewayError, match=expected):
                await gateway.execute("test", "read", {}, {"site:test:read"})
    finally:
        await runner.cleanup()


async def test_audit_does_not_record_query_or_unknown_identifiers(caplog):
    config = GatewayConfig.model_validate(
        {
            "sites": [
                {
                    "name": "test",
                    "base_url": "https://example.com",
                    "operations": [{"name": "read", "path": "/", "description": "Read"}],
                }
            ]
        }
    )
    audit = logging.getLogger("gateway.audit")
    old = audit.propagate
    audit.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="gateway.audit"):
            with pytest.raises(GatewayError):
                await Gateway(config).execute(
                    "SECRET_SITE", "SECRET_OPERATION", {"secret": "SECRET_VALUE"}, set()
                )
        assert "SECRET" not in caplog.text
        event = json.loads(caplog.records[-1].message)
        assert event["outcome"] == "forbidden"
        assert event["site"] == "unknown"
    finally:
        audit.propagate = old
