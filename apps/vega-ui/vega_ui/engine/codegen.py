"""Code generation: export edited specs as JSON or Python."""

from __future__ import annotations

import json
from typing import Any

from vega_ui.engine.provenance import strip_provenance


def export_json(spec: dict[str, Any], indent: int = 2) -> str:
    """Export a clean Vega-Lite spec as formatted JSON.

    Strips editor provenance metadata before serializing.
    """
    clean = strip_provenance(spec)
    return json.dumps(clean, indent=indent, ensure_ascii=False)


def export_python_from_dict(spec: dict[str, Any]) -> str:
    """Generate Python code that reconstructs the chart via ``from_dict``.

    This is the safe fallback that always works.
    """
    clean = strip_provenance(spec)
    spec_json = json.dumps(clean, indent=4, ensure_ascii=False)
    return f"""\
import altair as alt

spec = {spec_json}

chart = alt.Chart.from_dict(spec)
chart
"""


def _try_normalized_altair(spec: dict[str, Any]) -> str | None:
    """Attempt to generate idiomatic Altair code for simple single-view charts.

    Returns None if the spec is too complex for normalized output.
    """
    clean = strip_provenance(spec)

    # Only handle single-view specs with mark + encoding
    if "layer" in clean or "facet" in clean or "concat" in clean:
        return None

    mark = clean.get("mark")
    encoding = clean.get("encoding")
    if mark is None or encoding is None:
        return None

    # Extract mark info
    if isinstance(mark, str):
        mark_type = mark
        mark_kwargs: dict[str, Any] = {}
    elif isinstance(mark, dict):
        mark_type = mark.get("type", "point")
        mark_kwargs = {k: v for k, v in mark.items() if k != "type"}
    else:
        return None

    mark_method = f"mark_{mark_type}"

    # Build encoding arguments
    enc_parts: list[str] = []
    for channel, ch_def in encoding.items():
        if not isinstance(ch_def, dict):
            return None

        # Check for value encoding
        if "value" in ch_def:
            enc_parts.append(f"    {channel}=alt.value({ch_def['value']!r})")
            continue

        field = ch_def.get("field")
        field_type = ch_def.get("type")

        if field is None:
            # datum encoding or other non-field encoding
            return None

        shorthand_parts = [str(field)]
        type_map = {
            "quantitative": "Q",
            "nominal": "N",
            "ordinal": "O",
            "temporal": "T",
        }
        if field_type in type_map:
            shorthand_parts.append(type_map[field_type])

        shorthand = ":".join(shorthand_parts)
        channel_class = channel[0].upper() + channel[1:]

        # Collect extra kwargs for the channel constructor
        skip_keys = {"field", "type"}
        ch_kwargs: dict[str, Any] = {}
        for k, v in ch_def.items():
            if k not in skip_keys:
                ch_kwargs[k] = v

        if ch_kwargs:
            kwargs_str = ", ".join(f"{k}={v!r}" for k, v in ch_kwargs.items())
            enc_parts.append(f"    {channel}=alt.{channel_class}({shorthand!r}, {kwargs_str})")
        else:
            enc_parts.append(f"    {channel}={shorthand!r}")

    enc_block = ",\n".join(enc_parts)

    # Build mark kwargs
    if mark_kwargs:
        mark_kwargs_str = ", ".join(f"{k}={v!r}" for k, v in mark_kwargs.items())
        mark_call = f"{mark_method}({mark_kwargs_str})"
    else:
        mark_call = f"{mark_method}()"

    # Build chart properties
    props: list[str] = []
    if "title" in clean:
        title = clean["title"]
        if isinstance(title, str):
            props.append(f"    title={title!r}")
        elif isinstance(title, dict):
            props.append(f"    title={title!r}")
    if "width" in clean:
        props.append(f"    width={clean['width']!r}")
    if "height" in clean:
        props.append(f"    height={clean['height']!r}")

    lines = ["import altair as alt", "", "chart = ("]
    lines.append(f"    alt.Chart(data)")
    lines.append(f"    .{mark_call}")
    lines.append(f"    .encode(")
    lines.append(enc_block)
    lines.append(f"    )")
    if props:
        lines.append(f"    .properties(")
        lines.append(",\n".join(props))
        lines.append(f"    )")
    lines.append(")")
    lines.append("chart")

    return "\n".join(lines)


def export_python(spec: dict[str, Any], prefer_normalized: bool = True) -> str:
    """Export Python code for the chart.

    Attempts normalized Altair if ``prefer_normalized`` is True and the
    spec is simple enough. Otherwise falls back to ``from_dict``.
    """
    if prefer_normalized:
        normalized = _try_normalized_altair(spec)
        if normalized is not None:
            return normalized

    return export_python_from_dict(spec)
