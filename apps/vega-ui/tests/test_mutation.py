"""Tests for the mutation engine."""

import pytest

from vega_ui.engine.mutation import (
    MutationError,
    add_annotation,
    apply_mutation,
    apply_mutations,
    get_nested,
    get_supported_targets,
    remove_annotation,
    set_nested,
    update_annotation,
)
from vega_ui.engine.provenance import annotate_spec


# ---------------------------------------------------------------------------
# Path helper tests
# ---------------------------------------------------------------------------

class TestGetNested:
    def test_simple_path(self):
        d = {"a": {"b": {"c": 42}}}
        assert get_nested(d, "a.b.c") == 42

    def test_missing_path(self):
        d = {"a": {"b": 1}}
        assert get_nested(d, "a.c.d") is None

    def test_default_value(self):
        d = {"a": 1}
        assert get_nested(d, "b", default="nope") == "nope"


class TestSetNested:
    def test_simple_set(self):
        d = {"a": {"b": 1}}
        set_nested(d, "a.b", 2)
        assert d["a"]["b"] == 2

    def test_creates_intermediate(self):
        d = {}
        set_nested(d, "a.b.c", 99)
        assert d["a"]["b"]["c"] == 99


# ---------------------------------------------------------------------------
# Chart-level mutations
# ---------------------------------------------------------------------------

class TestChartMutations:
    def test_set_title_from_string(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "chart.title", "My Chart")
        assert result["title"] == {"text": "My Chart"}

    def test_set_title_preserves_subtitle(self, bar_spec):
        spec = annotate_spec(bar_spec)
        spec["title"] = {"text": "Old", "subtitle": "Sub"}
        result = apply_mutation(spec, "chart.title", "New")
        assert result["title"]["text"] == "New"
        assert result["title"]["subtitle"] == "Sub"

    def test_set_subtitle_normalizes(self, bar_spec):
        spec = annotate_spec(bar_spec)
        spec["title"] = "Main Title"
        result = apply_mutation(spec, "chart.subtitle", "My Subtitle")
        assert result["title"]["subtitle"] == "My Subtitle"
        assert result["title"]["text"] == "Main Title"

    def test_set_width(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "chart.width", 600)
        assert result["width"] == 600

    def test_set_height(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "chart.height", 400)
        assert result["height"] == 400

    def test_set_background(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "chart.background", "#f0f0f0")
        assert result["background"] == "#f0f0f0"


# ---------------------------------------------------------------------------
# Mark mutations
# ---------------------------------------------------------------------------

class TestMarkMutations:
    def test_set_color_normalizes_mark(self, bar_spec):
        spec = annotate_spec(bar_spec)
        # The ingested spec may have mark as string or object
        result = apply_mutation(spec, "mark.color", "steelblue")
        assert isinstance(result["mark"], dict)
        assert result["mark"]["color"] == "steelblue"

    def test_set_opacity(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "mark.opacity", 0.7)
        assert result["mark"]["opacity"] == 0.7

    def test_set_stroke_width(self, line_spec):
        spec = annotate_spec(line_spec)
        result = apply_mutation(spec, "mark.strokeWidth", 3)
        assert result["mark"]["strokeWidth"] == 3

    def test_set_size(self, scatter_spec):
        spec = annotate_spec(scatter_spec)
        result = apply_mutation(spec, "mark.size", 100)
        assert result["mark"]["size"] == 100

    def test_set_color_updates_constant_encoding_color(self):
        spec = annotate_spec({
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": [{"x": "A", "y": 1}]},
            "mark": "bar",
            "encoding": {
                "x": {"field": "x", "type": "nominal"},
                "y": {"field": "y", "type": "quantitative"},
                "color": {"value": "#4c78a8"},
            },
        })

        result = apply_mutation(spec, "mark.color", "#FFA500")

        assert result["encoding"]["color"]["value"] == "#FFA500"
        assert result.get("mark") == "bar"

    def test_set_color_rejects_field_driven_color_encoding(self, line_spec):
        spec = annotate_spec(line_spec)

        with pytest.raises(MutationError, match="encoding.color.field"):
            apply_mutation(spec, "mark.color", "#FFA500")

    def test_set_color_on_layered_spec_updates_base_layer(self, bar_spec):
        spec = annotate_spec(bar_spec)
        layered, _ = add_annotation(spec, "Note", x_value="A", y_value=50)

        result = apply_mutation(layered, "mark.color", "crimson")

        assert result["layer"][0]["mark"]["color"] == "crimson"
        assert result["layer"][1]["encoding"]["text"]["value"] == "Note"


# ---------------------------------------------------------------------------
# Axis mutations
# ---------------------------------------------------------------------------

class TestAxisMutations:
    def test_set_x_axis_title(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "axis.x.title", "Categories")
        assert result["encoding"]["x"]["axis"]["title"] == "Categories"

    def test_set_y_axis_title(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "axis.y.title", "Values")
        assert result["encoding"]["y"]["axis"]["title"] == "Values"

    def test_set_label_font_size(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "axis.x.labelFontSize", 14)
        assert result["encoding"]["x"]["axis"]["labelFontSize"] == 14

    def test_set_grid_visibility(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "axis.y.grid", False)
        assert result["encoding"]["y"]["axis"]["grid"] is False

    def test_set_tick_visibility(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutation(spec, "axis.x.ticks", False)
        assert result["encoding"]["x"]["axis"]["ticks"] is False

    def test_axis_created_when_missing(self, bar_spec):
        spec = annotate_spec(bar_spec)
        # Ensure no axis exists
        spec["encoding"]["x"].pop("axis", None)
        result = apply_mutation(spec, "axis.x.title", "New Title")
        assert result["encoding"]["x"]["axis"]["title"] == "New Title"


# ---------------------------------------------------------------------------
# Legend mutations
# ---------------------------------------------------------------------------

class TestLegendMutations:
    def test_set_legend_title(self, line_spec):
        spec = annotate_spec(line_spec)
        result = apply_mutation(spec, "legend.color.title", "Region")
        assert result["encoding"]["color"]["legend"]["title"] == "Region"

    def test_set_legend_orient(self, line_spec):
        spec = annotate_spec(line_spec)
        result = apply_mutation(spec, "legend.color.orient", "bottom")
        assert result["encoding"]["color"]["legend"]["orient"] == "bottom"


# ---------------------------------------------------------------------------
# Batch mutations
# ---------------------------------------------------------------------------

class TestBatchMutations:
    def test_apply_multiple(self, bar_spec):
        spec = annotate_spec(bar_spec)
        result = apply_mutations(spec, [
            ("chart.title", "My Chart"),
            ("chart.width", 500),
            ("mark.color", "red"),
        ])
        assert result["title"]["text"] == "My Chart"
        assert result["width"] == 500
        assert result["mark"]["color"] == "red"

    def test_batch_fails_on_first_error(self, bar_spec):
        spec = annotate_spec(bar_spec)
        with pytest.raises(MutationError):
            apply_mutations(spec, [
                ("chart.title", "OK"),
                ("nonexistent.target", "fail"),
                ("chart.width", 500),
            ])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestMutationErrors:
    def test_unknown_target_raises(self, bar_spec):
        spec = annotate_spec(bar_spec)
        with pytest.raises(MutationError, match="Unknown mutation target"):
            apply_mutation(spec, "bogus.target", "value")

    def test_does_not_mutate_original(self, bar_spec):
        spec = annotate_spec(bar_spec)
        original_title = spec.get("title")
        apply_mutation(spec, "chart.title", "Changed")
        assert spec.get("title") == original_title


# ---------------------------------------------------------------------------
# Annotation tests
# ---------------------------------------------------------------------------

class TestAnnotations:
    def test_add_annotation(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, ann_id = add_annotation(spec, "Hello", x_value="A", y_value=50)
        assert "layer" in new_spec
        assert len(new_spec["layer"]) == 2
        assert ann_id

    def test_add_annotation_preserves_original(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, _ = add_annotation(spec, "Hello")
        # Original mark should be in layer[0]
        assert new_spec["layer"][0].get("mark") is not None

    def test_remove_annotation(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, ann_id = add_annotation(spec, "Remove me")
        restored = remove_annotation(new_spec, ann_id)
        # Should flatten back to single-view
        assert "layer" not in restored
        assert "mark" in restored

    def test_remove_nonexistent_raises(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, _ = add_annotation(spec, "Text")
        with pytest.raises(MutationError, match="not found"):
            remove_annotation(new_spec, "nonexistent-id")

    def test_update_annotation_text(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, ann_id = add_annotation(spec, "Original")
        updated = update_annotation(new_spec, ann_id, text="Updated")
        ann_layer = [
            l for l in updated["layer"]
            if l.get("usermeta", {}).get("editor", {}).get("annotation_id") == ann_id
        ][0]
        assert ann_layer["encoding"]["text"]["value"] == "Updated"

    def test_update_annotation_style(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, ann_id = add_annotation(spec, "Styled")
        updated = update_annotation(new_spec, ann_id, color="red", fontSize=20)
        ann_layer = [
            l for l in updated["layer"]
            if l.get("usermeta", {}).get("editor", {}).get("annotation_id") == ann_id
        ][0]
        assert ann_layer["mark"]["color"] == "red"
        assert ann_layer["mark"]["fontSize"] == 20

    def test_update_nonexistent_raises(self, bar_spec):
        spec = annotate_spec(bar_spec)
        new_spec, _ = add_annotation(spec, "Text")
        with pytest.raises(MutationError):
            update_annotation(new_spec, "bad-id", text="x")


# ---------------------------------------------------------------------------
# Supported targets
# ---------------------------------------------------------------------------

def test_supported_targets_not_empty():
    targets = get_supported_targets()
    assert len(targets) > 0
    assert "chart.title" in targets
    assert "mark.color" in targets
    assert "axis.x.title" in targets
