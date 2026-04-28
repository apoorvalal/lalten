"""Spec mutation engine: apply constrained edits to Vega-Lite specs."""

from __future__ import annotations

import copy
import uuid
from typing import Any


class MutationError(Exception):
    """Raised when a mutation cannot be applied."""


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_nested(d: dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from a nested dict using dot-separated path."""
    keys = path.split(".")
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is default:
            return default
    return current


def set_nested(d: dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dict using dot-separated path.

    Creates intermediate dicts as needed.
    """
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def delete_nested(d: dict[str, Any], path: str) -> bool:
    """Delete a key from a nested dict. Returns True if deleted."""
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    if isinstance(current, dict) and keys[-1] in current:
        del current[keys[-1]]
        return True
    return False


# ---------------------------------------------------------------------------
# Spec normalization helpers
# ---------------------------------------------------------------------------

def _normalize_title(spec: dict[str, Any]) -> None:
    """Ensure title is in object form ``{"text": ...}`` if present."""
    title = spec.get("title")
    if isinstance(title, str):
        spec["title"] = {"text": title}
    elif isinstance(title, list):
        spec["title"] = {"text": title}


def _normalize_mark(spec: dict[str, Any]) -> None:
    """Ensure mark is in object form ``{"type": ...}`` if present."""
    mark = spec.get("mark")
    if isinstance(mark, str):
        spec["mark"] = {"type": mark}


def _ensure_axis(spec: dict[str, Any], channel: str) -> dict[str, Any]:
    """Ensure encoding.<channel>.axis exists and return it."""
    encoding = spec.setdefault("encoding", {})
    ch = encoding.setdefault(channel, {})
    if not isinstance(ch, dict):
        raise MutationError(f"encoding.{channel} is not a dict")
    axis = ch.setdefault("axis", {})
    return axis


def _ensure_legend(spec: dict[str, Any], channel: str) -> dict[str, Any]:
    """Ensure encoding.<channel>.legend exists and return it."""
    encoding = spec.setdefault("encoding", {})
    ch = encoding.setdefault(channel, {})
    if not isinstance(ch, dict):
        raise MutationError(f"encoding.{channel} is not a dict")
    legend = ch.setdefault("legend", {})
    return legend


# ---------------------------------------------------------------------------
# Mutation target registry
# ---------------------------------------------------------------------------

# Each target maps to a callable(spec, value) that applies the mutation.
# This avoids a giant if/elif chain and makes the supported edits explicit.

def _set_chart_title(spec: dict, value: Any) -> None:
    _normalize_title(spec)
    if isinstance(spec.get("title"), dict):
        spec["title"]["text"] = value
    else:
        spec["title"] = {"text": value}


def _set_chart_subtitle(spec: dict, value: Any) -> None:
    _normalize_title(spec)
    if isinstance(spec.get("title"), dict):
        spec["title"]["subtitle"] = value
    else:
        spec["title"] = {"text": "", "subtitle": value}


def _make_chart_setter(field: str):
    def setter(spec: dict, value: Any) -> None:
        spec[field] = value
    return setter


def _make_mark_setter(field: str):
    def setter(spec: dict, value: Any) -> None:
        _normalize_mark(spec)
        mark = spec.get("mark")
        if isinstance(mark, dict):
            mark[field] = value
        else:
            raise MutationError("Spec has no mark to modify")
    return setter


def _set_mark_color(spec: dict, value: Any) -> None:
    encoding = spec.get("encoding", {})
    color_channel = encoding.get("color")
    if isinstance(color_channel, dict):
        if "field" in color_channel:
            raise MutationError(
                "Color is controlled by encoding.color.field. "
                "Direct mark color edits only support constant-color charts."
            )
        if "value" in color_channel:
            color_channel["value"] = value
            return

    _make_mark_setter("color")(spec, value)


def _make_axis_setter(channel: str, field: str):
    def setter(spec: dict, value: Any) -> None:
        axis = _ensure_axis(spec, channel)
        axis[field] = value
    return setter


def _make_legend_setter(channel: str, field: str):
    def setter(spec: dict, value: Any) -> None:
        legend = _ensure_legend(spec, channel)
        legend[field] = value
    return setter


# Build the mutation registry
_MUTATIONS: dict[str, Any] = {}

# Chart-level
_MUTATIONS["chart.title"] = _set_chart_title
_MUTATIONS["chart.subtitle"] = _set_chart_subtitle
for _field in ("width", "height", "background", "padding"):
    _MUTATIONS[f"chart.{_field}"] = _make_chart_setter(_field)

# Mark-level
_MUTATIONS["mark.color"] = _set_mark_color
for _field in ("fill", "stroke", "opacity", "strokeWidth", "size",
               "fillOpacity", "strokeOpacity"):
    _MUTATIONS[f"mark.{_field}"] = _make_mark_setter(_field)

# Axis-level (x and y)
for _ch in ("x", "y"):
    for _field in ("title", "labelFontSize", "titleFontSize", "ticks", "grid",
                   "format", "orient", "domain", "labels", "tickCount",
                   "labelAngle"):
        _MUTATIONS[f"axis.{_ch}.{_field}"] = _make_axis_setter(_ch, _field)

# Legend-level (color, size, shape, opacity)
for _ch in ("color", "size", "shape", "opacity"):
    for _field in ("title", "orient", "labelFontSize", "titleFontSize",
                   "symbolSize", "direction"):
        _MUTATIONS[f"legend.{_ch}.{_field}"] = _make_legend_setter(_ch, _field)


def get_supported_targets() -> list[str]:
    """Return all supported mutation target strings."""
    return sorted(_MUTATIONS.keys())


# ---------------------------------------------------------------------------
# Annotation support
# ---------------------------------------------------------------------------

def _ensure_layer_structure(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert a single-view spec into a layered spec if needed.

    Moves the original mark/encoding into layer[0] and returns the
    top-level spec that now has a ``layer`` list.
    """
    if "layer" in spec:
        return spec

    # Extract the chart content into the first layer
    layer_0: dict[str, Any] = {}
    move_keys = ["mark", "encoding", "transform", "selection", "params"]
    for key in move_keys:
        if key in spec:
            layer_0[key] = spec.pop(key)

    spec["layer"] = [layer_0]
    return spec


def add_annotation(
    spec: dict[str, Any],
    text: str,
    x_value: Any = None,
    y_value: Any = None,
    color: str = "black",
    font_size: int = 14,
) -> tuple[dict[str, Any], str]:
    """Add a text annotation layer to the spec.

    Returns (new_spec, annotation_id).
    """
    spec = copy.deepcopy(spec)
    spec = _ensure_layer_structure(spec)

    annotation_id = str(uuid.uuid4())[:8]

    annotation_layer: dict[str, Any] = {
        "mark": {
            "type": "text",
            "fontSize": font_size,
            "color": color,
        },
        "encoding": {},
        "usermeta": {
            "editor": {
                "annotation_id": annotation_id,
            }
        },
    }

    # Position the annotation
    if x_value is not None:
        annotation_layer["encoding"]["x"] = {"datum": x_value}
    if y_value is not None:
        annotation_layer["encoding"]["y"] = {"datum": y_value}

    annotation_layer["encoding"]["text"] = {"value": text}

    spec["layer"].append(annotation_layer)
    return spec, annotation_id


def remove_annotation(spec: dict[str, Any], annotation_id: str) -> dict[str, Any]:
    """Remove an annotation layer by its ID."""
    spec = copy.deepcopy(spec)
    if "layer" not in spec:
        raise MutationError("Spec has no layers")

    original_len = len(spec["layer"])
    spec["layer"] = [
        layer for layer in spec["layer"]
        if (
            layer.get("usermeta", {})
            .get("editor", {})
            .get("annotation_id")
        ) != annotation_id
    ]

    if len(spec["layer"]) == original_len:
        raise MutationError(f"Annotation '{annotation_id}' not found")

    # If only one layer remains and it's the original chart, flatten back
    if len(spec["layer"]) == 1:
        layer = spec["layer"][0]
        del spec["layer"]
        for key, val in layer.items():
            if key != "usermeta":
                spec[key] = val

    return spec


def update_annotation(
    spec: dict[str, Any],
    annotation_id: str,
    **updates: Any,
) -> dict[str, Any]:
    """Update properties of an annotation layer.

    Supported updates: text, color, fontSize, x_value, y_value.
    """
    spec = copy.deepcopy(spec)
    if "layer" not in spec:
        raise MutationError("Spec has no layers")

    for layer in spec["layer"]:
        layer_ann_id = (
            layer.get("usermeta", {})
            .get("editor", {})
            .get("annotation_id")
        )
        if layer_ann_id == annotation_id:
            mark = layer.get("mark", {})
            if isinstance(mark, str):
                mark = {"type": mark}
                layer["mark"] = mark

            if "text" in updates:
                layer.setdefault("encoding", {})["text"] = {"value": updates["text"]}
            if "color" in updates:
                mark["color"] = updates["color"]
            if "fontSize" in updates:
                mark["fontSize"] = updates["fontSize"]
            if "x_value" in updates:
                layer.setdefault("encoding", {})["x"] = {"datum": updates["x_value"]}
            if "y_value" in updates:
                layer.setdefault("encoding", {})["y"] = {"datum": updates["y_value"]}
            return spec

    raise MutationError(f"Annotation '{annotation_id}' not found")


# ---------------------------------------------------------------------------
# Main mutation entry point
# ---------------------------------------------------------------------------

def apply_mutation(
    spec: dict[str, Any],
    target: str,
    value: Any,
) -> dict[str, Any]:
    """Apply a single mutation to a Vega-Lite spec.

    Args:
        spec: The current Vega-Lite spec (will not be modified).
        target: A mutation target string (e.g. "chart.title", "axis.x.labelFontSize").
        value: The new value to set.

    Returns:
        A new spec dict with the mutation applied.

    Raises:
        MutationError: If the target is unknown or the mutation is invalid.
    """
    mutator = _MUTATIONS.get(target)
    if mutator is None:
        raise MutationError(
            f"Unknown mutation target: '{target}'. "
            f"Supported targets: {', '.join(get_supported_targets()[:10])}..."
        )

    new_spec = copy.deepcopy(spec)
    mutation_root = new_spec
    if (
        "layer" in new_spec
        and isinstance(new_spec["layer"], list)
        and new_spec["layer"]
        and target.startswith(("mark.", "axis.", "legend."))
    ):
        base_layer = new_spec["layer"][0]
        if not isinstance(base_layer, dict):
            raise MutationError("Layered spec is malformed")
        mutation_root = base_layer

    try:
        mutator(mutation_root, value)
    except MutationError:
        raise
    except Exception as exc:
        raise MutationError(f"Failed to apply mutation '{target}': {exc}") from exc

    return new_spec


def apply_mutations(
    spec: dict[str, Any],
    mutations: list[tuple[str, Any]],
) -> dict[str, Any]:
    """Apply a batch of mutations sequentially.

    Returns the final spec. Raises MutationError on first failure.
    """
    current = spec
    for target, value in mutations:
        current = apply_mutation(current, target, value)
    return current
