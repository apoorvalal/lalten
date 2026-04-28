# Vega/Altair WYSIWYG Editor Spec

## 1. Goal

Build a WYSIWYG editor for Vega-Lite / Altair charts in two stages:

- **Stage A:** a practical visual editor for cosmetic and presentation-layer edits.
- **Stage B:** a semantic chart editor that supports controlled edits to encodings and chart structure.

The product should treat the **Vega-Lite spec as the editable intermediate representation** and support a disciplined round-trip back into Python.

The primary target user is a Python user working with Altair. The system does **not** need to recover the user’s original handwritten Altair source exactly. It only needs to return:

1. a valid edited Vega-Lite spec,
2. a valid Altair representation when feasible,
3. a robust fallback via `alt.Chart.from_dict(spec)` when decompilation is ambiguous.

---

## 2. Product Thesis

Vega-Lite is declarative enough that many visually meaningful plot edits can be implemented as edits to a JSON spec rather than by inferring intent from pixels.

Therefore the right architecture is:

- render the chart from a Vega-Lite spec,
- map visual selections back to spec nodes,
- mutate the spec through a constrained object model,
- preserve provenance where possible,
- regenerate Python in a normalized form when possible.

This is **not** a general graphics editor and should not attempt Figma-like arbitrary manipulation of arbitrary SVG fragments. The editor should expose only edits that have a clear and stable mapping to the Vega-Lite schema.

---

## 3. Non-goals

The following are explicitly out of scope for Stage A and mostly out of scope for Stage B unless separately prioritized:

- exact recovery of the user’s original Python source,
- round-tripping arbitrary notebook control flow or helper functions,
- arbitrary freeform shape drawing,
- pixel-perfect editing of raw SVG/canvas output,
- support for all Vega features on day one,
- automatic inference of complex user intent from ambiguous clicks,
- arbitrary data editing through direct manipulation,
- full parity with every Altair/Vega-Lite composition or transform primitive.

---

## 4. User stories

### Stage A user stories

1. As a Python user, I want to open an Altair chart in a visual editor and change titles, axis labels, legend text, colors, fonts, and annotation text without touching code.
2. As a user, I want to click or double-click visual elements and get a property panel scoped to the selected object.
3. As a user, I want to export the edited chart as Vega-Lite JSON.
4. As a Python user, I want the system to produce a valid Python representation of the edited chart, even if it falls back to `from_dict`.
5. As a user, I want edits to remain stable when the chart rerenders.

### Stage B user stories

1. As a Python user, I want to swap fields across channels, change mark types, and modify aggregate/bin/sort/filter settings visually.
2. As a user, I want to add and edit reference lines, text annotations, and simple layers through the editor.
3. As a user, I want the editor to distinguish presentation edits from semantic edits and expose the consequences clearly.
4. As a Python user, I want the regenerated Altair code to be normalized and readable for supported constructs.

---

## 5. System principles

1. **Spec-first:** Vega-Lite JSON is the canonical editable representation.
2. **Constrained manipulation:** every supported visual action must map to a well-defined spec mutation.
3. **Stable provenance:** spec nodes should carry stable IDs and provenance metadata when originating from Altair.
4. **Deterministic output:** the same edited spec should always regenerate the same normalized Python.
5. **Graceful fallback:** when decompilation is ambiguous, return valid `from_dict` code rather than attempt heroic reconstruction.
6. **No fake magic:** if multiple interpretations of an edit exist, surface a controlled choice rather than silently guessing.

---

## 6. Core architecture

## 6.1 Components

### Frontend editor

Responsibilities:

- render Vega-Lite charts,
- maintain editable chart state,
- support object selection,
- expose property panels,
- apply direct-manipulation edits for supported elements,
- serialize edits as spec mutations.

Likely implementation:

- `vega-embed` for rendering,
- editor-side selection state,
- schema-aware mutation layer,
- optional scenegraph inspection for hit-testing.

### Spec mutation engine

Responsibilities:

- accept high-level edit actions,
- resolve target spec path(s),
- validate edits against supported schema patterns,
- normalize output spec,
- preserve stable IDs and provenance metadata.

### Python bridge

Responsibilities:

- ingest Altair charts and compile them into editable Vega-Lite,
- attach provenance metadata,
- accept edited specs,
- attempt decompilation to normalized Altair code,
- fall back to `Chart.from_dict` when needed.

### Optional provenance layer

Responsibilities:

- attach stable node IDs,
- store original field shorthands,
- preserve information lost in plain Vega-Lite compilation,
- enable cleaner reverse mapping.

---

## 6.2 Data flow

### Inbound flow

1. User creates chart in Altair.
2. Python bridge compiles Altair to Vega-Lite spec.
3. System attaches provenance metadata and stable IDs.
4. Frontend receives editable spec.
5. Frontend renders chart and initializes selection model.

### Editing flow

1. User selects a visual object or structural node.
2. Frontend maps the selection to a logical object type and target spec node.
3. User changes properties in property panel or inline editor.
4. Mutation engine updates the spec.
5. Chart rerenders.
6. Edit history records the action.

### Outbound flow

1. User exports edited chart.
2. System emits edited Vega-Lite JSON.
3. Python bridge attempts normalized Altair regeneration.
4. If regeneration fails or is ambiguous, system emits `alt.Chart.from_dict(spec)`.

---

## 7. Object model

The editor should not expose raw JSON first. It should expose a controlled object model over common editable entities.

Supported object classes:

- chart
- title
- subtitle
- mark style
- x axis
- y axis
- legend
- encoding channel
- scale
- annotation text
- reference line / rule
- layer

Each object should define:

- how it is selected,
- what properties are editable,
- what spec paths it controls,
- whether edits are cosmetic or semantic,
- what ambiguities must be surfaced.

Example:

### Axis object

Editable fields:

- title
- label font size
- title font size
- tick visibility
- grid visibility
- orient
- format
- domain visibility

Likely target path:

- `encoding.x.axis.*` or `encoding.y.axis.*`

### Annotation text object

Editable fields:

- text
- x / y anchor
- font size
- color
- alignment

Likely representation:

- a dedicated text layer with stable annotation ID

---

## 8. Stage A scope

Stage A is a presentation-layer editor.

### 8.1 Supported chart families

Initial support:

- single-view charts,
- common mark types: bar, line, point, area, text, rule,
- simple layered charts only when layers are editor-created annotations.

Deferred from Stage A:

- arbitrary multi-layer charts authored externally,
- facet/repeat/concat,
- complex transform editing,
- selection-driven interactivity editing,
- deeply nested compositions.

### 8.2 Supported edits

#### Chart-level

- chart title
- chart subtitle
- chart width / height
- background
- padding where straightforward

#### Axis-level

- axis title text
- label font size
- title font size
- tick visibility
- grid visibility
- axis format string

#### Legend-level

- legend title
- orient / placement where supported
- font sizes
- symbol sizing where straightforward

#### Mark styling

- fill / stroke color when statically settable
- opacity
- stroke width
- point size
- line width

#### Text styling

- text color
- text size
- font weight for titles / annotations

#### Annotations

- add text annotation
- edit text annotation contents
- move annotation through simple controls or drag handles if easy
- add rule/reference line with label

### 8.3 Stage A exclusions

- remapping data fields
- changing aggregation/binning
- changing sort/group semantics
- changing transform pipelines
- arbitrary drag-to-edit underlying data values
- editing externally authored complex layered specs beyond recognized safe patterns

### 8.4 Stage A UX model

Selection model:

- click selects object
- double-click opens inline editing where natural, especially text
- right sidebar shows scoped property panel

Preferred interaction style:

- mixed direct manipulation plus property editing,
- property editing is primary,
- direct manipulation is limited to intuitive cases like annotation position.

### 8.5 Stage A output contract

The system must always emit:

- edited Vega-Lite spec,
- valid JSON serialization,
- valid Python snippet using `alt.Chart.from_dict(spec)`.

Stretch output:

- normalized Altair code for simple supported cases.

### 8.6 Stage A success criteria

Functional:

- user can edit titles, labels, legends, colors, and annotations on supported charts without touching raw JSON,
- rendered chart updates correctly after each supported edit,
- edited spec remains valid Vega-Lite,
- export to JSON and Python works reliably.

Product:

- common cosmetic edits take fewer steps than editing code manually,
- users understand what object is selected,
- failure cases degrade clearly rather than corrupting the spec.

---

## 9. Stage B scope

Stage B introduces controlled semantic editing.

### 9.1 Supported semantic edits

#### Encodings

- assign field to x / y / color / size / shape / detail when schema-compatible
- swap x and y
- remove encoding channel
- change channel type metadata where safe

#### Mark type

- switch mark type among bar / line / point / area / text / rule for supported charts

#### Aggregation and binning

- toggle aggregate for quantitative channels using supported aggregate ops
- toggle binning for quantitative fields
- edit stack setting where applicable

#### Sorting and scale behavior

- edit sort order for simple cases
- edit scale domain / zero / log where safe

#### Filtering

- add simple filters through a constrained UI
- remove editor-authored filters

#### Layers

- add/remove reference lines and text layers
- basic support for semantic layers created in-editor

### 9.2 Stage B constraints

Stage B should only permit semantic edits when the editor can preserve a clean internal model.

If the incoming spec is too complex or ambiguous, the system should:

- allow read-only inspection,
- allow Stage A cosmetic edits where safe,
- disable unsupported semantic edits with explanation.

### 9.3 Stage B output contract

The system should attempt to emit normalized Altair code for the supported subset.

Examples of acceptable output forms:

```python
alt.Chart(df).mark_bar().encode(
    x=alt.X("year:O", title="Year"),
    y=alt.Y("sales:Q", aggregate="sum"),
    color=alt.Color("region:N")
)
```

Fallback:

```python
alt.Chart.from_dict(spec)
```

### 9.4 Stage B success criteria

- user can perform common semantic chart edits without corrupting the spec,
- regenerated Altair is readable and stable on supported inputs,
- ambiguous edits are surfaced explicitly,
- unsupported patterns fail closed, not open.

---

## 10. Provenance strategy

Provenance is not strictly required for Stage A but strongly recommended from the beginning.

### 10.1 Metadata to preserve

- stable object IDs,
- chart origin metadata,
- original field shorthands,
- channel identities,
- annotation IDs,
- whether a property originated from mark-level style vs encoding-level style,
- optional original Altair AST fragments for supported nodes.

### 10.2 Why provenance matters

Without provenance, the editor can still mutate Vega-Lite specs, but several reverse-mapping tasks become noisy or ambiguous:

- whether color belongs in `mark.color` vs `encoding.color`,
- which layer owns an annotation,
- whether a title was explicitly user-authored or inferred,
- which normalized Altair code shape is most faithful.

### 10.3 Recommendation

Add a namespaced metadata block from day one, even if initially sparse.

Example:

```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "usermeta": {
    "editor": {
      "version": 1,
      "object_ids": {...},
      "provenance": {...}
    }
  }
}
```

---

## 11. Decompilation strategy

The system should not attempt unconstrained source recovery.

Instead, define a **normalized Altair subset**.

### 11.1 Supported normalized subset

- `alt.Chart(data)`
- standard mark constructors
- `encode(...)` with explicit channel constructors
- common axis / legend / scale arguments
- common transforms where editor-authored and representable
- `properties(...)`
- simple layering

### 11.2 Decompilation policy

1. Parse edited Vega-Lite spec into an internal chart AST.
2. Resolve object types using provenance where available.
3. Attempt to map AST into normalized Altair subset.
4. If any node falls outside the supported subset, emit `from_dict`.

### 11.3 Determinism requirement

For identical inputs and edits, normalized code generation must be deterministic.

---

## 12. Ambiguity policy

Some user edits can correspond to multiple valid spec changes.

Example: editing a bar’s color could mean:

- set `mark.color`,
- set `encoding.color = alt.value(...)`,
- edit a scale range,
- override only one layer.

The system should prefer explicit rules:

1. preserve current abstraction level when possible,
2. preserve semantic encodings unless user explicitly requests overriding them,
3. expose disambiguation UI when an edit crosses abstraction layers.

This is especially important in Stage B.

---

## 13. Validation and safety

Every mutation should pass through:

- schema validation,
- supported-pattern validation,
- optional linting / normalization,
- undo/redo checkpointing.

The editor must never silently emit invalid Vega-Lite.

If a mutation request is unsupported:

- reject the mutation,
- explain why,
- preserve chart state.

---

## 14. Testing plan

### 14.1 Stage A tests

- snapshot tests for spec mutations,
- schema validation after each edit,
- UI tests for selection and property panel binding,
- round-trip export tests for JSON and Python fallback,
- regression tests on representative Altair gallery charts within the supported subset.

### 14.2 Stage B tests

- encoding remap tests,
- mark-switch tests,
- aggregation/bin/sort/filter mutation tests,
- normalized Altair generation golden tests,
- fail-closed tests on unsupported charts.

### 14.3 Corpus strategy

Create a fixed corpus of supported charts:

- simple bar chart,
- line chart with color encoding,
- scatterplot,
- binned histogram,
- aggregated grouped bar chart,
- chart with editor-authored annotation layer.

Use this corpus for versioned compatibility testing.

---

## 15. Suggested implementation sequence

### Phase 0: technical spike

Deliverables:

- render Vega-Lite spec,
- inspect scenegraph / hit-test selected objects,
- prove object-to-spec mapping for titles, axes, legends, and mark styling.

### Phase 1: Stage A core

Deliverables:

- property panel,
- editable titles / axes / legends,
- mark style editing,
- annotation layer support,
- JSON export,
- Python `from_dict` export.

### Phase 2: Stage A hardening

Deliverables:

- provenance metadata,
- validation and normalization,
- undo/redo,
- support matrix and clear disabled states.

### Phase 3: Stage B semantic core

Deliverables:

- encoding reassignment,
- mark switching,
- aggregate/bin/sort/filter edits,
- normalized internal chart AST.

### Phase 4: Stage B codegen

Deliverables:

- normalized Altair code emission,
- supported-subset gating,
- deterministic output tests,
- explicit `from_dict` fallback.

---

## 16. Open questions

1. Should the frontend operate directly on Vega-Lite only, or on a thinner editor AST that then lowers into Vega-Lite?
2. How much of Vega scenegraph inspection is needed versus a pure spec-tree inspector?
3. Should Stage A accept arbitrary externally-authored Vega-Lite, or only Altair-originated charts initially?
4. How should annotation placement be represented so it survives responsive layout changes?
5. Should Stage B support field selection from an attached dataframe schema, or only spec-local editing at first?
6. How aggressively should normalized Altair code prefer explicit constructors versus shorthand syntax?

---

## 17. Recommended decisions

1. **Canonical IR:** use Vega-Lite spec plus editor metadata.
2. **Initial input boundary:** support Altair-originated charts first; permit best-effort handling of arbitrary Vega-Lite later.
3. **Editor interaction model:** property-editor first, selective direct manipulation second.
4. **Python output policy:** always support `from_dict`; add normalized Altair code only for a declared supported subset.
5. **Stage discipline:** do not mix semantic editing into Stage A except for editor-authored annotations.

---

## 18. MVP definition

A credible MVP is Stage A with the following guarantees:

- user can open an Altair chart,
- select title/axis/legend/annotation/mark-style objects,
- edit presentation properties visually,
- export valid Vega-Lite JSON,
- export valid Python using `alt.Chart.from_dict(spec)`.

That is already useful, buildable, and avoids the hardest inverse problems.

---

## 19. Exit criteria for moving from Stage A to Stage B

Move to Stage B only when all of the following hold:

- Stage A edits are robust across a representative chart corpus,
- selection and object mapping are stable,
- provenance metadata exists and survives round-trip edits,
- unsupported structures fail predictably,
- users demonstrably want semantic edits beyond presentation edits.

Once these conditions hold, Stage B becomes an extension of a stable system rather than a rewrite.

