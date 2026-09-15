"""Strict, operator-owned configuration. Agents cannot register destinations."""

import ipaddress
import json
import re
import tomllib
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastmcp_gateway.policy import check_address

Name = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Operation(StrictModel):
    name: Name
    path: str = Field(max_length=1024)
    description: str = Field(min_length=1, max_length=300)
    query_params: list[Name] = Field(default_factory=list, max_length=20)
    response_format: Literal["json", "text"] = "json"
    fields: list[Name] = Field(default_factory=list, max_length=50)
    max_items: int = Field(default=50, ge=1, le=500)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        if not re.fullmatch(r"/[A-Za-z0-9/_~.\-]*", value):
            raise ValueError("Path must be a fixed, unencoded absolute path")
        if value.startswith("//") or any(part in (".", "..") for part in value.split("/")):
            raise ValueError("Ambiguous path is forbidden")
        return value


class Site(StrictModel):
    name: Name
    base_url: str
    approved: Literal[True] = True
    allowed_networks: list[str] = Field(default_factory=list)
    credential_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{0,100}$")
    credential_header: Literal["Authorization", "X-API-Key", "Cookie"] = "Authorization"
    ca_bundle: Path | None = None
    operations: list[Operation] = Field(min_length=1, max_length=100)

    @field_validator("base_url")
    @classmethod
    def origin_only(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or "\\" in value
            or any(ord(c) < 33 for c in value)
        ):
            raise ValueError("base_url must be an HTTP(S) origin without credentials or path")
        _ = parsed.port
        return value.rstrip("/")

    @field_validator("allowed_networks")
    @classmethod
    def valid_networks(cls, networks: list[str]) -> list[str]:
        return [str(ipaddress.ip_network(network)) for network in networks]

    @model_validator(mode="after")
    def unique_operations(self) -> Self:
        if len({op.name for op in self.operations}) != len(self.operations):
            raise ValueError("Operation names must be unique within a site")
        return self


class GatewayConfig(StrictModel):
    development: bool = False
    sites: list[Site] = Field(min_length=1, max_length=100)
    timeout_seconds: float = Field(default=10, ge=0.1, le=25)
    max_response_bytes: int = Field(default=262144, ge=128, le=1048576)
    max_concurrency: int = Field(default=16, ge=1, le=128)
    requests_per_minute: int = Field(default=60, ge=1, le=10000)

    @model_validator(mode="after")
    def network_policy(self) -> Self:
        if len({site.name for site in self.sites}) != len(self.sites):
            raise ValueError("Site names must be unique")
        for site in self.sites:
            parsed = urlsplit(site.base_url)
            if parsed.scheme != "https" and not self.development:
                raise ValueError("HTTPS is required outside development")
            hostname = parsed.hostname or ""
            try:
                ipaddress.ip_address(hostname)
            except ValueError:
                continue
            check_address(hostname, site.allowed_networks, development=self.development)
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    mode: Literal["development", "production"] = "production"
    config: Path = Path("config/gateway.toml")
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    token: SecretStr | None = None
    jwks_uri: str | None = None
    issuer: str | None = None
    audience: str | None = None
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_origins: list[str] = []
    otlp_endpoint: str | None = None

    @model_validator(mode="after")
    def authentication_required(self) -> Self:
        if self.mode == "production":
            if not self.jwks_uri or not self.issuer or not self.audience:
                raise ValueError("Production requires jwks_uri, issuer and audience")
            if urlsplit(self.jwks_uri).scheme != "https":
                raise ValueError("JWKS must use HTTPS")
            if self.token:
                raise ValueError("Static tokens are development-only")
        elif self.token is None or len(self.token.get_secret_value()) < 32:
            raise ValueError("Development requires a random token of at least 32 characters")
        if not self.allowed_hosts or any("*" in host for host in self.allowed_hosts):
            raise ValueError("Explicit allowed_hosts are required; wildcards are forbidden")
        if any("*" in origin for origin in self.allowed_origins):
            raise ValueError("Wildcard origins are forbidden")
        return self


def load_config(path: Path) -> GatewayConfig:
    if path.stat().st_size > 1048576:
        raise ValueError("Configuration exceeds 1 MiB")
    content = path.read_text(encoding="utf-8")
    data = json.loads(content) if path.suffix == ".json" else tomllib.loads(content)
    return GatewayConfig.model_validate(data)
