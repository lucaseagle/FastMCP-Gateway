import socket

import pytest
from aiohttp.abc import ResolveResult

from fastmcp_gateway.policy import PolicyResolver


@pytest.mark.parametrize(
    "addresses,allowed",
    [
        (["93.184.216.34"], True),
        (["93.184.216.34", "10.0.0.1"], False),
        (["169.254.169.254"], False),
    ],
)
async def test_dns_answers_are_checked_as_a_set(monkeypatch, addresses, allowed):
    async def resolve(self, host, port, family):
        return [
            ResolveResult(
                hostname=host, host=ip, port=port, family=socket.AF_INET, proto=0, flags=0
            )
            for ip in addresses
        ]

    monkeypatch.setattr("fastmcp_gateway.policy.ThreadedResolver.resolve", resolve)
    resolver = PolicyResolver([], development=False)
    try:
        if allowed:
            results = await resolver.resolve("example.com", 443)
            assert [result["host"] for result in results] == addresses
        else:
            with pytest.raises(ValueError):
                await resolver.resolve("example.com", 443)
    finally:
        await resolver.close()
