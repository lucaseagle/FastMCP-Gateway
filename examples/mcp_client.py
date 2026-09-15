"""Run against `fastmcp-gateway demo`; token is read from the local environment."""

import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client


async def main() -> None:
    load_dotenv()
    url = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8000/mcp")
    async with Client(url, auth=os.environ["GATEWAY_TOKEN"]) as client:
        sites = await client.call_tool("list_sites", {})
        print("Authorized sites:", sites.data)
        operations = await client.call_tool("list_operations", {"site": "catalog"})
        print("Available operations:", operations.data)
        result = await client.call_tool(
            "execute",
            {
                "site": "catalog",
                "operation": "search",
                "params": {"q": "ThinkPad"},
            },
        )
        print(json.dumps(result.structured_content, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
