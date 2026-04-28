"""Pydantic models for chart sessions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChartIngest(BaseModel):
    """Request body for creating a chart session."""
    spec: dict[str, Any] = Field(..., description="Vega-Lite spec or Altair-compiled dict")


class ChartSession(BaseModel):
    """Represents an active editor session for a chart."""
    id: str
    spec: dict[str, Any]
    original_spec: dict[str, Any]
    history: list[dict[str, Any]] = Field(default_factory=list)


class ChartInfo(BaseModel):
    """Response model for chart session info."""
    id: str
    spec: dict[str, Any]
    supported_objects: list[str] = Field(default_factory=list)
