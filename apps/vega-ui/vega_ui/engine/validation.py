"""Vega-Lite spec validation and Stage A support checks."""

from __future__ import annotations

from typing import Any

import altair as alt

SUPPORTED_MARKS = {"bar", "line", "point", "area", "text", "rule", "circle", "square", "tick", "rect"}

COMPOSITION_KEYS = {"facet", "repeat", "concat", "hconcat", "vconcat"}


def validate_vegalite(spec: dict[str, Any]) -> list[str]:
    """Validate a spec against Altair's built-in Vega-Lite schema validation.

    Returns a list of error strings (empty means valid).
    """
    from vega_ui.engine.provenance import strip_provenance

    clean = strip_provenance(spec)
    try:
        alt.Chart.from_dict(clean)
        return []
    except Exception as exc:
        return [str(exc)]


def _get_mark_type(spec: dict[str, Any]) -> str | None:
    """Extract the mark type string from a spec."""
    mark = spec.get("mark")
    if isinstance(mark, str):
        return mark
    if isinstance(mark, dict):
        return mark.get("type")
    return None


def is_supported_chart(spec: dict[str, Any]) -> tuple[bool, str]:
    """Check whether a spec falls within Stage A's supported subset.

    Returns (True, "") for supported charts or (False, reason) otherwise.
    """
    if any(k in spec for k in COMPOSITION_KEYS):
        return False, f"Composition charts ({', '.join(COMPOSITION_KEYS & spec.keys())}) are not supported in Stage A"

    if "layer" in spec:
        for layer in spec["layer"]:
            layer_editor = (
                layer.get("usermeta", {})
                .get("editor", {})
            )
            if not layer_editor.get("annotation_id"):
                # Allow layers but warn they have limited support
                pass
        return True, ""

    mark_type = _get_mark_type(spec)
    if mark_type and mark_type not in SUPPORTED_MARKS:
        return False, f"Mark type '{mark_type}' is not supported in Stage A"

    if mark_type is None and "layer" not in spec:
        return False, "Spec has no mark and is not a layered chart"

    return True, ""
