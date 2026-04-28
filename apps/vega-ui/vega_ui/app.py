"""Application factory and entry point."""

from __future__ import annotations

import os

from fastapi import FastAPI

from vega_ui.routes import charts, export, mutations
from vega_ui.store import SessionStore
from vega_ui.ui import create_ui_app


def _normalize_base_path(base_path: str) -> str:
    base = base_path.strip()
    if not base:
        return ""
    if not base.startswith("/"):
        base = f"/{base}"
    return base.rstrip("/")


def create_app(base_path: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    resolved_base_path = _normalize_base_path(
        os.getenv("VEGA_UI_BASE_PATH", "") if base_path is None else base_path
    )
    app = FastAPI(
        title="Vega-Altair WYSIWYG Editor",
        description="Stage A presentation editor for Vega-Lite / Altair charts",
        version="0.1.0",
        root_path=resolved_base_path,
    )

    # Shared session store for API and UI
    session_store = SessionStore()
    charts.store = session_store
    mutations.store = session_store
    export.store = session_store

    # JSON API
    app.include_router(charts.router)
    app.include_router(mutations.router)
    app.include_router(export.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Health endpoint for local verification."""
        return {"status": "ok"}

    # Server-rendered FastHTML UI
    app.mount("/", create_ui_app(session_store, base_path=resolved_base_path))

    return app


app = create_app()


def run() -> None:
    """CLI entry point: ``vega-ui``."""
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("VEGA_UI_RELOAD", "").lower() in {"1", "true", "yes", "on"}

    uvicorn.run("vega_ui.app:app", host=host, port=port, reload=reload_enabled)
