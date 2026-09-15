"""Transport-independent execution with one policy path for MCP and CLI."""

import asyncio
import json
import logging
import os
import ssl
import time
import uuid
from collections import deque
from html.parser import HTMLParser
from types import TracebackType
from typing import Any, Self

import aiohttp
from opentelemetry import metrics, trace
from pydantic import BaseModel

from fastmcp_gateway.config import GatewayConfig, Operation, Site
from fastmcp_gateway.policy import PolicyResolver

logger = logging.getLogger("gateway.audit")
tracer = trace.get_tracer("fastmcp_gateway")
meter = metrics.get_meter("fastmcp_gateway")
calls = meter.create_counter("gateway.calls", description="Gateway executions by outcome")
duration = meter.create_histogram("gateway.duration", unit="s")


class GatewayError(Exception):
    """Only bounded error codes cross the agent boundary."""


class Result(BaseModel):
    site: str
    operation: str
    data: Any
    truncated: bool = False
    untrusted: bool = True
    request_id: str


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "template"):
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "template"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class Gateway:
    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self.sites = {site.name: site for site in config.sites}
        self._sessions: dict[str, aiohttp.ClientSession] = {}
        self._resolvers: list[PolicyResolver] = []
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._budgets: dict[str, deque[float]] = {site.name: deque() for site in config.sites}

    async def __aenter__(self) -> Self:
        try:
            for site in self.config.sites:
                resolver = PolicyResolver(
                    site.allowed_networks, development=self.config.development
                )
                self._resolvers.append(resolver)
                context = ssl.create_default_context(cafile=site.ca_bundle)
                connector = aiohttp.TCPConnector(
                    resolver=resolver,
                    ssl=context,
                    use_dns_cache=False,
                    limit=self.config.max_concurrency,
                )
                self._sessions[site.name] = aiohttp.ClientSession(
                    connector=connector,
                    trust_env=False,
                    auto_decompress=False,
                    cookie_jar=aiohttp.DummyCookieJar(),
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
                    headers={"Accept-Encoding": "identity", "User-Agent": "FastMCP-Gateway/0.1"},
                )
        except Exception:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for session in self._sessions.values():
            await session.close()
        for resolver in self._resolvers:
            await resolver.close()
        self._sessions.clear()
        self._resolvers.clear()

    @staticmethod
    def scope(site: str) -> str:
        return f"site:{site}:read"

    def catalog(self, scopes: set[str]) -> list[dict[str, str]]:
        return [
            {"name": name, "scope": self.scope(name)}
            for name in self.sites
            if self.scope(name) in scopes
        ]

    def operations(self, site: str, scopes: set[str]) -> list[dict[str, Any]]:
        target = self._authorize(site, scopes)
        return [op.model_dump(exclude={"path"}) for op in target.operations]

    def _authorize(self, site: str, scopes: set[str]) -> Site:
        if self.scope(site) not in scopes:
            raise GatewayError("forbidden")
        if site not in self.sites:
            raise GatewayError("not_found")
        return self.sites[site]

    def _budget(self, site: str) -> None:
        now = time.monotonic()
        budget = self._budgets[site]
        while budget and budget[0] <= now - 60:
            budget.popleft()
        if len(budget) >= self.config.requests_per_minute:
            raise GatewayError("rate_limited")
        budget.append(now)

    async def execute(
        self, site: str, operation: str, params: dict[str, str], scopes: set[str]
    ) -> Result:
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        outcome = "ok"
        # Only registry identifiers enter telemetry; attacker-supplied names never become labels.
        safe_site = site if site in self.sites else "unknown"
        safe_operation = "unknown"
        with tracer.start_as_current_span(
            "gateway.execute", record_exception=False, set_status_on_exception=False
        ) as span:
            try:
                target = self._authorize(site, scopes)
                op = next((item for item in target.operations if item.name == operation), None)
                if op is None:
                    raise GatewayError("not_found")
                safe_operation = op.name
                if any(key not in op.query_params for key in params) or any(
                    len(value) > 512 or any(ord(char) < 32 for char in value)
                    for value in params.values()
                ):
                    raise GatewayError("invalid_parameters")
                if site not in self._sessions:
                    raise GatewayError("not_ready")
                self._budget(site)
                if self._semaphore.locked():
                    raise GatewayError("busy")
                async with self._semaphore:
                    async with asyncio.timeout(self.config.timeout_seconds):
                        data, truncated = await self._fetch(target, op, params)
                return Result(
                    site=site,
                    operation=operation,
                    data=data,
                    truncated=truncated,
                    request_id=request_id,
                )
            except GatewayError as error:
                outcome = str(error)
                raise
            except TimeoutError:
                outcome = "upstream_timeout"
                raise GatewayError(outcome) from None
            except (aiohttp.ClientError, ValueError, UnicodeError, RecursionError, OSError):
                outcome = "upstream_unavailable"
                raise GatewayError(outcome) from None
            finally:
                elapsed = time.monotonic() - started
                attributes = {"site": safe_site, "operation": safe_operation, "outcome": outcome}
                span.set_attributes(attributes)
                span.set_attribute("request_id", request_id)
                calls.add(1, attributes)
                duration.record(elapsed, attributes)
                logger.info(
                    json.dumps(
                        {
                            "event": "gateway.execute",
                            "request_id": request_id,
                            **attributes,
                            "duration_ms": round(elapsed * 1000, 2),
                        }
                    )
                )

    async def _fetch(
        self, site: Site, operation: Operation, params: dict[str, str]
    ) -> tuple[Any, bool]:
        headers: dict[str, str] = {}
        if site.credential_env:
            credential = os.environ.get(site.credential_env)
            if not credential:
                raise GatewayError("credential_unavailable")
            headers[site.credential_header] = credential
        async with self._sessions[site.name].get(
            site.base_url + operation.path,
            params=params,
            headers=headers,
            allow_redirects=False,
        ) as response:
            if 300 <= response.status < 400:
                raise GatewayError("redirect_denied")
            if response.status != 200:
                raise GatewayError("upstream_error")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise GatewayError("encoded_response_denied")
            if response.content_length and response.content_length > self.config.max_response_bytes:
                raise GatewayError("response_too_large")
            body = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                body.extend(chunk)
                if len(body) > self.config.max_response_bytes:
                    raise GatewayError("response_too_large")
            content_type = response.content_type
        if operation.response_format == "json":
            if content_type != "application/json" and not content_type.endswith("+json"):
                raise GatewayError("unexpected_content_type")
            data = json.loads(body)
            truncated = isinstance(data, list) and len(data) > operation.max_items
            if isinstance(data, list):
                data = data[: operation.max_items]
                if operation.fields:
                    data = [self._project(item, operation.fields) for item in data]
            elif operation.fields:
                data = self._project(data, operation.fields)
            return data, truncated
        if content_type not in ("text/plain", "text/html"):
            raise GatewayError("unexpected_content_type")
        text = body.decode("utf-8")
        if content_type == "text/html":
            parser = TextExtractor()
            parser.feed(text)
            text = "\n".join(parser.parts)
        # Tool text is data, never an HTML document to execute.
        return text[:16000], len(text) > 16000

    @staticmethod
    def _project(data: Any, fields: list[str]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise GatewayError("unexpected_response_shape")
        return {key: data[key] for key in fields if key in data}
