import json

import pytest
import pytest_asyncio
from aiohttp import web


@pytest_asyncio.fixture
async def upstream():
    app = web.Application()

    async def products(request):
        return web.json_response(
            [
                {"id": 1, "name": "Laptop", "secret": "private"},
                {"id": 2, "name": "Monitor", "secret": "private"},
            ]
        )

    async def redirect(request):
        return web.Response(
            status=302, headers={"Location": "http://169.254.169.254/latest/meta-data"}
        )

    async def large(request):
        return web.Response(text="x" * 2000)

    async def html(request):
        return web.Response(
            text="<h1>Catalog</h1><script>steal()</script><p>Available</p>",
            content_type="text/html",
        )

    async def error(request):
        return web.Response(status=500, text="SECRET INTERNAL")

    for path, handler in [
        ("products", products),
        ("redirect", redirect),
        ("large", large),
        ("html", html),
        ("error", error),
    ]:
        app.router.add_get(f"/{path}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    server = web.TCPSite(runner, "127.0.0.1", 0)
    await server.start()
    port = runner.addresses[0][1]
    yield f"http://127.0.0.1:{port}"
    await runner.cleanup()


def config(url, **overrides):
    from fastmcp_gateway.config import GatewayConfig

    return GatewayConfig.model_validate(
        dict(
            development=True,
            sites=[
                dict(
                    name="catalog",
                    base_url=url,
                    allowed_networks=["127.0.0.1/32"],
                    operations=[
                        dict(
                            name=name,
                            path=f"/{name}",
                            description=f"Read {name}",
                            query_params=["q"],
                            fields=["id", "name"] if name == "products" else [],
                            response_format="text" if name in ("html", "large") else "json",
                            max_items=1,
                        )
                        for name in ["products", "redirect", "large", "html", "error"]
                    ],
                )
            ],
            **overrides,
        )
    )


async def test_approved_call_projects_fields_and_caps_records(upstream):
    from fastmcp_gateway.gateway import Gateway

    async with Gateway(config(upstream)) as gateway:
        result = await gateway.execute(
            "catalog", "products", {"q": "laptop"}, {"site:catalog:read"}
        )
    assert result.data == [{"id": 1, "name": "Laptop"}]
    assert result.truncated
    assert result.untrusted is True
    assert "private" not in result.model_dump_json()


async def test_unauthorized_call_is_denied_before_network(upstream):
    from fastmcp_gateway.gateway import Gateway, GatewayError

    async with Gateway(config(upstream)) as gateway:
        with pytest.raises(GatewayError, match="forbidden"):
            await gateway.execute("catalog", "products", {}, set())


@pytest.mark.parametrize(
    "operation,params,code",
    [
        ("redirect", {}, "redirect_denied"),
        ("large", {}, "response_too_large"),
        ("products", {"url": "http://evil.com"}, "invalid_parameters"),
        ("error", {}, "upstream_error"),
        ("missing", {}, "not_found"),
    ],
)
async def test_fail_closed(upstream, operation, params, code):
    from fastmcp_gateway.gateway import Gateway, GatewayError

    async with Gateway(config(upstream, max_response_bytes=1024)) as gateway:
        with pytest.raises(GatewayError, match=code) as error:
            await gateway.execute("catalog", operation, params, {"site:catalog:read"})
    assert "SECRET" not in str(error.value)


async def test_html_is_returned_as_inert_text(upstream):
    from fastmcp_gateway.gateway import Gateway

    async with Gateway(config(upstream)) as gateway:
        result = await gateway.execute("catalog", "html", {}, {"site:catalog:read"})
    assert "Catalog" in result.data
    assert "steal" not in result.data
    assert "<" not in result.data


async def test_rate_budget_applies_to_the_site_across_callers(upstream):
    from fastmcp_gateway.gateway import Gateway, GatewayError

    async with Gateway(config(upstream, requests_per_minute=1)) as gateway:
        await gateway.execute("catalog", "products", {}, {"site:catalog:read"})
        with pytest.raises(GatewayError, match="rate_limited"):
            await gateway.execute("catalog", "products", {}, {"site:catalog:read"})


def test_har_discovery_discards_secrets_values_bodies_and_non_get_requests():
    from fastmcp_gateway.discovery import discover

    request = dict(
        method="GET",
        url="https://example.com/api/products?q=PRIVATE&token=SECRET",
        headers=[dict(name="Authorization", value="SECRET")],
        cookies=[dict(name="session", value="SECRET")],
    )
    har = {
        "log": {
            "entries": [
                {
                    "request": request,
                    "response": {"content": {"mimeType": "application/json", "text": "SECRET"}},
                },
                {"request": dict(method="POST", url="https://example.com/delete")},
            ]
        }
    }
    candidate = discover(har, "https://example.com", "catalog")
    serialized = json.dumps(candidate)
    assert "SECRET" not in serialized and "PRIVATE" not in serialized
    assert "token" not in serialized
    assert candidate["sites"][0]["approved"] is False
    assert len(candidate["sites"][0]["operations"]) == 1
