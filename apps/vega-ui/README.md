# Vega UI

Vega UI is a Python-only Stage A Vega-Lite / Altair presentation editor. The browser UI is rendered with FastHTML, the JSON API stays on FastAPI, and chart previews are rendered server-side with `vl-convert-python`. There is no Node, Vite, or client bundle to install or debug.

## Why This Stack

The previous frontend stack added a second runtime, a second dependency graph, and a second failure surface for a tool whose editing model is already constrained and form-oriented. The current implementation keeps the useful parts and removes the accidental complexity:

- FastHTML for the UI because the editor is mostly forms, previews, and session links
- FastAPI for the existing typed JSON API and testable route layer
- the existing Python mutation engine for ingestion, provenance, validation, undo, annotations, and exports
- `vl-convert-python` for server-side SVG previews so the browser does not need Vega runtime code

That gives the repo one install path, one app process, and one place where chart mutations happen.

## What The App Does

Current supported Stage A workflow:

- paste a Vega-Lite spec into the loader page
- create an editing session backed by the in-memory session store
- change chart title, subtitle, size, and background
- change mark styling such as color, stroke, opacity, stroke width, and size
- change axis titles and label font sizes
- apply custom supported mutations through the existing mutation target list
- add and remove text annotations
- undo the last change
- export clean Vega-Lite JSON
- export Python code, preferring normalized Altair when possible and falling back to `alt.Chart.from_dict(...)`

The API remains available under `/api` for programmatic use.

## Architecture

Primary code paths:

- [`vega_ui/app.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/app.py): application factory, shared session store wiring, JSON API mounting, FastHTML UI mounting
- [`vega_ui/ui.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/ui.py): server-rendered editor pages, forms, preview rendering, redirect-based workflow
- [`vega_ui/engine/ingestion.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/engine/ingestion.py): validates incoming specs and normalizes supported charts
- [`vega_ui/engine/provenance.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/engine/provenance.py): stable editor metadata and export cleanup
- [`vega_ui/engine/mutation.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/engine/mutation.py): constrained presentation edits, layered annotation support, undo-safe mutation helpers
- [`vega_ui/engine/codegen.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/engine/codegen.py): JSON and Python export
- [`vega_ui/routes/charts.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/routes/charts.py): chart session API
- [`vega_ui/routes/mutations.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/routes/mutations.py): mutation, annotation, and undo API
- [`vega_ui/routes/export.py`](/home/alal/Desktop/code/viz/vega-ui/vega_ui/routes/export.py): export API
- [`tests`](/home/alal/Desktop/code/viz/vega-ui/tests): backend, API, mutation, provenance, validation, and UI tests

Important implementation choices:

- The FastHTML UI is mounted at `/`.
- The JSON API stays under `/api/...`.
- Session state is in memory and process-local.
- Preview rendering is done on the server by converting the current Vega-Lite spec to SVG.
- When annotations promote a chart to a layered spec, mark and axis mutations are applied to the base chart layer rather than the annotation layer.
- Preview rendering failures are caught and shown in the page instead of crashing the request.

## Install

From the repo root:

```bash
uv sync
```

That installs the runtime and dev dependencies into the project environment managed by `uv`.

## Run

From the repo root:

```bash
uv run vega-ui
```

Equivalent direct entrypoint:

```bash
uv run python main.py
```

The app listens on `http://127.0.0.1:8000`.

Runtime environment variables:

- `HOST`: bind host for the uvicorn process
- `PORT`: bind port for the uvicorn process
- `VEGA_UI_RELOAD`: set to `1` or `true` to enable auto-reload for development
- `VEGA_UI_BASE_PATH`: URL prefix for reverse-proxy deployments such as `/vega-ui`

Once it is running:

1. Open `http://127.0.0.1:8000`.
2. Paste a Vega-Lite JSON spec or start from the sample spec shown on the page.
3. Submit the loader form to create a session.
4. Use the server-rendered forms to edit chart settings, marks, axes, annotations, undo, and exports.

There is no separate frontend server and no build step required for local use.

Example reverse-proxy launch for a prefixed deployment:

```bash
HOST=127.0.0.1 PORT=8756 VEGA_UI_BASE_PATH=/vega-ui uv run vega-ui
```

## API Surface

Main endpoints:

- `POST /api/charts`
- `GET /api/charts/{session_id}`
- `POST /api/charts/{session_id}/mutate`
- `POST /api/charts/{session_id}/undo`
- `POST /api/charts/{session_id}/annotations/add`
- `POST /api/charts/{session_id}/annotations/update`
- `POST /api/charts/{session_id}/annotations/remove`
- `GET /api/charts/{session_id}/export/json`
- `GET /api/charts/{session_id}/export/python`
- `GET /health`

The FastHTML UI uses its own form posts for browser navigation, but it shares the same session store and mutation engine as the API.

## Test

Run the Python test suite:

```bash
uv run pytest
```

The suite covers:

- ingestion and validation
- provenance annotation
- mutation helpers
- API routes
- export code generation
- FastHTML UI smoke flows and layered annotation regression paths

## Operational Notes

- This is a development-focused app. The session store is in-memory and not suitable for multi-process deployment.
- FastHTML may create a local `.sesskey` file for session support; it is ignored by git.
- `uv.lock` is tracked and should remain tracked.
- If you extend the UI, keep business logic in the engine and route layers rather than embedding mutation rules in HTML handlers.
- If you add new presentation edits, add both engine-level tests and route or UI regressions for them.
- For the `lalten.org/vega-ui` deployment, see [`DEPLOY.md`](/home/alal/Desktop/code/viz/vega-ui/DEPLOY.md).
