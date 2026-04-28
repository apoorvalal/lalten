"""Tests for mutation routes."""


def _create_session(client, spec):
    resp = client.post("/api/charts", json={"spec": spec})
    return resp.json()["id"]


def test_mutate_title(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.post(f"/api/charts/{sid}/mutate", json={
        "mutations": [{"target": "chart.title", "value": "New Title"}]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["spec"]["title"]["text"] == "New Title"


def test_mutate_multiple(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.post(f"/api/charts/{sid}/mutate", json={
        "mutations": [
            {"target": "chart.title", "value": "Title"},
            {"target": "chart.width", "value": 800},
            {"target": "mark.color", "value": "coral"},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["spec"]["width"] == 800


def test_mutate_invalid_target(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.post(f"/api/charts/{sid}/mutate", json={
        "mutations": [{"target": "fake.target", "value": "x"}]
    })
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_mutate_session_not_found(client):
    resp = client.post("/api/charts/bad-id/mutate", json={
        "mutations": [{"target": "chart.title", "value": "x"}]
    })
    assert resp.status_code == 404


def test_undo(client, bar_spec):
    sid = _create_session(client, bar_spec)

    # Apply a mutation
    client.post(f"/api/charts/{sid}/mutate", json={
        "mutations": [{"target": "chart.title", "value": "Changed"}]
    })

    # Verify it changed
    get_resp = client.get(f"/api/charts/{sid}")
    assert get_resp.json()["spec"]["title"]["text"] == "Changed"

    # Undo
    undo_resp = client.post(f"/api/charts/{sid}/undo")
    assert undo_resp.status_code == 200

    # Verify it reverted
    get_resp2 = client.get(f"/api/charts/{sid}")
    spec = get_resp2.json()["spec"]
    # Title should not be "Changed" anymore
    title = spec.get("title")
    if isinstance(title, dict):
        assert title.get("text") != "Changed"


def test_undo_empty_history(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.post(f"/api/charts/{sid}/undo")
    assert resp.status_code == 400


def test_add_annotation(client, bar_spec):
    sid = _create_session(client, bar_spec)
    resp = client.post(f"/api/charts/{sid}/annotations/add", json={
        "text": "Hello",
        "x_value": "A",
        "y_value": 50,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert "layer" in data["spec"]


def test_remove_annotation(client, bar_spec):
    sid = _create_session(client, bar_spec)

    # Add annotation
    add_resp = client.post(f"/api/charts/{sid}/annotations/add", json={
        "text": "Temp",
    })
    spec = add_resp.json()["spec"]

    # Find the annotation ID
    ann_id = None
    for layer in spec.get("layer", []):
        aid = layer.get("usermeta", {}).get("editor", {}).get("annotation_id")
        if aid:
            ann_id = aid
            break
    assert ann_id is not None

    # Remove it
    rem_resp = client.post(f"/api/charts/{sid}/annotations/remove", json={
        "annotation_id": ann_id,
    })
    assert rem_resp.status_code == 200
    assert rem_resp.json()["valid"] is True
