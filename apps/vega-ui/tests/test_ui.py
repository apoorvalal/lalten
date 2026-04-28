"""Tests for the FastHTML UI."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from vega_ui.store import SessionStore
from vega_ui.ui import create_ui_app


def test_home_page_renders_loader(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Create Editing Session" in response.text
    assert "Paste Vega-Lite JSON" in response.text
    assert "htmx.js" not in response.text


def test_home_page_uses_base_path_in_actions() -> None:
    client = TestClient(create_ui_app(SessionStore(), base_path="/vega-ui"))

    response = client.get("/")

    assert response.status_code == 200
    assert 'action="/vega-ui/charts"' in response.text


def test_create_chart_from_ui_redirects_to_session_page(client, bar_spec) -> None:
    response = client.post(
        "/charts",
        data={"spec_text": json.dumps(bar_spec)},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/charts/")

    session_page = client.get(location)
    assert session_page.status_code == 200
    assert "Session" in session_page.text
    assert "Apply Chart Changes" in session_page.text


def test_ui_chart_form_updates_title(client, bar_spec) -> None:
    create_response = client.post(
        "/charts",
        data={"spec_text": json.dumps(bar_spec)},
        follow_redirects=False,
    )
    location = create_response.headers["location"]
    session_id = location.rsplit("/", maxsplit=1)[-1]

    update_response = client.post(
        f"/charts/{session_id}/chart",
        data={"title": "Server Rendered Title"},
        follow_redirects=False,
    )

    assert update_response.status_code == 303

    session_page = client.get(f"/charts/{session_id}")
    assert "Server Rendered Title" in session_page.text


def test_ui_mark_edit_still_works_after_annotation(client, bar_spec) -> None:
    create_response = client.post(
        "/charts",
        data={"spec_text": json.dumps(bar_spec)},
        follow_redirects=False,
    )
    session_id = create_response.headers["location"].rsplit("/", maxsplit=1)[-1]

    annotation_response = client.post(
        f"/charts/{session_id}/annotations",
        data={
            "text": "Threshold",
            "x_value": "A",
            "y_value": "50",
            "color": "black",
            "font_size": "14",
        },
        follow_redirects=False,
    )
    assert annotation_response.status_code == 303

    mark_response = client.post(
        f"/charts/{session_id}/mark",
        data={"color": "crimson"},
        follow_redirects=False,
    )
    assert mark_response.status_code == 303

    api_response = client.get(f"/api/charts/{session_id}")
    assert api_response.status_code == 200
    spec = api_response.json()["spec"]
    assert spec["layer"][0]["mark"]["color"] == "crimson"
    assert spec["layer"][1]["encoding"]["text"]["value"] == "Threshold"


def test_ui_mark_color_updates_constant_encoding_color(client) -> None:
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": [{"category": "A", "value": 28}]},
        "mark": "bar",
        "encoding": {
            "x": {"field": "category", "type": "nominal"},
            "y": {"field": "value", "type": "quantitative"},
            "color": {"value": "#4c78a8"},
        },
    }
    create_response = client.post(
        "/charts",
        data={"spec_text": json.dumps(spec)},
        follow_redirects=False,
    )
    session_id = create_response.headers["location"].rsplit("/", maxsplit=1)[-1]

    update_response = client.post(
        f"/charts/{session_id}/mark",
        data={"color": "#FFA500"},
        follow_redirects=False,
    )
    assert update_response.status_code == 303

    api_response = client.get(f"/api/charts/{session_id}")
    updated = api_response.json()["spec"]
    assert updated["encoding"]["color"]["value"] == "#FFA500"


def test_ui_mark_style_explains_field_driven_color(client, line_spec) -> None:
    create_response = client.post(
        "/charts",
        data={"spec_text": json.dumps(line_spec)},
        follow_redirects=False,
    )
    session_page = client.get(create_response.headers["location"])

    assert "encoding.color.field" in session_page.text
    assert "constant-color charts" in session_page.text
