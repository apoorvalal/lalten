"""Tests for the validation module."""

import pytest

from vega_ui.engine.validation import is_supported_chart, validate_vegalite


def test_valid_bar_spec(bar_spec):
    errors = validate_vegalite(bar_spec)
    assert errors == []


def test_valid_line_spec(line_spec):
    errors = validate_vegalite(line_spec)
    assert errors == []


def test_valid_scatter_spec(scatter_spec):
    errors = validate_vegalite(scatter_spec)
    assert errors == []


def test_valid_histogram_spec(histogram_spec):
    errors = validate_vegalite(histogram_spec)
    assert errors == []


def test_invalid_spec_returns_errors():
    bad_spec = {"mark": "bar"}  # no data, no encoding
    errors = validate_vegalite(bad_spec)
    assert len(errors) > 0


def test_supported_bar(bar_spec):
    supported, reason = is_supported_chart(bar_spec)
    assert supported
    assert reason == ""


def test_supported_line(line_spec):
    supported, reason = is_supported_chart(line_spec)
    assert supported


def test_supported_scatter(scatter_spec):
    supported, reason = is_supported_chart(scatter_spec)
    assert supported


def test_unsupported_facet():
    spec = {"facet": {"field": "x"}, "spec": {"mark": "bar"}}
    supported, reason = is_supported_chart(spec)
    assert not supported
    assert "facet" in reason.lower() or "Composition" in reason


def test_unsupported_concat():
    spec = {"hconcat": [{"mark": "bar"}, {"mark": "line"}]}
    supported, reason = is_supported_chart(spec)
    assert not supported


def test_unsupported_no_mark():
    spec = {"encoding": {"x": {"field": "a"}}}
    supported, reason = is_supported_chart(spec)
    assert not supported
    assert "no mark" in reason.lower()
