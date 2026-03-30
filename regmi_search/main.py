#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
from fasthtml.common import FastHTML
from sentence_transformers import SentenceTransformer
from starlette.responses import JSONResponse


HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8755"))
DATA_DIR = Path(os.getenv("REGMI_SEARCH_DATA_DIR", Path(__file__).resolve().parent / "data"))
TOP_K = int(os.getenv("REGMI_SEARCH_TOP_K", "20"))
MODEL_NAME = os.getenv("REGMI_SEARCH_MODEL", "nomic-ai/modernbert-embed-base")
PAGE_MARKER_RE = re.compile(r"^\s*(\d{1,3})\.?\s*$")

app = FastHTML()


@dataclass
class PlaintextDoc:
    txt_name: str
    pdf_name: str
    lines: list[str]
    page_by_line: list[int | None]


class SearchStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        manifest_path = data_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest: {manifest_path}")

        self.manifest = json.loads(manifest_path.read_text())
        self.db = duckdb.connect(str(data_dir / "regmi_chunks.duckdb"), read_only=True)
        self.embeddings = np.load(data_dir / "embeddings.npy", mmap_mode="r")
        self.model: SentenceTransformer | None = None
        self.docs = self._load_plaintext_docs(data_dir / "plaintext")

    def _load_plaintext_docs(self, plaintext_dir: Path) -> dict[str, PlaintextDoc]:
        docs: dict[str, PlaintextDoc] = {}
        for path in sorted(plaintext_dir.glob("regmi_*.txt")):
            lines = path.read_text().splitlines()
            docs[path.name] = PlaintextDoc(
                txt_name=path.name,
                pdf_name=path.stem.replace("regmi_", "Regmi_") + ".pdf",
                lines=lines,
                page_by_line=infer_page_by_line(lines),
            )
        return docs

    def get_model(self) -> SentenceTransformer:
        if self.model is None:
            self.model = SentenceTransformer(MODEL_NAME, device="cpu")
        return self.model

    def semantic_search(self, query: str, limit: int) -> list[dict[str, object]]:
        model = self.get_model()
        query_vec = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)[0]
        scores = self.embeddings @ query_vec
        top_n = min(limit, int(scores.shape[0]))
        if top_n == 0:
            return []

        if top_n >= int(scores.shape[0]):
            ranked_idx = np.argsort(scores)[::-1][:top_n]
        else:
            candidate_idx = np.argpartition(scores, -top_n)[-top_n:]
            ranked_idx = candidate_idx[np.argsort(scores[candidate_idx])[::-1]]
        rows = self.db.execute(
            f"""
            select
                chunk_index,
                chunk_id,
                doc_id,
                doc_name,
                pdf_name,
                page,
                start_line,
                end_line,
                word_count,
                text
            from chunks
            where chunk_index in ({",".join("?" for _ in ranked_idx)})
            """,
            [int(idx) for idx in ranked_idx],
        ).fetchall()
        row_map = {row[0]: row for row in rows}

        results: list[dict[str, object]] = []
        for idx in ranked_idx:
            row = row_map[int(idx)]
            results.append(
                {
                    "kind": "semantic",
                    "chunk_index": int(row[0]),
                    "chunk_id": row[1],
                    "doc_id": row[2],
                    "doc_name": row[3],
                    "pdf_name": row[4],
                    "page": row[5],
                    "start_line": row[6],
                    "end_line": row[7],
                    "word_count": row[8],
                    "text": row[9],
                    "score": float(scores[int(idx)]),
                    "pdf_url": f"/pages/regmi_research_papers/{row[4]}",
                }
            )
        return results

    def regex_search(self, pattern: str, limit: int) -> list[dict[str, object]]:
        plaintext_dir = self.data_dir / "plaintext"
        if shutil.which("rg"):
            return self._regex_search_rg(plaintext_dir, pattern, limit)
        return self._regex_search_grep(plaintext_dir, pattern, limit)

    def _regex_search_rg(self, plaintext_dir: Path, pattern: str, limit: int) -> list[dict[str, object]]:
        command = [
            "rg",
            "-uuu",
            "--json",
            "--line-number",
            "--smart-case",
            "--max-count",
            str(max(limit * 4, limit)),
            pattern,
            str(plaintext_dir),
        ]
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode not in (0, 1):
            stderr = proc.stderr.strip() or "ripgrep failed."
            raise ValueError(stderr)

        matches: list[tuple[str, int, str]] = []
        for line in proc.stdout.splitlines():
            payload = json.loads(line)
            if payload.get("type") != "match":
                continue
            data = payload["data"]
            matches.append(
                (
                    Path(data["path"]["text"]).name,
                    int(data["line_number"]),
                    data["lines"]["text"].rstrip("\n"),
                )
            )
        return self._format_regex_results(matches, limit)

    def _regex_search_grep(self, plaintext_dir: Path, pattern: str, limit: int) -> list[dict[str, object]]:
        command = [
            "grep",
            "-RInE",
            "--binary-files=text",
            pattern,
            str(plaintext_dir),
        ]
        if pattern.lower() == pattern:
            command.insert(1, "-i")
        proc = subprocess.run(command, capture_output=True, text=True)
        if proc.returncode not in (0, 1):
            stderr = proc.stderr.strip() or "grep failed."
            raise ValueError(stderr)

        matches: list[tuple[str, int, str]] = []
        for raw_line in proc.stdout.splitlines():
            file_path, line_no, text = raw_line.split(":", 2)
            matches.append((Path(file_path).name, int(line_no), text))
        return self._format_regex_results(matches, limit)

    def _format_regex_results(self, matches: list[tuple[str, int, str]], limit: int) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for file_name, line_number, line_text in matches:
            doc = self.docs.get(file_name)
            if doc is None:
                continue

            context_before = doc.lines[line_number - 2].strip() if line_number > 1 else ""
            context_after = doc.lines[line_number].strip() if line_number < len(doc.lines) else ""
            page = doc.page_by_line[line_number - 1] if line_number - 1 < len(doc.page_by_line) else None
            results.append(
                {
                    "kind": "regex",
                    "doc_id": file_name.replace(".txt", ""),
                    "doc_name": file_name.replace(".txt", ""),
                    "pdf_name": doc.pdf_name,
                    "line_number": line_number,
                    "page": page,
                    "text": line_text,
                    "context_before": context_before,
                    "context_after": context_after,
                    "pdf_url": f"/pages/regmi_research_papers/{doc.pdf_name}",
                }
            )
            if len(results) >= limit:
                break
        return results


def infer_page_by_line(lines: list[str]) -> list[int | None]:
    page_re = PAGE_MARKER_RE
    page_by_line: list[int | None] = [None] * len(lines)
    current_page: int | None = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        match = page_re.fullmatch(stripped)
        prev_blank = idx == 0 or not lines[idx - 1].strip()
        next_blank = idx == len(lines) - 1 or not lines[idx + 1].strip()
        if match and prev_blank and next_blank:
            candidate = int(match.group(1))
            if current_page is None and candidate <= 2:
                current_page = candidate
            elif current_page is not None and candidate >= current_page and candidate - current_page <= 4:
                current_page = candidate
        page_by_line[idx] = current_page

    return page_by_line


STORE = SearchStore(DATA_DIR)


@app.get("/health")
def health():
    return JSONResponse(
        {
            "ok": True,
            "chunks": int(STORE.embeddings.shape[0]),
            "embedding_dim": int(STORE.embeddings.shape[1]),
            "model_name": STORE.manifest["model_name"],
        }
    )


@app.get("/search")
def search(q: str = "", mode: str = "regex", limit: int = TOP_K):
    query = q.strip()
    if not query:
        return JSONResponse({"ok": False, "error": "Enter a query."}, status_code=400)

    limit = max(1, min(limit, 50))
    try:
        if mode == "semantic":
            results = STORE.semantic_search(query, limit=limit)
        else:
            results = STORE.regex_search(query, limit=limit)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    return JSONResponse(
        {
            "ok": True,
            "mode": mode,
            "query": query,
            "limit": limit,
            "results": results,
        }
    )


if __name__ == "__main__":
    from fasthtml.common import serve

    serve(host=HOST, port=PORT)
