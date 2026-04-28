"""Routes for applying mutations and undo."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from vega_ui.engine.mutation import (
    MutationError,
    add_annotation,
    apply_mutation,
    remove_annotation,
    update_annotation,
)
from vega_ui.engine.provenance import annotate_spec
from vega_ui.engine.validation import validate_vegalite
from vega_ui.models.mutation import (
    AnnotationAdd,
    AnnotationRemove,
    AnnotationUpdate,
    MutationBatch,
    MutationResult,
)
from vega_ui.store import NothingToUndoError, SessionNotFoundError, SessionStore

router = APIRouter(prefix="/api/charts", tags=["mutations"])

store: SessionStore | None = None


def get_store() -> SessionStore:
    if store is None:
        raise RuntimeError("Store not initialized")
    return store


@router.post("/{session_id}/mutate", response_model=MutationResult)
def mutate_chart(session_id: str, body: MutationBatch) -> MutationResult:
    """Apply a batch of mutations to a chart."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    current_spec = session.spec
    errors: list[str] = []

    for mut in body.mutations:
        try:
            current_spec = apply_mutation(current_spec, mut.target, mut.value)
        except MutationError as exc:
            errors.append(str(exc))
            return MutationResult(spec=session.spec, valid=False, errors=errors)

    # Re-annotate to update object IDs after mutation
    current_spec = annotate_spec(current_spec)

    # Validate the result
    validation_errors = validate_vegalite(current_spec)
    if validation_errors:
        return MutationResult(spec=session.spec, valid=False, errors=validation_errors)

    get_store().update_spec(session_id, current_spec)
    return MutationResult(spec=current_spec, valid=True, errors=[])


@router.post("/{session_id}/undo", response_model=MutationResult)
def undo_chart(session_id: str) -> MutationResult:
    """Undo the last mutation."""
    try:
        session = get_store().undo(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except NothingToUndoError:
        raise HTTPException(status_code=400, detail="Nothing to undo")

    return MutationResult(spec=session.spec, valid=True, errors=[])


@router.post("/{session_id}/annotations/add", response_model=MutationResult)
def add_annotation_route(session_id: str, body: AnnotationAdd) -> MutationResult:
    """Add a text annotation to the chart."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        new_spec, _ann_id = add_annotation(
            session.spec,
            text=body.text,
            x_value=body.x_value,
            y_value=body.y_value,
            color=body.color,
            font_size=body.font_size,
        )
    except MutationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    new_spec = annotate_spec(new_spec)
    get_store().update_spec(session_id, new_spec)
    return MutationResult(spec=new_spec, valid=True, errors=[])


@router.post("/{session_id}/annotations/update", response_model=MutationResult)
def update_annotation_route(session_id: str, body: AnnotationUpdate) -> MutationResult:
    """Update an existing annotation."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    updates = {}
    if body.text is not None:
        updates["text"] = body.text
    if body.color is not None:
        updates["color"] = body.color
    if body.font_size is not None:
        updates["fontSize"] = body.font_size
    if body.x_value is not None:
        updates["x_value"] = body.x_value
    if body.y_value is not None:
        updates["y_value"] = body.y_value

    try:
        new_spec = update_annotation(session.spec, body.annotation_id, **updates)
    except MutationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    new_spec = annotate_spec(new_spec)
    get_store().update_spec(session_id, new_spec)
    return MutationResult(spec=new_spec, valid=True, errors=[])


@router.post("/{session_id}/annotations/remove", response_model=MutationResult)
def remove_annotation_route(session_id: str, body: AnnotationRemove) -> MutationResult:
    """Remove an annotation from the chart."""
    try:
        session = get_store().get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        new_spec = remove_annotation(session.spec, body.annotation_id)
    except MutationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    new_spec = annotate_spec(new_spec)
    get_store().update_spec(session_id, new_spec)
    return MutationResult(spec=new_spec, valid=True, errors=[])
