"""Ingest Altair charts or raw Vega-Lite dicts into annotated editor specs."""

from __future__ import annotations

from typing import Any

import altair as alt

from vega_ui.engine.provenance import annotate_spec
from vega_ui.engine.validation import is_supported_chart


class IngestionError(Exception):
    """Raised when a chart cannot be ingested."""


def ingest_dict(chart_dict: dict[str, Any]) -> dict[str, Any]:
    """Ingest a Vega-Lite spec dict (or Altair-compiled dict).

    Normalizes via Altair round-trip, annotates with provenance, and
    validates Stage A support.

    Returns the annotated Vega-Lite spec.
    Raises IngestionError if the chart is invalid or unsupported.
    """
    try:
        chart = alt.Chart.from_dict(chart_dict)
        normalized = chart.to_dict()
    except Exception as exc:
        raise IngestionError(f"Invalid Vega-Lite spec: {exc}") from exc

    supported, reason = is_supported_chart(normalized)
    if not supported:
        raise IngestionError(f"Unsupported chart: {reason}")

    return annotate_spec(normalized)


def ingest_altair(chart: alt.Chart) -> dict[str, Any]:
    """Ingest an Altair chart object.

    Compiles to Vega-Lite, annotates, and validates.
    """
    try:
        spec = chart.to_dict()
    except Exception as exc:
        raise IngestionError(f"Failed to compile Altair chart: {exc}") from exc

    supported, reason = is_supported_chart(spec)
    if not supported:
        raise IngestionError(f"Unsupported chart: {reason}")

    return annotate_spec(spec)
