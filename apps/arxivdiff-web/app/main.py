from __future__ import annotations

import html
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import threading
import time
import dataclasses
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlretrieve

import uvicorn
from binaryornot.check import is_binary
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from webdiff import diff, options, util
from webdiff.dirdiff import gitdiff
from webdiff.unified_diff import Code, diff_to_codes


ARXIV_ID_RE = re.compile(r"(?P<id>\d{4}\.\d{4,5})(?:v(?P<version>\d+))?")
BASE_PATH = os.environ.get("ARXIVDIFF_BASE_PATH", "/arxivdiff").rstrip("/")
DATA_DIR = Path(os.environ.get("ARXIVDIFF_DATA_DIR", "/tmp/arxivdiff-web"))
ARCHIVE_CACHE_DIR = DATA_DIR / "_archives"
WEBDIFF_DIR = Path(__import__("webdiff").__file__).parent
WEBDIFF_CONFIG = options.get_config()["webdiff"]


@dataclass
class Job:
    job_id: str
    paper_id: str
    v_before: int
    v_after: int
    work_dir: Path
    old_dir: Path
    new_dir: Path


app = FastAPI(root_path=BASE_PATH)
app.mount("/static", StaticFiles(directory=WEBDIFF_DIR / "static"), name="webdiff-static")
JOBS: dict[str, Job] = {}
DIFFS: dict[str, list] = {}
RUNNING: set[str] = set()
RUNNING_LOCK = threading.Lock()


def page(title: str, body: str, request: Request | None = None) -> HTMLResponse:
    base = request.scope.get("root_path", BASE_PATH) if request else BASE_PATH
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f6f7f9; color: #15171a; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 16px; }}
    form {{ display: grid; grid-template-columns: minmax(280px, 1fr) 110px 110px auto; gap: 10px; align-items: end; }}
    label {{ display: grid; gap: 6px; font-size: 13px; color: #3f4650; }}
    input {{ height: 38px; border: 1px solid #c9d0d8; border-radius: 6px; padding: 0 10px; font: inherit; background: white; }}
    button, .button {{ height: 40px; border: 0; border-radius: 6px; padding: 0 14px; font: inherit; font-weight: 650; color: white; background: #1d4ed8; cursor: pointer; }}
    .button {{ display: inline-flex; align-items: center; justify-content: center; text-decoration: none; box-sizing: border-box; }}
    .button.secondary {{ color: #1f2937; background: #e5e7eb; }}
    button[disabled] {{ opacity: .72; cursor: wait; }}
    .panel {{ background: white; border: 1px solid #dce1e7; border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
    .muted {{ color: #66707c; font-size: 13px; }}
    .status {{ margin: 12px 0; color: #334155; }}
    .toolbar {{ display: flex; gap: 8px; align-items: center; justify-content: space-between; margin: 12px 0; flex-wrap: wrap; }}
    .toolbar-actions {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .file-label {{ color: #334155; font-size: 13px; overflow-wrap: anywhere; }}
    .workbox {{ display: grid; gap: 10px; place-items: center; min-height: 320px; border: 1px solid #cbd5e1; border-radius: 8px; background: white; color: #334155; }}
    .spinner {{ width: 42px; height: 42px; border: 4px solid #dbe4ef; border-top-color: #1d4ed8; border-radius: 999px; animation: spin .9s linear infinite; }}
    .stage {{ color: #66707c; font-size: 13px; }}
    .error {{ color: #b91c1c; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    iframe {{ width: 100%; height: calc(100vh - 230px); min-height: 620px; border: 1px solid #cbd5e1; border-radius: 8px; background: white; }}
    @media (max-width: 720px) {{ form {{ grid-template-columns: 1fr 1fr; }} label:first-child {{ grid-column: 1 / -1; }} button {{ grid-column: 1 / -1; }} main {{ padding: 14px; }} }}
  </style>
</head>
<body>
<main>
  <h1>arXiv Diff</h1>
  {body}
</main>
</body>
</html>"""
    )


def form_html(paper_url: str = "", v_before: str = "1", v_after: str = "2") -> str:
    return f"""
<div class="panel">
  <form action="{BASE_PATH}/generate" method="post">
    <label>arXiv URL or ID
      <input name="paper_url" value="{html.escape(paper_url)}" placeholder="https://arxiv.org/abs/2503.23524 or 2503.23524" required>
    </label>
    <label>Before
      <input name="v_before" type="number" min="1" value="{html.escape(v_before)}" required>
    </label>
    <label>After
      <input name="v_after" type="number" min="1" value="{html.escape(v_after)}" required>
    </label>
    <button type="submit">Generate diff</button>
  </form>
</div>
"""


def parse_paper(value: str) -> tuple[str, int | None]:
    match = ARXIV_ID_RE.search(value.strip())
    if not match:
        raise HTTPException(status_code=400, detail="Could not find a modern arXiv id in that URL.")
    version = int(match.group("version")) if match.group("version") else None
    return match.group("id"), version


def safe_extract(tar_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as archive:
        archive.extractall(path=dest, filter="data")


def archive_path(paper_id: str, version: int) -> Path:
    safe_id = paper_id.replace("/", "_")
    return ARCHIVE_CACHE_DIR / f"{safe_id}v{version}.tar.gz"


def job_id_for(paper_id: str, v_before: int, v_after: int) -> str:
    readable = f"{paper_id.replace('.', '-')}-v{v_before}-v{v_after}"
    digest = hashlib.sha1(f"{paper_id}:v{v_before}:v{v_after}".encode()).hexdigest()[:8]
    return f"{readable}-{digest}"


def meta_path(job_id: str) -> Path:
    return DATA_DIR / job_id / "job.json"


def read_meta(job_id: str) -> dict:
    path = meta_path(job_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write_meta(job: Job, status: str, stage: str = "", error: str | None = None) -> None:
    job.work_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_id": job.job_id,
        "paper_id": job.paper_id,
        "v_before": job.v_before,
        "v_after": job.v_after,
        "status": status,
        "stage": stage,
        "error": error,
        "updated_at": time.time(),
    }
    (job.work_dir / "job.json").write_text(json.dumps(payload, indent=2))


def is_done(job: Job, meta: dict | None = None) -> bool:
    meta = meta if meta is not None else read_meta(job.job_id)
    return meta.get("status") == "done" or (
        "status" not in meta and job.old_dir.exists() and job.new_dir.exists()
    )


def download_version(paper_id: str, version: int, dest: Path) -> None:
    src_url = f"https://arxiv.org/src/{paper_id}v{version}"
    ARCHIVE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tar_path = archive_path(paper_id, version)
    try:
        if not tar_path.exists() or tar_path.stat().st_size == 0:
            tmp_path = tar_path.with_suffix(".tmp")
            urlretrieve(src_url, tmp_path)
            tmp_path.replace(tar_path)
        safe_extract(tar_path, dest)
    except (HTTPError, URLError, tarfile.TarError, OSError) as exc:
        raise RuntimeError(f"Could not fetch/extract {src_url}: {exc}") from exc


def job_from_parts(paper_id: str, v_before: int, v_after: int) -> Job:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    job_id = job_id_for(paper_id, v_before, v_after)
    work_dir = DATA_DIR / job_id
    old_dir = work_dir / "old_src"
    new_dir = work_dir / "new_src"
    return Job(job_id, paper_id, v_before, v_after, work_dir, old_dir, new_dir)


def ensure_job(job: Job) -> None:
    meta = read_meta(job.job_id)
    if is_done(job, meta):
        if meta.get("status") != "done":
            write_meta(job, "done", "ready")
        return
    with RUNNING_LOCK:
        if job.job_id in RUNNING:
            return
        RUNNING.add(job.job_id)
    try:
        write_meta(job, "running", "preparing workspace")
        if job.old_dir.exists():
            shutil.rmtree(job.old_dir)
        if job.new_dir.exists():
            shutil.rmtree(job.new_dir)
        write_meta(job, "running", f"fetching {job.paper_id}v{job.v_before} source")
        download_version(job.paper_id, job.v_before, job.old_dir)
        write_meta(job, "running", f"fetching {job.paper_id}v{job.v_after} source")
        download_version(job.paper_id, job.v_after, job.new_dir)
        write_meta(job, "running", "building file diff")
        JOBS[job.job_id] = job
        DIFFS[job.job_id] = gitdiff(str(job.old_dir), str(job.new_dir), WEBDIFF_CONFIG)
        write_meta(job, "done", "ready")
    except Exception as exc:
        write_meta(job, "error", "failed", str(exc))
    finally:
        with RUNNING_LOCK:
            RUNNING.discard(job.job_id)


def load_job(job_id: str) -> Job:
    if job_id in JOBS:
        return JOBS[job_id]
    path = meta_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Unknown diff job.")
    meta = json.loads(path.read_text())
    job = Job(
        job_id=job_id,
        paper_id=meta["paper_id"],
        v_before=int(meta["v_before"]),
        v_after=int(meta["v_after"]),
        work_dir=DATA_DIR / job_id,
        old_dir=DATA_DIR / job_id / "old_src",
        new_dir=DATA_DIR / job_id / "new_src",
    )
    JOBS[job_id] = job
    return job


def job_diffs(job_id: str) -> list:
    job = load_job(job_id)
    meta = read_meta(job_id)
    if not is_done(job, meta):
        raise HTTPException(status_code=409, detail="Diff job is not ready yet.")
    if job_id not in DIFFS:
        DIFFS[job_id] = gitdiff(str(job.old_dir), str(job.new_dir), WEBDIFF_CONFIG)
    return DIFFS[job_id]


def app_base(request: Request) -> str:
    return request.scope.get("root_path", BASE_PATH).rstrip("/")


def preferred_initial_idx(job_id: str) -> int:
    for idx, item in enumerate(job_diffs(job_id)):
        paths = [path for path in [item.a_path, item.b_path] if path]
        if paths and not any(is_binary(path) for path in paths):
            return idx
    return 0


def requested_file_idx(request: Request, job_id: str) -> int | None:
    raw = request.query_params.get("file")
    if raw is None:
        return None
    try:
        idx = int(raw)
    except ValueError:
        return None
    if 0 <= idx < len(job_diffs(job_id)):
        return idx
    return None


def diff_file_label(job_id: str, idx: int) -> str:
    pairs = diff.get_thin_list(job_diffs(job_id))
    if idx < 0 or idx >= len(pairs):
        return f"file {idx}"
    pair = pairs[idx]
    return str(pair.get("b") or pair.get("a") or f"file {idx}")


def job_body(job: Job, request: Request) -> str:
    base = app_base(request)
    meta = read_meta(job.job_id)
    status = meta.get("status", "queued")
    stage = meta.get("stage", "queued")
    error = meta.get("error")
    title = f"{job.paper_id}v{job.v_before} → v{job.v_after}"
    if is_done(job, meta):
        if status != "done":
            write_meta(job, "done", "ready")
        initial_idx = requested_file_idx(request, job.job_id)
        if initial_idx is None:
            initial_idx = preferred_initial_idx(job.job_id)
        permalink = f"{base}/jobs/{job.job_id}?file={initial_idx}"
        file_label = diff_file_label(job.job_id, initial_idx)
        return (
            form_html(f"https://arxiv.org/abs/{job.paper_id}", str(job.v_before), str(job.v_after))
            + f'<p class="status">Diff for <strong>{html.escape(title)}</strong>.</p>'
            + f"""
<div class="toolbar">
  <div class="file-label">Current file: <strong id="current-file">{html.escape(file_label)}</strong></div>
  <div class="toolbar-actions">
    <a class="button secondary" id="permalink" href="{html.escape(permalink)}">Permalink</a>
    <button type="button" id="copy-permalink">Copy link</button>
  </div>
</div>
<iframe id="diff-frame" src="{base}/jobs/{job.job_id}/view/{initial_idx}"></iframe>
<script>
const baseJobUrl = "{base}/jobs/{job.job_id}";
const fileLabels = {json.dumps([diff_file_label(job.job_id, i) for i, _ in enumerate(job_diffs(job.job_id))])};
const frame = document.getElementById("diff-frame");
const permalink = document.getElementById("permalink");
const copyButton = document.getElementById("copy-permalink");
const currentFile = document.getElementById("current-file");

function setPermalink(idx) {{
  if (!Number.isInteger(idx) || idx < 0 || idx >= fileLabels.length) return permalink.href;
  const url = `${{baseJobUrl}}?file=${{idx}}`;
  permalink.href = url;
  currentFile.textContent = fileLabels[idx] || `file ${{idx}}`;
  const absolute = new URL(url, window.location.origin).toString();
  window.history.replaceState(null, "", absolute);
  return absolute;
}}

function syncFromFrame() {{
  try {{
    const match = frame.contentWindow.location.pathname.match(/\\/view\\/(\\d+)$/);
    if (match) setPermalink(Number(match[1]));
  }} catch (error) {{}}
}}

frame.addEventListener("load", syncFromFrame);
window.addEventListener("message", event => {{
  if (event.source !== frame.contentWindow) return;
  const data = event.data || {{}};
  if (data.type !== "arxivdiff:file") return;
  setPermalink(Number(data.idx));
}});
copyButton.addEventListener("click", async () => {{
  const url = permalink.href;
  await navigator.clipboard.writeText(url);
  copyButton.textContent = "Copied";
  setTimeout(() => copyButton.textContent = "Copy link", 1200);
}});
</script>
"""
        )
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return (
        form_html(f"https://arxiv.org/abs/{job.paper_id}", str(job.v_before), str(job.v_after))
        + f'<p class="status">Diff for <strong>{html.escape(title)}</strong>.</p>'
        + f"""
<div class="workbox" id="workbox">
  <div class="spinner" aria-hidden="true"></div>
  <strong id="status-text">{html.escape(status.title())}</strong>
  <div class="stage" id="stage-text">{html.escape(stage)}</div>
  {error_html}
</div>
<script>
const statusUrl = "{base}/jobs/{job.job_id}/status";
async function pollStatus() {{
  const response = await fetch(statusUrl, {{cache: "no-store"}});
  const data = await response.json();
  document.getElementById("status-text").textContent = data.status === "done" ? "Ready" : data.status;
  document.getElementById("stage-text").textContent = data.stage || "";
  if (data.status === "done") {{
    window.location.reload();
    return;
  }}
  if (data.status === "error") {{
    document.getElementById("workbox").innerHTML = `<strong class="error">Diff failed</strong><div class="stage">${{data.error || "Unknown error"}}</div>`;
    return;
  }}
  setTimeout(pollStatus, 1000);
}}
setTimeout(pollStatus, 600);
</script>
"""
    )


def tolerant_diff_ops(item, git_diff_args=None, normalize_json=False):
    try:
        return diff.get_diff_ops(item, git_diff_args, normalize_json=normalize_json)
    except UnicodeDecodeError:
        a_path = os.path.realpath(item.a_path) if item.a_path else ""
        b_path = os.path.realpath(item.b_path) if item.b_path else ""
        if normalize_json:
            a_path = a_path and util.normalize_json(a_path)
            b_path = b_path and util.normalize_json(b_path)
        if a_path and b_path:
            num_lines = diff.fast_num_lines(b_path)
            result = subprocess.run(
                ["git", "diff", "--no-index", *(git_diff_args or []), a_path, b_path],
                capture_output=True,
                check=False,
            )
            codes = diff_to_codes(result.stdout.decode("utf-8", errors="replace"), num_lines)
            return codes or [Code(type="replace", before=(0, 1), after=(0, 1))]
        if a_path:
            return [Code("delete", before=(0, diff.fast_num_lines(a_path)), after=(0, 0))]
        if b_path:
            return [Code("insert", before=(0, 0), after=(0, diff.fast_num_lines(b_path) + 1))]
        return []


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return page("arXiv Diff", form_html(), request)


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    background_tasks: BackgroundTasks,
    paper_url: str = Form(...),
    v_before: int = Form(...),
    v_after: int = Form(...),
):
    paper_id, version_in_url = parse_paper(paper_url)
    if version_in_url and v_after == 2 and v_before == 1:
        v_after = version_in_url
        v_before = max(1, version_in_url - 1)
    if v_before == v_after:
        raise HTTPException(status_code=400, detail="Pick two different versions.")
    job = job_from_parts(paper_id, v_before, v_after)
    JOBS[job.job_id] = job
    meta = read_meta(job.job_id)
    if meta.get("status") != "done":
        write_meta(job, meta.get("status", "queued"), meta.get("stage", "queued"), meta.get("error"))
        background_tasks.add_task(ensure_job, job)
    return page("arXiv Diff", job_body(job, request), request)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_page(job_id: str, request: Request):
    job = load_job(job_id)
    return page("arXiv Diff", job_body(job, request), request)


@app.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    job = load_job(job_id)
    meta = read_meta(job_id)
    if is_done(job, meta):
        if meta.get("status") != "done":
            write_meta(job, "done", "ready")
        meta = read_meta(job_id)
    return JSONResponse(
        {
            "job_id": job_id,
            "status": meta.get("status", "queued"),
            "stage": meta.get("stage", ""),
            "error": meta.get("error"),
        }
    )


@app.get("/jobs/{job_id}/view/{idx}", response_class=HTMLResponse)
async def webdiff_view(job_id: str, idx: int, request: Request):
    pairs = diff.get_thin_list(job_diffs(job_id))
    base = app_base(request)
    data = json.dumps(
        {
            "idx": idx,
            "has_magick": util.is_imagemagick_available(),
            "pairs": pairs,
            "git_config": options.get_config(),
        },
        indent=2,
    )
    html_text = (WEBDIFF_DIR / "templates" / "file_diff.html").read_text()
    html_text = html_text.replace("/static/", f"{base}/static/")
    html_text = html_text.replace(f"{base}/static/js/file_diff.js", f"{base}/jobs/{job_id}/static/js/file_diff.js")
    html_text = html_text.replace(
        f"{base}/static/css/inconsolata.css",
        f"{base}/jobs/{job_id}/static/css/inconsolata.css",
    )
    html_text = html_text.replace("/theme.css", f"{base}/theme.css")
    html_text = html_text.replace("{{data}}", data)
    return HTMLResponse(html_text)


@app.get("/jobs/{job_id}/static/js/file_diff.js")
async def patched_file_diff_js(job_id: str, request: Request):
    load_job(job_id)
    base = app_base(request)
    prefix = f"{base}/jobs/{job_id}"
    script = (WEBDIFF_DIR / "static" / "js" / "file_diff.js").read_text()
    replacements = {
        "`/thick/${e}`": f"`{prefix}/thick/${{e}}`",
        "`/${e}/get_contents`": f"`{prefix}/${{e}}/get_contents`",
        "`/diff/${n.idx}`": f"`{prefix}/diff/${{n.idx}}`",
        "`/pdiff/${n.idx}`": f"`{prefix}/pdiff/${{n.idx}}`",
        "`/a/image/${i.a}`": f"`{prefix}/a/image/${{i.a}}`",
        "`/b/image/${i.b}`": f"`{prefix}/b/image/${{i.b}}`",
        "`/pdiffbbox/${c.idx}`": f"`{prefix}/pdiffbbox/${{c.idx}}`",
        'path:"/:index?"': f'path:"{prefix}/view/:index?"',
        'g(`/${e}`+(t?`?${t}`:""))': f'g(`{prefix}/view/${{e}}`+(t?`?${{t}}`:""))',
        "new WebSocket(`ws://${an}/ws`)": (
            f"new WebSocket(`${{window.location.protocol === 'https:' ? 'wss' : 'ws'}}://${{an}}{prefix}/ws`)"
        ),
    }
    for old, new in replacements.items():
        script = script.replace(old, new)
    script = script.replace(
        "e.useEffect(()=>{const e=St(w),t=w.type;document.title=`Diff: ${e} (${t})`},[w]);",
        (
            "e.useEffect(()=>{const e=St(w),t=w.type;"
            "document.title=`Diff: ${e} (${t})`;"
            "window.parent&&window.parent.postMessage({type:\"arxivdiff:file\",idx:b,label:e},\"*\")},[w,b]);"
        ),
    )
    return Response(script, media_type="application/javascript")


@app.get("/jobs/{job_id}/static/css/inconsolata.css")
async def patched_inconsolata_css(job_id: str, request: Request):
    load_job(job_id)
    base = app_base(request)
    css = (WEBDIFF_DIR / "static" / "css" / "inconsolata.css").read_text()
    css = css.replace("url(/static/", f"url({base}/static/")
    css = css.replace("url('/static/", f"url('{base}/static/")
    css = css.replace('url("/static/', f'url("{base}/static/')
    return Response(css, media_type="text/css")


@app.get("/theme.css")
async def theme_css():
    theme = options.get_config()["webdiff"]["theme"]
    theme_path = WEBDIFF_DIR / "static" / "css" / "themes" / f"{theme}.css"
    return FileResponse(theme_path, media_type="text/css")


@app.get("/jobs/{job_id}/thick/{idx}")
async def thick(job_id: str, idx: int):
    diffs = job_diffs(job_id)
    if idx < 0 or idx >= len(diffs):
        raise HTTPException(status_code=404, detail="Diff index out of range.")
    return JSONResponse(diff.get_thick_dict(diffs[idx]))


@app.post("/jobs/{job_id}/{side}/get_contents")
async def get_contents(job_id: str, side: str, request: Request):
    if side not in {"a", "b"}:
        raise HTTPException(status_code=404, detail="Unknown side.")
    form = await request.form()
    path = str(form.get("path", ""))
    if not path:
        return JSONResponse({"error": "incomplete"}, status_code=400)
    idx = diff.find_diff_index(job_diffs(job_id), side, path)
    if idx is None:
        return JSONResponse({"error": "not found"}, status_code=400)
    item = job_diffs(job_id)[idx]
    abs_path = item.a_path if side == "a" else item.b_path
    try:
        if is_binary(abs_path):
            return PlainTextResponse(f"Binary file ({os.path.getsize(abs_path)} bytes)")
        if form.get("normalize_json"):
            abs_path = util.normalize_json(abs_path)
        return FileResponse(abs_path, media_type="text/plain")
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/jobs/{job_id}/diff/{idx}")
async def diff_ops(job_id: str, idx: int, request: Request):
    diffs = job_diffs(job_id)
    if idx < 0 or idx >= len(diffs):
        raise HTTPException(status_code=404, detail="Diff index out of range.")
    payload = await request.json()
    ops = payload.get("options") or []
    extra_args = WEBDIFF_CONFIG["extraFileDiffArgs"]
    if extra_args:
        ops += extra_args.split(" ")
    codes = [
        dataclasses.asdict(item)
        for item in tolerant_diff_ops(diffs[idx], ops, normalize_json=payload.get("normalize_json"))
    ]
    return JSONResponse(codes)


@app.get("/jobs/{job_id}/{side}/image/{path:path}")
async def image(job_id: str, side: str, path: str):
    idx = diff.find_diff_index(job_diffs(job_id), side, path)
    if idx is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    item = job_diffs(job_id)[idx]
    abs_path = item.a_path if side == "a" else item.b_path
    return FileResponse(abs_path)


@app.get("/jobs/{job_id}/pdiff/{idx}")
async def pdiff(job_id: str, idx: int):
    diffs = job_diffs(job_id)
    if idx < 0 or idx >= len(diffs):
        raise HTTPException(status_code=404, detail="Diff index out of range.")
    item = diffs[idx]
    same, png = util.generate_pdiff_image(item.a_path, item.b_path)
    return FileResponse(png, media_type="image/png")


@app.get("/jobs/{job_id}/pdiffbbox/{idx}")
async def pdiffbbox(job_id: str, idx: int):
    diffs = job_diffs(job_id)
    if idx < 0 or idx >= len(diffs):
        raise HTTPException(status_code=404, detail="Diff index out of range.")
    item = diffs[idx]
    return JSONResponse(util.pdiff_bbox(item.a_path, item.b_path))


@app.websocket("/jobs/{job_id}/ws")
async def ws(job_id: str, websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(message)
    except Exception:
        return


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8757"))
    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
