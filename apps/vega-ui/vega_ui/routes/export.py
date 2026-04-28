"""Routes for exporting charts as JSON or Python."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vega_ui.engine.codegen import export_json, export_python
from vega_ui.models.mutation import ExportResponse
from vega_ui.store import SessionNotFoundError, SessionStore

router = APIRouter(prefix="/api/charts", tags=["export"])

store: SessionStore | None = None


def get_store() -> SessionStore:
    if store is None:
        raise RuntimeError("Store not initialized")
    return store


@router.get("/{session_id}/export/json", response_model=ExportResponse)
def export_chart_json(session_id: str) -> ExportResponse:
    """Export the chart as Vega-Lite JSON."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    content = export_json(session.spec)
    return ExportResponse(format="json", content=content)


@router.get("/{session_id}/export/python", response_model=ExportResponse)
def export_chart_python(session_id: str) -> ExportResponse:
    """Export the chart as Python code."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    content = export_python(session.spec)
    return ExportResponse(format="python", content=content)
