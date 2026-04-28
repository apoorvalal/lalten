"""Tests for export routes."""

import json


def _create_session(client, spec):
    resp = client.post("/api/charts", json={"spec": spec})
    return resp.json()["id"]


def test_export_json(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.get(f"/api/charts/{sid}/export/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "json"
    # Content should be valid JSON
    parsed = json.loads(data["content"])
    assert "mark" in parsed
    assert "usermeta" not in parsed


def test_export_python(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.get(f"/api/charts/{sid}/export/python")
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "python"
    assert "import altair" in data["content"]
    assert "from_dict" in data["content"] or "alt.Chart" in data["content"]


def test_export_after_mutation(client, bar_spec):
    sid = _create_session(client, bar_spec)

    # Mutate
    client.post(f"/api/charts/{sid}/mutate", json={
        "mutations": [{"target": "chart.title", "value": "Edited"}]
    })

    # Export JSON should reflect the mutation
    resp = client.get(f"/api/charts/{sid}/export/json")
    content = json.loads(resp.json()["content"])
    title = content.get("title")
    if isinstance(title, dict):
        assert title["text"] == "Edited"
    else:
        assert title == "Edited"


def test_export_session_not_found(client):
    resp = client.get("/api/charts/nonexistent/export/json")
    assert resp.status_code == 404
