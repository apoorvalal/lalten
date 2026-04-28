"""Pydantic models for mutation requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MutationRequest(BaseModel):
    """A single mutation to apply."""
    target: str = Field(..., description="Mutation target, e.g. 'chart.title', 'axis.x.labelFontSize'")
    value: Any = Field(..., description="New value for the target")


class MutationBatch(BaseModel):
    """Batch of mutations to apply atomically."""
    mutations: list[MutationRequest]


class AnnotationAdd(BaseModel):
    """Request to add a text annotation."""
    text: str
    x_value: Any = None
    y_value: Any = None
    color: str = "black"
    font_size: int = 14


class AnnotationUpdate(BaseModel):
    """Request to update an annotation."""
    annotation_id: str
    text: str | None = None
    x_value: Any = None
    y_value: Any = None
    color: str | None = None
    font_size: int | None = None


class AnnotationRemove(BaseModel):
    """Request to remove an annotation."""
    annotation_id: str


class MutationResult(BaseModel):
    """Response after applying mutations."""
    spec: dict[str, Any]
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ExportResponse(BaseModel):
    """Response for export endpoints."""
    format: Literal["json", "python"]
    content: str
