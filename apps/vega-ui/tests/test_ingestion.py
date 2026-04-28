"""Tests for the ingestion module."""

import pytest

from vega_ui.engine.ingestion import IngestionError, ingest_dict
from vega_ui.engine.provenance import get_object_ids


def test_ingest_bar_spec(bar_spec):
    result = ingest_dict(bar_spec)
    assert "usermeta" in result
    ids = get_object_ids(result)
    assert "chart" in ids
    assert "mark" in ids


def test_ingest_preserves_data(bar_spec):
    result = ingest_dict(bar_spec)
    assert "data" in result


def test_ingest_all_fixtures(all_specs):
    for spec in all_specs:
        result = ingest_dict(spec)
        assert "usermeta" in result
        assert get_object_ids(result)


def test_ingest_invalid_spec_raises():
    with pytest.raises(IngestionError, match="Invalid"):
        ingest_dict({"not": "a valid spec"})


def test_ingest_unsupported_chart_raises():
    faceted = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "facet": {"field": "x", "type": "nominal"},
        "spec": {
            "mark": "bar",
            "encoding": {
                "x": {"field": "a", "type": "nominal"},
                "y": {"field": "b", "type": "quantitative"},
            },
        },
        "data": {"values": [{"x": "A", "a": "A", "b": 1}]},
    }
    with pytest.raises(IngestionError, match="[Uu]nsupported"):
        ingest_dict(faceted)
