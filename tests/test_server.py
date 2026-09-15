import pytest
from fastapi.testclient import TestClient

from fastmcp_gateway.config import GatewayConfig, Settings

TOKEN = "development-test-token-with-at-least-32-characters"


def settings(**kwargs):
    return Settings(
        _env_file=None,
        mode="development",
        token=TOKEN,
        allowed_hosts=["testserver", "localhost", "127.0.0.1"],
        **kwargs,
    )


def registry():
    return GatewayConfig.model_validate(
        {
            "sites": [
                {
                    "name": "catalog",
                    "base_url": "https://example.com",
                    "operations": [
                        {"name": "products", "path": "/products", "description": "Read products"}
                    ],
                }
            ]
        }
    )


def rpc(method, params=None):
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}


def headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"}


def test_health_and_real_mcp_discovery():
    from fastmcp_gateway.server import create_app

    with TestClient(create_app(settings(), registry())) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        response = client.post(
            "/mcp",
            headers=headers(),
            json=rpc(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            ),
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["serverInfo"]["name"] == "FastMCP Gateway"
        response = client.post("/mcp", headers=headers(), json=rpc("tools/list"))
        assert {tool["name"] for tool in response.json()["result"]["tools"]} == {
            "list_sites",
            "list_operations",
            "execute",
        }
        response = client.post(
            "/mcp",
            headers=headers(),
            json=rpc("tools/call", {"name": "list_sites", "arguments": {}}),
        )
        assert "catalog" in response.text


@pytest.mark.parametrize("token", ["wrong-token", ""])
def test_invalid_bearer_is_rejected(token):
    from fastmcp_gateway.server import create_app

    with TestClient(create_app(settings(), registry())) as client:
        assert (
            client.post("/mcp", headers=headers(token), json=rpc("tools/list")).status_code == 401
        )


def test_origin_host_and_body_guards():
    from fastmcp_gateway.server import create_app

    with TestClient(create_app(settings(), registry())) as client:
        assert (
            client.post(
                "/mcp",
                headers={**headers(), "Origin": "https://evil.example"},
                json=rpc("tools/list"),
            ).status_code
            == 403
        )
        assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
        assert client.post("/mcp", headers=headers(), content="x" * 70000).status_code == 413


def test_production_rejects_development_registry():
    from fastmcp_gateway.server import create_app

    cfg = registry().model_copy(update={"development": True})
    prod = Settings(
        _env_file=None,
        mode="production",
        jwks_uri="https://id.example/jwks",
        issuer="https://id.example",
        audience="gateway",
    )
    with pytest.raises(ValueError, match="development"):
        create_app(prod, cfg)
