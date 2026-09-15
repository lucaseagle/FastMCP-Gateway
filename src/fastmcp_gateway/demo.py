"""Public fictional data for a zero-account local demonstration."""

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

PRODUCTS = [
    {"id": "HW-001", "name": "ThinkPad T14", "price": 1299, "currency": "EUR", "stock": 12},
    {"id": "HW-002", "name": "Dell UltraSharp 27", "price": 449, "currency": "EUR", "stock": 30},
    {"id": "HW-003", "name": "Logitech MX Keys", "price": 109, "currency": "EUR", "stock": 45},
]


def add_demo_routes(app: FastAPI) -> None:
    async def products(request: Request) -> JSONResponse:
        query = request.query_params.get("q", "").lower()
        return JSONResponse(
            [product for product in PRODUCTS if query in str(product["name"]).lower()]
        )

    async def handbook(request: Request) -> HTMLResponse:
        return HTMLResponse(
            "<h1>Procurement handbook</h1><p>Fictional demonstration data.</p>"
            "<p>Orders above EUR 1000 require manager approval.</p>"
        )

    # Insert before the catch-all MCP mount.
    app.router.routes[0:0] = [Route("/demo/products", products), Route("/demo/handbook", handbook)]
