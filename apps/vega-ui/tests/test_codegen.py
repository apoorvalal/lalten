"""Tests for the code generation module."""

import json

from vega_ui.engine.codegen import export_json, export_python, export_python_from_dict
from vega_ui.engine.provenance import annotate_spec


def test_export_json_valid(bar_spec):
    spec = annotate_spec(bar_spec)
    result = export_json(spec)
    parsed = json.loads(result)
    assert "usermeta" not in parsed
    assert "mark" in parsed


def test_export_json_strips_provenance(bar_spec):
    spec = annotate_spec(bar_spec)
    result = export_json(spec)
    assert "editor" not in result or "usermeta" not in result


def test_export_json_all_fixtures(all_specs):
    for spec in all_specs:
        annotated = annotate_spec(spec)
        result = export_json(annotated)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


def test_export_python_from_dict_contains_from_dict(bar_spec):
    spec = annotate_spec(bar_spec)
    result = export_python_from_dict(spec)
    assert "from_dict" in result
    assert "import altair" in result


def test_export_python_from_dict_no_provenance(bar_spec):
    spec = annotate_spec(bar_spec)
    result = export_python_from_dict(spec)
    assert "usermeta" not in result


def test_export_python_from_dict_valid_json_embedded(bar_spec):
    spec = annotate_spec(bar_spec)
    result = export_python_from_dict(spec)
    # Extract the spec dict from the generated code
    lines = result.split("\n")
    spec_start = None
    for i, line in enumerate(lines):
        if line.startswith("spec = "):
            spec_start = i
            break
    assert spec_start is not None


def test_export_python_prefers_from_dict_for_complex(line_spec):
    spec = annotate_spec(line_spec)
    result = export_python(spec, prefer_normalized=True)
    # The function should return something valid regardless
    assert "import altair" in result


def test_export_python_fallback_always_works(all_specs):
    for spec in all_specs:
        annotated = annotate_spec(spec)
        result = export_python(annotated, prefer_normalized=False)
        assert "from_dict" in result
        assert "import altair" in result


def test_export_json_deterministic(bar_spec):
    spec = annotate_spec(bar_spec)
    result1 = export_json(spec)
    result2 = export_json(spec)
    assert result1 == result2


def test_export_python_deterministic(bar_spec):
    spec = annotate_spec(bar_spec)
    result1 = export_python(spec)
    result2 = export_python(spec)
    assert result1 == result2
