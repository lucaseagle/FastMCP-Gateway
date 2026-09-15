"""Network policy enforced inside DNS resolution, before sockets are opened."""

import ipaddress
import socket

from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.resolver import ThreadedResolver

_PRIVATE = tuple(
    ipaddress.ip_network(cidr)
    for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def check_address(address: str, networks: list[str], *, development: bool) -> str:
    ip = ipaddress.ip_address(address)
    allowed = any(ip in ipaddress.ip_network(network) for network in networks)
    if "%" in address or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped):
        raise ValueError("Destination address is forbidden")
    if ip.is_loopback and development and allowed:
        return str(ip)
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        raise ValueError("Destination address is forbidden")
    if ip.is_global:
        return str(ip)
    if allowed and any(ip in network for network in _PRIVATE):
        return str(ip)
    raise ValueError("Destination address is not authorized")


class PolicyResolver(AbstractResolver):
    """Validate every answer, returning the same approved addresses to aiohttp.

    There is no separate preflight lookup followed by an unchecked second lookup.
    Mixed public/private DNS answers fail closed. aiohttp handles TLS hostname/SNI.
    """

    def __init__(self, networks: list[str], *, development: bool) -> None:
        self._resolver = ThreadedResolver()
        self._networks = networks
        self._development = development

    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[ResolveResult]:
        answers = await self._resolver.resolve(host, port, socket.AddressFamily(family))
        for answer in answers:
            check_address(answer["host"], self._networks, development=self._development)
        return answers

    async def close(self) -> None:
        await self._resolver.close()
