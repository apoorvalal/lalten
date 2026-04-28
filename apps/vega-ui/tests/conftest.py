"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vega_ui.app import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def bar_spec() -> dict:
    return _load_fixture("bar_simple.json")


@pytest.fixture
def line_spec() -> dict:
    return _load_fixture("line_color.json")


@pytest.fixture
def scatter_spec() -> dict:
    return _load_fixture("scatter.json")


@pytest.fixture
def histogram_spec() -> dict:
    return _load_fixture("histogram_binned.json")


@pytest.fixture
def all_specs(bar_spec, line_spec, scatter_spec, histogram_spec) -> list[dict]:
    return [bar_spec, line_spec, scatter_spec, histogram_spec]


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)
