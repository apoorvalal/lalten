"""Routes for chart session management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vega_ui.engine.ingestion import IngestionError, ingest_dict
from vega_ui.engine.provenance import get_object_ids
from vega_ui.models.chart import ChartIngest, ChartInfo
from vega_ui.store import SessionNotFoundError, SessionStore

router = APIRouter(prefix="/api/charts", tags=["charts"])

# Shared store instance — injected by app.py
store: SessionStore | None = None


def get_store() -> SessionStore:
    if store is None:
        raise RuntimeError("Store not initialized")
    return store


@router.post("", response_model=ChartInfo, status_code=201)
def create_chart(body: ChartIngest) -> ChartInfo:
    """Create a new chart editing session."""
    try:
        annotated = ingest_dict(body.spec)
    except IngestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    session = get_store().create(annotated)
    object_ids = get_object_ids(session.spec)
    return ChartInfo(
        id=session.id,
        spec=session.spec,
        supported_objects=list(object_ids.keys()),
    )


@router.get("/{session_id}", response_model=ChartInfo)
def get_chart(session_id: str) -> ChartInfo:
    """Get the current state of a chart session."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    object_ids = get_object_ids(session.spec)
    return ChartInfo(
        id=session.id,
        spec=session.spec,
        supported_objects=list(object_ids.keys()),
    )
