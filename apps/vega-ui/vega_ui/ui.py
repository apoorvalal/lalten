"""FastHTML user interface for Vega UI."""

from __future__ import annotations

import html
import json
from typing import Any

import vl_convert as vlc
from fasthtml.common import (
    A,
    Button,
    Code,
    Details,
    Div,
    Form,
    H1,
    H2,
    H3,
    H4,
    Input,
    Li,
    Main,
    Meta,
    NotStr,
    Option,
    P,
    Pre,
    Select,
    Style,
    Summary,
    Titled,
    Textarea,
    Ul,
    fast_app,
)
from starlette.responses import RedirectResponse

from vega_ui.engine.codegen import export_json, export_python
from vega_ui.engine.ingestion import IngestionError, ingest_dict
from vega_ui.engine.mutation import (
    MutationError,
    add_annotation,
    apply_mutations,
    get_supported_targets,
    remove_annotation,
)
from vega_ui.engine.provenance import get_object_ids, strip_provenance
from vega_ui.engine.validation import validate_vegalite
from vega_ui.store import NothingToUndoError, SessionNotFoundError, SessionStore

PAGE_CSS = """
:root {
  --bg: #f4f1ea;
  --panel: #fffdf8;
  --border: #d7d0c2;
  --ink: #1f2328;
  --muted: #5e6772;
  --accent: #0b5cab;
  --danger: #9f2d2d;
  --shadow: 0 16px 40px rgba(23, 31, 38, 0.08);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: linear-gradient(180deg, #f5f2ec 0%, #efede6 100%);
  font-family: "Iowan Old Style", "Palatino Linotype", serif;
}
.shell {
  width: min(1480px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 24px 0 40px;
}
.hero {
  margin-bottom: 20px;
  padding: 24px 28px;
  border: 1px solid var(--border);
  border-radius: 22px;
  background: linear-gradient(135deg, #fffaf0 0%, #f5f8fb 100%);
  box-shadow: var(--shadow);
}
.hero h1 {
  margin: 0 0 8px;
  font-size: 2.6rem;
}
.hero p {
  margin: 0;
  max-width: 72ch;
  color: var(--muted);
  line-height: 1.5;
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
.grid {
  display: grid;
  grid-template-columns: minmax(340px, 420px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.sidebar, .content {
  display: grid;
  gap: 18px;
}
.card {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--panel);
  box-shadow: 0 10px 28px rgba(23, 31, 38, 0.06);
}
.card h2, .card h3, .card h4 {
  margin: 0 0 12px;
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
.muted {
  color: var(--muted);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
.alert {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 14px;
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
.alert.error {
  color: var(--danger);
  background: #f8e2e2;
  border: 1px solid #e8bcbc;
}
.alert.success {
  color: #1f6f43;
  background: #e2f1e8;
  border: 1px solid #bdd8c7;
}
.field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}
.field label {
  color: var(--muted);
  font-size: 0.92rem;
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
input, textarea, select, button {
  font: inherit;
}
input, textarea, select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  color: var(--ink);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
textarea.code {
  min-height: 260px;
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.88rem;
  line-height: 1.45;
}
button, .button-link {
  display: inline-block;
  padding: 10px 14px;
  border: 1px solid #0b5cab;
  border-radius: 999px;
  background: #0b5cab;
  color: #fff;
  text-decoration: none;
  cursor: pointer;
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
.button-link.secondary, button.secondary {
  background: #fff;
  color: var(--ink);
  border-color: var(--border);
}
.button-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.preview {
  min-height: 320px;
  overflow: auto;
  padding: 10px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--border);
}
.preview svg {
  max-width: 100%;
  height: auto;
}
.pill-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 0;
  margin: 0;
  list-style: none;
}
.pill-list li {
  padding: 6px 10px;
  border-radius: 999px;
  background: #edf3fb;
  color: #1f3854;
  font-family: "Avenir Next", "Segoe UI", sans-serif;
  font-size: 0.9rem;
}
.annotation-list {
  padding-left: 18px;
}
.annotation-item {
  margin-bottom: 10px;
}
.inline-form {
  display: inline;
}
.topbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
}
details {
  margin-top: 14px;
}
summary {
  cursor: pointer;
  color: var(--accent);
  font-family: "Avenir Next", "Segoe UI", sans-serif;
}
@media (max-width: 1080px) {
  .grid { grid-template-columns: 1fr; }
}
"""

SAMPLE_SPEC: dict[str, Any] = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "data": {
        "values": [
            {"category": "A", "value": 28},
            {"category": "B", "value": 55},
            {"category": "C", "value": 43},
            {"category": "D", "value": 91},
            {"category": "E", "value": 81},
            {"category": "F", "value": 53},
        ]
    },
    "mark": "bar",
    "encoding": {
        "x": {"field": "category", "type": "nominal"},
        "y": {"field": "value", "type": "quantitative"},
        "color": {"value": "#4c78a8"},
    },
}


def create_ui_app(store: SessionStore, base_path: str = ""):
    """Create the FastHTML UI app mounted at the backend root."""
    app, rt = fast_app(
        title="Vega UI",
        hdrs=(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(PAGE_CSS),
        ),
        default_hdrs=False,
        htmx=False,
        surreal=False,
        pico=False,
        canonical=False,
    )

    def app_path(path: str) -> str:
        return _join_path(base_path, path)

    @app.get("/")
    def home():
        return _page(
            "Load Chart",
            Div(
                H1("Vega UI"),
                P(
                    "Server-rendered chart editing with FastHTML. Paste a Vega-Lite spec, "
                    "create a session, mutate it from Python-backed forms, and export the "
                    "result without running a separate JavaScript application.",
                ),
                cls="hero",
            ),
            _load_card(json.dumps(SAMPLE_SPEC, indent=2), app_path("/charts")),
        )

    @app.post("/charts")
    def create_chart(spec_text: str):
        try:
            parsed = json.loads(spec_text)
        except json.JSONDecodeError as exc:
            return _page(
                "Load Chart",
                Div(
                    H1("Vega UI"),
                    P("The supplied chart is not valid JSON.", cls="muted"),
                    cls="hero",
                ),
                _alert(f"Line {exc.lineno}, column {exc.colno}: {exc.msg}", "error"),
                _load_card(spec_text, app_path("/charts")),
            )

        try:
            annotated = ingest_dict(parsed)
        except IngestionError as exc:
            return _page(
                "Load Chart",
                Div(
                    H1("Vega UI"),
                    P(str(exc), cls="muted"),
                    cls="hero",
                ),
                _alert(str(exc), "error"),
                _load_card(spec_text, app_path("/charts")),
            )

        session = store.create(annotated)
        return RedirectResponse(app_path(f"/charts/{session.id}"), status_code=303)

    @app.get("/charts/{session_id}")
    def show_chart(session_id: str):
        try:
            session = store.get(session_id)
        except SessionNotFoundError:
            return _page("Session Not Found", _alert("Session not found.", "error"))
        return _chart_page(session_id, session.spec, len(session.history), base_path=base_path)

    @app.post("/charts/{session_id}/chart")
    def update_chart(
        session_id: str,
        title: str = "",
        subtitle: str = "",
        width: str = "",
        height: str = "",
        background: str = "",
    ):
        mutations: list[tuple[str, Any]] = []
        if title.strip():
            mutations.append(("chart.title", title.strip()))
        if subtitle.strip():
            mutations.append(("chart.subtitle", subtitle.strip()))
        if width.strip():
            mutations.append(("chart.width", _coerce_number(width, int)))
        if height.strip():
            mutations.append(("chart.height", _coerce_number(height, int)))
        if background.strip():
            mutations.append(("chart.background", background.strip()))
        return _apply_and_redirect(store, session_id, mutations, base_path=base_path)

    @app.post("/charts/{session_id}/mark")
    def update_mark(
        session_id: str,
        color: str = "",
        stroke: str = "",
        opacity: str = "",
        stroke_width: str = "",
        size: str = "",
    ):
        mutations: list[tuple[str, Any]] = []
        if color.strip():
            mutations.append(("mark.color", color.strip()))
        if stroke.strip():
            mutations.append(("mark.stroke", stroke.strip()))
        if opacity.strip():
            mutations.append(("mark.opacity", _coerce_number(opacity, float)))
        if stroke_width.strip():
            mutations.append(("mark.strokeWidth", _coerce_number(stroke_width, float)))
        if size.strip():
            mutations.append(("mark.size", _coerce_number(size, float)))
        return _apply_and_redirect(store, session_id, mutations, base_path=base_path)

    @app.post("/charts/{session_id}/axes")
    def update_axes(
        session_id: str,
        x_title: str = "",
        y_title: str = "",
        x_label_size: str = "",
        y_label_size: str = "",
    ):
        mutations: list[tuple[str, Any]] = []
        if x_title.strip():
            mutations.append(("axis.x.title", x_title.strip()))
        if y_title.strip():
            mutations.append(("axis.y.title", y_title.strip()))
        if x_label_size.strip():
            mutations.append(("axis.x.labelFontSize", _coerce_number(x_label_size, int)))
        if y_label_size.strip():
            mutations.append(("axis.y.labelFontSize", _coerce_number(y_label_size, int)))
        return _apply_and_redirect(store, session_id, mutations, base_path=base_path)

    @app.post("/charts/{session_id}/custom")
    def custom_mutation(session_id: str, target: str, value: str):
        try:
            parsed = _coerce_jsonish(value)
        except ValueError as exc:
            return _error_chart_page(store, session_id, str(exc), base_path=base_path)
        return _apply_and_redirect(store, session_id, [(target, parsed)], base_path=base_path)

    @app.post("/charts/{session_id}/annotations")
    def create_annotation(
        session_id: str,
        text: str,
        x_value: str = "",
        y_value: str = "",
        color: str = "black",
        font_size: str = "14",
    ):
        try:
            session = store.get(session_id)
        except SessionNotFoundError:
            return _page("Session Not Found", _alert("Session not found.", "error"))

        try:
            new_spec, _annotation_id = add_annotation(
                session.spec,
                text=text,
                x_value=_coerce_optional_jsonish(x_value),
                y_value=_coerce_optional_jsonish(y_value),
                color=color or "black",
                font_size=_coerce_number(font_size, int),
            )
            _update_session_spec(store, session_id, new_spec)
        except (MutationError, ValueError) as exc:
            return _error_chart_page(store, session_id, str(exc), base_path=base_path)

        return RedirectResponse(app_path(f"/charts/{session_id}"), status_code=303)

    @app.post("/charts/{session_id}/annotations/remove")
    def delete_annotation(session_id: str, annotation_id: str):
        try:
            session = store.get(session_id)
        except SessionNotFoundError:
            return _page("Session Not Found", _alert("Session not found.", "error"))

        try:
            new_spec = remove_annotation(session.spec, annotation_id)
            _update_session_spec(store, session_id, new_spec)
        except MutationError as exc:
            return _error_chart_page(store, session_id, str(exc), base_path=base_path)

        return RedirectResponse(app_path(f"/charts/{session_id}"), status_code=303)

    @app.post("/charts/{session_id}/undo")
    def undo(session_id: str):
        try:
            store.undo(session_id)
        except SessionNotFoundError:
            return _page("Session Not Found", _alert("Session not found.", "error"))
        except NothingToUndoError as exc:
            return _error_chart_page(store, session_id, str(exc), base_path=base_path)
        return RedirectResponse(app_path(f"/charts/{session_id}"), status_code=303)

    return app


def _page(title: str, *content):
    return Titled(title, Main(*content, cls="shell"))


def _alert(message: str, tone: str):
    return Div(message, cls=f"alert {tone}")


def _card(title: str, *content):
    return Div(H2(title), *content, cls="card")


def _field(label: str, control):
    return Div(Div(label, cls="muted"), control, cls="field")


def _load_card(spec_text: str, action_path: str):
    return _card(
        "Load Vega-Lite Spec",
        Form(
            _field(
                "Paste Vega-Lite JSON",
                Textarea(spec_text, name="spec_text", rows=18, cls="code"),
            ),
            Button("Create Editing Session", type="submit"),
            method="post",
            action=action_path,
        ),
    )


def _chart_page(
    session_id: str,
    spec: dict[str, Any],
    history_len: int,
    error: str | None = None,
    base_path: str = "",
):
    def app_path(path: str) -> str:
        return _join_path(base_path, path)

    chart_view = _base_view(spec)
    title_text, subtitle_text = _title_parts(spec)
    mark = _mark_dict(chart_view)
    color_control = _mark_color_control(chart_view)
    x_axis = _axis_dict(chart_view, "x")
    y_axis = _axis_dict(chart_view, "y")
    supported_objects = sorted(get_object_ids(spec).keys())
    export_json_text = export_json(spec)
    export_python_text = export_python(spec)
    annotations = _annotation_rows(spec)

    content = [
        Div(
            Div(
                H1("Vega UI"),
                P(
                    f"Session {session_id}. All edits are server-side and use the current "
                    f"Python mutation engine.",
                ),
            ),
            Div(
                A("Back To Loader", href=app_path("/"), cls="button-link secondary"),
                A(
                    "Export JSON API",
                    href=app_path(f"/api/charts/{session_id}/export/json"),
                    cls="button-link secondary",
                ),
                A(
                    "Export Python API",
                    href=app_path(f"/api/charts/{session_id}/export/python"),
                    cls="button-link secondary",
                ),
                cls="button-row",
            ),
            cls="hero topbar",
        ),
    ]
    if error:
        content.append(_alert(error, "error"))

    content.append(
        Div(
            Div(
                _card(
                    "Session",
                    P(f"History depth: {history_len}", cls="muted"),
                    P(f"Supported objects: {len(supported_objects)}", cls="muted"),
                    Ul(*(Li(Code(item)) for item in supported_objects), cls="pill-list"),
                ),
                _card(
                    "Chart Settings",
                    Form(
                        _field("Title", Input(name="title", value=title_text)),
                        _field("Subtitle", Input(name="subtitle", value=subtitle_text)),
                        _field("Width", Input(name="width", type="number", value=spec.get("width", ""))),
                        _field("Height", Input(name="height", type="number", value=spec.get("height", ""))),
                        _field("Background", Input(name="background", value=spec.get("background", ""))),
                        Button("Apply Chart Changes", type="submit"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/chart"),
                    ),
                ),
                _card(
                    "Mark Style",
                    Form(
                        _field(
                            "Color",
                            Input(
                                name="color",
                                value=color_control["value"],
                                readonly=color_control["readonly"],
                            ),
                        ),
                        P(color_control["note"], cls="muted") if color_control["note"] else "",
                        _field("Stroke", Input(name="stroke", value=mark.get("stroke", ""))),
                        _field("Opacity", Input(name="opacity", value=mark.get("opacity", ""))),
                        _field(
                            "Stroke Width",
                            Input(name="stroke_width", value=mark.get("strokeWidth", "")),
                        ),
                        _field("Size", Input(name="size", value=mark.get("size", ""))),
                        Button("Apply Mark Changes", type="submit"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/mark"),
                    ),
                ),
                _card(
                    "Axes",
                    Form(
                        _field("X Axis Title", Input(name="x_title", value=x_axis.get("title", ""))),
                        _field("Y Axis Title", Input(name="y_title", value=y_axis.get("title", ""))),
                        _field(
                            "X Label Font Size",
                            Input(name="x_label_size", value=x_axis.get("labelFontSize", "")),
                        ),
                        _field(
                            "Y Label Font Size",
                            Input(name="y_label_size", value=y_axis.get("labelFontSize", "")),
                        ),
                        Button("Apply Axis Changes", type="submit"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/axes"),
                    ),
                ),
                _card(
                    "Annotations",
                    Form(
                        _field("Text", Input(name="text")),
                        _field("X Value", Input(name="x_value")),
                        _field("Y Value", Input(name="y_value")),
                        _field("Color", Input(name="color", value="black")),
                        _field("Font Size", Input(name="font_size", type="number", value="14")),
                        Button("Add Annotation", type="submit"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/annotations"),
                    ),
                    H4("Existing Annotations"),
                    _annotation_list(session_id, annotations, base_path=base_path),
                ),
                _card(
                    "Undo",
                    Form(
                        Button("Undo Last Change", type="submit", cls="secondary"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/undo"),
                    ),
                ),
                cls="sidebar",
            ),
            Div(
                _card("Preview", Div(NotStr(_render_svg(spec)), cls="preview")),
                _card(
                    "Custom Mutation",
                    Form(
                        _field(
                            "Target",
                            Select(
                                *(Option(target, value=target) for target in get_supported_targets()),
                                name="target",
                            ),
                        ),
                        _field(
                            "Value",
                            Input(
                                name="value",
                                placeholder='JSON value or plain string, e.g. "Title", 800, false',
                            ),
                        ),
                        Button("Apply Custom Mutation", type="submit"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/custom"),
                    ),
                ),
                _card(
                    "Exports",
                    Details(
                        Summary("Show JSON"),
                        Textarea(export_json_text, readonly=True, rows=16, cls="code"),
                        open=True,
                    ),
                    Details(
                        Summary("Show Python"),
                        Textarea(export_python_text, readonly=True, rows=18, cls="code"),
                    ),
                    Details(
                        Summary("Show Current Spec"),
                        Textarea(json.dumps(spec, indent=2), readonly=True, rows=18, cls="code"),
                    ),
                ),
                cls="content",
            ),
            cls="grid",
        )
    )
    return _page("Vega UI", *content)


def _annotation_list(session_id: str, annotations: list[dict[str, Any]], base_path: str = ""):
    def app_path(path: str) -> str:
        return _join_path(base_path, path)

    if not annotations:
        return P("No annotations yet.", cls="muted")
    return Ul(
        *[
            Li(
                Div(
                    Div(
                        f"{item['annotation_id']}: {item['text']}",
                        cls="muted",
                    ),
                    Form(
                        Input(type="hidden", name="annotation_id", value=item["annotation_id"]),
                        Button("Remove", type="submit", cls="secondary"),
                        method="post",
                        action=app_path(f"/charts/{session_id}/annotations/remove"),
                        cls="inline-form",
                    ),
                    cls="annotation-item",
                )
            )
            for item in annotations
        ],
        cls="annotation-list",
    )


def _annotation_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for layer in spec.get("layer", []):
        editor = layer.get("usermeta", {}).get("editor", {})
        annotation_id = editor.get("annotation_id")
        if not annotation_id:
            continue
        text = layer.get("encoding", {}).get("text", {}).get("value", "")
        rows.append({"annotation_id": annotation_id, "text": text})
    return rows


def _render_svg(spec: dict[str, Any]) -> str:
    try:
        return vlc.vegalite_to_svg(strip_provenance(spec))
    except Exception as exc:  # pragma: no cover - defensive rendering fallback
        message = html.escape(str(exc))
        return (
            "<pre>"
            "Preview rendering failed.\n"
            f"{message}"
            "</pre>"
        )


def _title_parts(spec: dict[str, Any]) -> tuple[str, str]:
    title = spec.get("title")
    if isinstance(title, str):
        return title, ""
    if isinstance(title, dict):
        subtitle = title.get("subtitle", "")
        if isinstance(subtitle, list):
            subtitle = " ".join(str(item) for item in subtitle)
        return str(title.get("text", "")), str(subtitle)
    return "", ""


def _base_view(spec: dict[str, Any]) -> dict[str, Any]:
    if "layer" in spec and isinstance(spec["layer"], list) and spec["layer"]:
        base = spec["layer"][0]
        if isinstance(base, dict):
            return base
    return spec


def _mark_dict(spec: dict[str, Any]) -> dict[str, Any]:
    mark = spec.get("mark", {})
    if isinstance(mark, str):
        return {"type": mark}
    if isinstance(mark, dict):
        return mark
    return {}


def _mark_color_control(spec: dict[str, Any]) -> dict[str, Any]:
    mark = _mark_dict(spec)
    encoding = spec.get("encoding", {})
    color_channel = encoding.get("color")

    if isinstance(color_channel, dict):
        if "field" in color_channel:
            field_name = color_channel.get("field", "unknown")
            return {
                "value": "",
                "readonly": True,
                "note": (
                    f"Color is driven by encoding.color.field ({field_name}). "
                    "This control only edits constant-color charts."
                ),
            }
        if "value" in color_channel:
            return {
                "value": str(color_channel["value"]),
                "readonly": False,
                "note": "This chart uses encoding.color.value, so color edits update that constant color channel.",
            }

    return {
        "value": mark.get("color", ""),
        "readonly": False,
        "note": None,
    }


def _axis_dict(spec: dict[str, Any], channel: str) -> dict[str, Any]:
    encoding = spec.get("encoding", {})
    channel_def = encoding.get(channel, {})
    if isinstance(channel_def, dict):
        axis = channel_def.get("axis", {})
        if isinstance(axis, dict):
            return axis
    return {}


def _apply_and_redirect(
    store: SessionStore,
    session_id: str,
    mutations: list[tuple[str, Any]],
    base_path: str = "",
):
    if not mutations:
        return RedirectResponse(_join_path(base_path, f"/charts/{session_id}"), status_code=303)
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        return _page("Session Not Found", _alert("Session not found.", "error"))

    try:
        new_spec = apply_mutations(session.spec, mutations)
        _update_session_spec(store, session_id, new_spec)
    except (MutationError, ValueError) as exc:
        return _error_chart_page(store, session_id, str(exc), base_path=base_path)

    return RedirectResponse(_join_path(base_path, f"/charts/{session_id}"), status_code=303)


def _update_session_spec(store: SessionStore, session_id: str, spec: dict[str, Any]) -> None:
    errors = validate_vegalite(spec)
    if errors:
        raise MutationError("; ".join(errors))
    from vega_ui.engine.provenance import annotate_spec

    store.update_spec(session_id, annotate_spec(spec))


def _error_chart_page(store: SessionStore, session_id: str, message: str, base_path: str = ""):
    try:
        session = store.get(session_id)
    except SessionNotFoundError:
        return _page("Session Not Found", _alert("Session not found.", "error"))
    return _chart_page(session_id, session.spec, len(session.history), error=message, base_path=base_path)


def _coerce_number(value: str, typ):
    if typ is int:
        return int(float(value))
    return float(value)


def _coerce_jsonish(value: str) -> Any:
    text = value.strip()
    if not text:
        raise ValueError("Mutation value cannot be empty.")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _coerce_optional_jsonish(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    return _coerce_jsonish(text)


def _join_path(base_path: str, path: str) -> str:
    if not base_path:
        return path
    if path == "/":
        return base_path or "/"
    return f"{base_path}{path}"
