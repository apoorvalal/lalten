"""Provenance metadata for tracking editor state across spec mutations."""

from __future__ import annotations

import copy
from typing import Any

EDITOR_META_KEY = "editor"
USERMETA_KEY = "usermeta"
EDITOR_VERSION = 1


def _build_object_ids(spec: dict[str, Any]) -> dict[str, str]:
    """Generate stable object IDs for editable elements in the spec."""
    ids: dict[str, str] = {}

    ids["chart"] = "chart"

    if "title" in spec:
        ids["title"] = "title"

    mark = spec.get("mark")
    if mark is not None:
        ids["mark"] = "mark"

    encoding = spec.get("encoding", {})
    for channel in ("x", "y", "x2", "y2", "color", "size", "shape", "opacity",
                     "detail", "text", "tooltip"):
        if channel in encoding:
            ids[f"encoding-{channel}"] = f"encoding-{channel}"
            ch_def = encoding[channel]
            if isinstance(ch_def, dict):
                if "axis" in ch_def or channel in ("x", "y", "x2", "y2"):
                    ids[f"axis-{channel}"] = f"axis-{channel}"
                if "legend" in ch_def or channel in ("color", "size", "shape", "opacity"):
                    ids[f"legend-{channel}"] = f"legend-{channel}"

    if "layer" in spec:
        for i, layer in enumerate(spec["layer"]):
            layer_meta = (
                layer.get(USERMETA_KEY, {})
                .get(EDITOR_META_KEY, {})
            )
            annotation_id = layer_meta.get("annotation_id")
            if annotation_id:
                ids[f"annotation-{annotation_id}"] = f"annotation-{annotation_id}"
            else:
                ids[f"layer-{i}"] = f"layer-{i}"

    return ids


def annotate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Add editor provenance metadata to a Vega-Lite spec.

    Adds a ``usermeta.editor`` block with version info and stable object IDs.
    Idempotent: re-annotating preserves existing annotation IDs.
    """
    spec = copy.deepcopy(spec)
    usermeta = spec.setdefault(USERMETA_KEY, {})
    editor = usermeta.setdefault(EDITOR_META_KEY, {})
    editor["version"] = EDITOR_VERSION
    editor["object_ids"] = _build_object_ids(spec)
    return spec


def strip_provenance(spec: dict[str, Any]) -> dict[str, Any]:
    """Return a clean Vega-Lite spec with editor metadata removed."""
    def _strip(node: Any) -> Any:
        if isinstance(node, list):
            return [_strip(item) for item in node]

        if isinstance(node, dict):
            cleaned: dict[str, Any] = {}
            for key, value in node.items():
                if key == USERMETA_KEY and isinstance(value, dict):
                    usermeta = {
                        nested_key: _strip(nested_value)
                        for nested_key, nested_value in value.items()
                        if nested_key != EDITOR_META_KEY
                    }
                    if usermeta:
                        cleaned[key] = usermeta
                    continue

                cleaned[key] = _strip(value)
            return cleaned

        return copy.deepcopy(node)

    return _strip(spec)


def get_object_ids(spec: dict[str, Any]) -> dict[str, str]:
    """Return the editor object IDs from a spec, or empty dict."""
    return (
        spec.get(USERMETA_KEY, {})
        .get(EDITOR_META_KEY, {})
        .get("object_ids", {})
    )
