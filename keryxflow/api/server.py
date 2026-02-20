"""FastAPI application for KeryxFlow web dashboard."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from keryxflow.web.dashboard import router as dashboard_router

app = FastAPI(title="KeryxFlow API", version="0.13.0")

app.include_router(dashboard_router)


@app.get("/")
async def root() -> RedirectResponse:
    """Redirect root to dashboard."""
    return RedirectResponse(url="/dashboard")


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the API server with uvicorn."""
    uvicorn.run(app, host=host, port=port)
