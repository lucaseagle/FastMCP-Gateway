"""Smoke-test the WP registry over HTTP MCP; read the local token from .env."""

import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client


async def main() -> None:
    load_dotenv()
    url = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8011/mcp")
    async with Client(url, auth=os.environ["GATEWAY_TOKEN"]) as client:
        print("Tools:", [tool.name for tool in await client.list_tools()])
        print("Sites:", (await client.call_tool("list_sites", {})).data)
        print(
            "Operations:",
            (await client.call_tool("list_operations", {"site": "wp"})).data,
        )
        result = await client.call_tool(
            "execute", {"site": "wp", "operation": "homepage", "params": {}}
        )
        print(json.dumps(result.structured_content, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
