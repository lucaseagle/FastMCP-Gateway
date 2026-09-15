"""A small deterministic CLI sharing the gateway's policy and execution engine."""

import argparse
import asyncio
import json
import os
import secrets
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from pydantic import ValidationError

from fastmcp_gateway.config import Settings, load_config
from fastmcp_gateway.discovery import discover
from fastmcp_gateway.gateway import Gateway, GatewayError


def initialize() -> None:
    Path("config").mkdir(exist_ok=True)
    config_path = Path("config/gateway.toml")
    if not config_path.exists():
        template = files("fastmcp_gateway").joinpath("templates/gateway.toml").read_text("utf-8")
        with config_path.open("x", encoding="utf-8") as target:
            target.write(template)
    env_path = Path(".env")
    if not env_path.exists():
        descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            target.write(f"GATEWAY_MODE=development\nGATEWAY_TOKEN={secrets.token_urlsafe(32)}\n")
    print("Local configuration ready. Run: fastmcp-gateway demo. Token is in .env.")


async def local_call(args: argparse.Namespace) -> None:
    load_dotenv()
    config = load_config(args.config)
    # CLI is an operator interface: OS access to config and secrets is its trust boundary.
    scopes = {Gateway.scope(site.name) for site in config.sites}
    async with Gateway(config) as gateway:
        result: Any
        if args.command == "sites":
            result = gateway.catalog(scopes)
        elif args.command == "operations":
            result = gateway.operations(args.site, scopes)
        else:
            params = json.loads(args.params)
            if not isinstance(params, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in params.items()
            ):
                raise ValueError("Parameters must be a JSON object of strings")
            result = (await gateway.execute(args.site, args.operation, params, scopes)).model_dump()
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FastMCP Gateway: approved websites as MCP and CLI"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create local demo config and a random token; never overwrite")
    for name in ("serve", "demo"):
        commands.add_parser(
            name,
            help="Run authenticated MCP HTTP"
            if name == "serve"
            else "Run MCP with a fictional local catalog",
        )
    for name in ("sites", "operations", "call", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=Path("config/gateway.toml"))
        if name in ("operations", "call"):
            command.add_argument("site")
        if name == "call":
            command.add_argument("operation")
            command.add_argument("--params", default="{}", help="JSON object with string values")
    importer = commands.add_parser(
        "import-har", help="Offline endpoint inventory; emits unapproved JSON"
    )
    importer.add_argument("har", type=Path)
    importer.add_argument("--origin", required=True)
    importer.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize()
        elif args.command in ("serve", "demo"):
            from fastmcp_gateway.server import create_app
            from fastmcp_gateway.telemetry import configure

            settings = Settings()
            configure(settings.otlp_endpoint)
            app = create_app(settings)
            if args.command == "demo":
                if settings.mode != "development":
                    raise ValueError("Demo is development-only")
                from fastmcp_gateway.demo import add_demo_routes

                add_demo_routes(app)
            uvicorn.run(
                app,
                host=settings.host,
                port=settings.port,
                access_log=False,
                proxy_headers=False,
                server_header=False,
                limit_concurrency=128,
            )
        elif args.command == "validate":
            config = load_config(args.config)
            print(json.dumps({"valid": True, "sites": len(config.sites)}))
        elif args.command == "import-har":
            if args.har.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("HAR exceeds 10 MiB")
            har = json.loads(args.har.read_text(encoding="utf-8-sig"))
            print(json.dumps(discover(har, args.origin, args.name), indent=2))
        else:
            asyncio.run(local_call(args))
        return 0
    except (OSError, ValueError, GatewayError, ValidationError) as error:
        # Pydantic errors may contain secrets as input_value; never print the raw exception.
        code = str(error) if isinstance(error, GatewayError) else "configuration_or_input_error"
        print(json.dumps({"error": code}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
