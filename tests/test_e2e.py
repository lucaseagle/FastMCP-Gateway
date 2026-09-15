import asyncio
import socket

import pytest
import uvicorn
from fastmcp import Client

from fastmcp_gateway.config import GatewayConfig, Settings
from fastmcp_gateway.demo import add_demo_routes
from fastmcp_gateway.server import create_app


class ReadyServer(uvicorn.Server):
    def __init__(self, config):
        super().__init__(config)
        self.ready = asyncio.Event()

    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        self.ready.set()


async def test_full_http_client_to_gateway_to_upstream_flow():
    token = "ephemeral-integration-test-token-32-characters"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        config = GatewayConfig.model_validate(
            {
                "development": True,
                "sites": [
                    {
                        "name": "catalog",
                        "base_url": f"http://127.0.0.1:{port}",
                        "allowed_networks": ["127.0.0.1/32"],
                        "operations": [
                            {
                                "name": "search",
                                "path": "/demo/products",
                                "description": "Read demo products",
                                "query_params": ["q"],
                                "fields": ["id", "name"],
                            }
                        ],
                    }
                ],
            }
        )
        app = create_app(Settings(_env_file=None, mode="development", token=token), config)
        add_demo_routes(app)
        server = ReadyServer(uvicorn.Config(app, log_level="error", access_log=False))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            await asyncio.wait_for(server.ready.wait(), 10)
            async with Client(f"http://127.0.0.1:{port}/mcp", auth=token) as client:
                sites = await client.call_tool("list_sites", {})
                assert "catalog" in str(sites.data)
                operations = await client.call_tool("list_operations", {"site": "catalog"})
                assert "search" in str(operations.data)
                result = await client.call_tool(
                    "execute",
                    {"site": "catalog", "operation": "search", "params": {"q": "ThinkPad"}},
                )
                assert result.structured_content["data"] == [
                    {"id": "HW-001", "name": "ThinkPad T14"}
                ]
                assert result.structured_content["untrusted"] is True
                assert await client.read_resource("gateway://policy")
                assert await client.get_prompt(
                    "research_site", {"site": "catalog", "question": "Which laptops?"}
                )
                with pytest.raises(Exception, match="forbidden"):
                    await client.call_tool("execute", {"site": "other", "operation": "search"})
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, 10)
