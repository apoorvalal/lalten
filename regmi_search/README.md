# Regmi Search App

Small FastHTML app for hybrid archive search on `lalten.org/pages/regmi_research_papers/`.

This scaffold is intentionally simple:

- regex search uses `rg` when available and falls back to recursive `grep -E`
- semantic search embeds the query on CPU with `sentence-transformers`
- chunk metadata lives in DuckDB
- the embedding matrix lives in `embeddings.npy`
- the static page is plain HTML with a small amount of JavaScript

The point is not to be fancy. The point is to have a self-contained archive search app that is easy to clone, rename, and redeploy for another small corpus.

## What lives where

This directory is the deployment bundle for the live app. It expects prebuilt search artifacts in a sibling `data/` directory on the server.

Expected layout on Hetzner:

```text
/root/lalten/regmi_search/
├── main.py
├── pyproject.toml
├── README.md
├── regmi_search.service
├── uv.lock
└── data/
    ├── embeddings.npy
    ├── manifest.json
    ├── regmi_chunks.duckdb
    └── plaintext/
        ├── regmi_01.txt
        ├── regmi_02.txt
        └── ...
```

The public-facing static page is separate:

```text
/root/lalten/pages/regmi_research_papers/index.html
```

Nginx proxies `/pages/regmi_research_papers/api/` to the FastHTML service and serves the PDFs and `index.html` statically from `/pages/regmi_research_papers/`.

## Runtime contract

The app only needs four data artifacts:

1. `embeddings.npy`
   Normalized `float32` embedding matrix of shape `(num_chunks, embedding_dim)`.
2. `regmi_chunks.duckdb`
   DuckDB file with one row per chunk and stable `chunk_index` values aligned to the rows in `embeddings.npy`.
3. `manifest.json`
   Small metadata file used for diagnostics and health checks.
4. `plaintext/`
   Plain text files used for regex search and line-level context.

The app assumes the DuckDB `chunks` table has these columns:

```sql
chunk_index integer primary key,
chunk_id varchar,
doc_id varchar,
doc_name varchar,
pdf_name varchar,
page integer,
start_line integer,
end_line integer,
word_count integer,
text varchar
```

The text files in `plaintext/` should correspond to the chunk source text. For this Regmi deployment they are `regmi_*.txt`.

## Search modes

### Regex search

Regex mode shells out to a local search tool instead of pulling the full corpus into Python:

- preferred path: `rg -uuu --json --line-number --smart-case`
- fallback path: `grep -RInE --binary-files=text`

That gives good enough grep-style behavior for modest archives while keeping the implementation simple.

Results are post-processed in Python to:

- map each hit back to the source `.txt`
- infer the PDF name
- attach nearby line context
- infer a likely page number from page-marker lines in the plaintext

### Semantic search

Semantic mode:

1. loads `nomic-ai/modernbert-embed-base`
2. embeds the query on CPU
3. computes cosine-style similarity with a dot product against the normalized `.npy` matrix
4. looks up metadata for the best chunk rows in DuckDB

This is fast enough for small archives without introducing a vector database.

## Main files

### `main.py`

The FastHTML app. Responsibilities:

- load the manifest, DuckDB file, embeddings, and plaintext corpus
- lazily load the sentence-transformers model on first semantic query
- serve `/health`
- serve `/search`
- run regex and semantic retrieval

### `regmi_search.service`

Systemd unit. Runs the app under `uv run` and binds to `127.0.0.1:8755`.

### `pyproject.toml` and `uv.lock`

Pinned Python dependencies for the runtime app.

## API

### `GET /health`

Returns a small JSON payload confirming:

- service is up
- artifact counts are readable
- the configured embedding model name

### `GET /search`

Query params:

- `q`: query text or regex
- `mode`: `regex` or `semantic`
- `limit`: max result count, capped in the app

Examples:

```bash
curl 'http://127.0.0.1:8755/health'
curl 'http://127.0.0.1:8755/search?mode=regex&limit=5&q=Chandan%20Nath'
curl 'http://127.0.0.1:8755/search?mode=semantic&limit=5&q=trade%20between%20british%20india%20and%20nepal'
```

## Local development

From the app directory:

```bash
uv sync
REGMI_SEARCH_DATA_DIR=/path/to/output uv run python main.py
```

The app defaults to `./data`, so for deployed use you can just place the artifacts in `regmi_search/data/`.

## How to repurpose this for another archive

The easiest path is to copy this app directory and rename a few archive-specific strings.

### 1. Build plaintext first

Start with one `.txt` per source document. Keep the filenames stable. If you also have page marker lines in the text, the app can infer approximate page numbers for regex hits.

### 2. Chunk the corpus

Chunk by paragraph, page, or short section. The current Regmi setup uses paragraph-based chunks with target and max word counts. Keep chunks reasonably short so semantic hits are interpretable.

Good practical targets:

- target chunk size around `150-220` words
- hard max around `250-350` words
- preserve document id, page, and line offsets in metadata

### 3. Embed the chunks

Use a sentence-transformers embedding model and normalize embeddings before saving.

For this app, the important invariant is:

- row `i` in `embeddings.npy` must correspond to `chunk_index = i` in DuckDB

### 4. Write the four runtime artifacts

Your offline builder can be any script you want, but it must output:

- `embeddings.npy`
- `manifest.json`
- `regmi_chunks.duckdb`
- `plaintext/`

If you are adapting this app wholesale, you can keep the DuckDB filename and schema unchanged even for a different archive. That is the lowest-friction option.

### 5. Rename archive-specific paths

For a new archive, search for these strings and update them:

- `regmi_search`
- `regmi_research_papers`
- `regmi_`
- `Regmi_`
- `REGMI_SEARCH_*`

The main places that usually need edits are:

- `main.py`
- `regmi_search.service`
- the static `index.html`
- nginx route definitions

### 6. Deploy the bundle

Copy:

- the app directory to something like `/root/lalten/<archive>_search/`
- the static page to `/root/lalten/pages/<archive>/index.html`
- the PDFs or source scans to `/root/lalten/pages/<archive>/`

Then add an nginx proxy block for `/pages/<archive>/api/` pointing at the systemd service port.

### 7. Verify both search modes

Always test:

- `/health`
- at least one literal regex query
- at least one semantic query
- the browser page
- an actual PDF link from a result card

## Suggested offline build shape

The live app does not care how the index was produced, but a practical pattern is:

1. read `.txt` files from an input directory
2. infer page numbers from standalone page marker lines if present
3. split into paragraphs
4. merge adjacent paragraphs into chunks within a word budget
5. embed chunk text with `sentence-transformers`
6. save the matrix to `.npy`
7. write chunk metadata to DuckDB
8. copy the plaintext files into the output bundle
9. write a small manifest

That is enough for a full grep plus semantic retrieval stack without extra infrastructure.

## Operational notes

- First semantic query is slower because the embedding model loads lazily.
- If `rg` is unavailable on the server, regex search falls back to `grep -E`.
- Semantic search is entirely CPU-side at runtime. Build embeddings elsewhere if you want the indexing step to be faster.
- The app is designed for small archives. If the corpus grows large, move retrieval into a proper index instead of a plain `.npy` scan.

## Why this pattern works well for small archives

It keeps each layer replaceable:

- static frontend is just HTML
- backend is a single Python file
- retrieval metadata is DuckDB
- vectors are a plain NumPy file
- deployment is a small systemd service plus one nginx route

That makes it straightforward to duplicate for another archive without dragging in a larger search stack.
