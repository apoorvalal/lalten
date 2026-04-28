"""Tests for chart session routes."""


def test_create_chart(client, bar_spec):
    resp = client.post("/api/charts", json={"spec": bar_spec})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "spec" in data
    assert "supported_objects" in data
    assert "chart" in data["supported_objects"]


def test_create_chart_invalid_spec(client):
    resp = client.post("/api/charts", json={"spec": {"bad": "spec"}})
    assert resp.status_code == 400


def test_get_chart(client, bar_spec):
    create_resp = client.post("/api/charts", json={"spec": bar_spec})
    session_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/charts/{session_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == session_id
    assert "spec" in data


def test_get_chart_not_found(client):
    resp = client.get("/api/charts/nonexistent")
    assert resp.status_code == 404


def test_create_multiple_sessions(client, bar_spec, line_spec):
    resp1 = client.post("/api/charts", json={"spec": bar_spec})
    resp2 = client.post("/api/charts", json={"spec": line_spec})
    assert resp1.json()["id"] != resp2.json()["id"]
