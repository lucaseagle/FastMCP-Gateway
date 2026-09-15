# WP.pl HTTP MCP smoke test

## Run locally (PowerShell)

Use the existing environment, or install dependencies as described in README.
Run `fastmcp-gateway init` first if `.env` does not yet exist.
The development bearer token stays in `.env`; it is never forwarded to WP.

```powershell
$env:GATEWAY_CONFIG = 'config/wp.example.toml'
$env:GATEWAY_MODE = 'development'
$env:GATEWAY_PORT = '8011'
& '.venv\Scripts\python.exe' -m fastmcp_gateway.cli serve
```

From another terminal in the project directory:

```powershell
& '.venv\Scripts\python.exe' examples/wp_client.py
```

The client reads `.env`, lists MCP tools, sites and operations, then executes
`wp/homepage`. Override `GATEWAY_URL` if using a different port. The server must
have outbound HTTPS access to `www.wp.pl`. Stop it with Ctrl+C when finished.

## Observed result (2026-09-15)

- Real HTTP MCP endpoint: `http://127.0.0.1:8011/mcp`.
- Tools discovered: `list_sites`, `list_operations`, `execute`.
- Registered site: `wp`; operation: `homepage`.
- WP returned HTTP 200 and UTF-8 HTML without content compression.
- A diagnostic fetch measured 418,170 bytes, exceeding the default 256 KiB.
  The WP example therefore uses a bounded 512 KiB response limit; the global
  default and runtime implementation are unchanged.
- The MCP call returned homepage text, navigation and news headlines, with
  `untrusted: true` and `truncated: true` (16,000-character text limit).
- Successful call request ID: `d2a361e16a514ec693fc16d16960abdd`.

The initial sandboxed process could not access the external network and returned
`upstream_unavailable`; a direct diagnostic confirmed Windows socket error 10013.
The live MCP call succeeded after launching the server with network permission.

This verifies public homepage retrieval through MCP. It does not verify individual
article retrieval, search, login, browser rendering, structured headline/link
extraction or any private WP API. Text includes navigation and promotional content;
link attributes are not retained. Homepage size and availability can change.
