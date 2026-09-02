import hashlib
import hmac
import os
import re
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, send_file


BASE = "/quomodoc"
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "quomodoc.db"
MAX_BYTES = 20 * 1024 * 1024
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


UPLOAD_CLI = r'''#!/usr/bin/env python3
"""Upload one HTML document to Quomodoc over HTTPS."""

import argparse
import getpass
import json
import mimetypes
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "https://lalten.org/quomodoc/api/documents"


def field(boundary, name, value, filename=None, content_type=None):
    disposition = f'form-data; name="{name}"'
    if filename is not None:
        disposition += f'; filename="{filename}"'
    headers = [f"Content-Disposition: {disposition}"]
    if content_type:
        headers.append(f"Content-Type: {content_type}")
    return (
        f"--{boundary}\r\n" + "\r\n".join(headers) + "\r\n\r\n"
    ).encode() + value + b"\r\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="self-contained HTML file")
    parser.add_argument("--title", help="homepage title; defaults to filename")
    parser.add_argument("--slug", default="", help="optional URL slug")
    args = parser.parse_args()

    if not args.html.is_file():
        parser.error(f"file not found: {args.html}")
    content = args.html.read_bytes()
    if len(content) > 20 * 1024 * 1024:
        parser.error("HTML file exceeds Quomodoc's 20 MiB limit")

    password = getpass.getpass("Quomodoc upload password: ")
    boundary = "quomodoc-" + secrets.token_hex(16)
    title = args.title or args.html.stem.replace("-", " ").replace("_", " ").title()
    body = b"".join([
        field(boundary, "password", password.encode()),
        field(boundary, "title", title.encode()),
        field(boundary, "slug", args.slug.encode()),
        field(
            boundary,
            "file",
            content,
            filename=args.html.name,
            content_type=mimetypes.guess_type(args.html.name)[0] or "text/html",
        ),
        f"--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"upload failed ({exc.code}): {detail}") from None
    print(result["url"])


if __name__ == "__main__":
    main()
'''


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY,
          slug TEXT UNIQUE NOT NULL,
          title TEXT NOT NULL,
          html TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comments (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          start_offset INTEGER NOT NULL,
          end_offset INTEGER NOT NULL,
          quote TEXT NOT NULL,
          body TEXT NOT NULL,
          author TEXT NOT NULL DEFAULT 'Anonymous',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS replies (
          id INTEGER PRIMARY KEY,
          comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
          body TEXT NOT NULL,
          author TEXT NOT NULL DEFAULT 'Anonymous',
          created_at TEXT NOT NULL
        );
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(comments)")}
    for name, definition in {
        "prefix": "TEXT NOT NULL DEFAULT ''",
        "suffix": "TEXT NOT NULL DEFAULT ''",
        "orphaned": "INTEGER NOT NULL DEFAULT 0",
        "resolved": "INTEGER NOT NULL DEFAULT 0",
        "resolved_at": "TEXT",
    }.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE comments ADD COLUMN {name} {definition}")
    conn.commit()
    return conn


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "document"


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text(html):
    parser = VisibleTextParser()
    parser.feed(html)
    return "".join(parser.parts)


def common_prefix(a, b):
    size = 0
    for left, right in zip(a, b):
        if left != right:
            break
        size += 1
    return size


def reanchor_comments(conn, document_id, old_html, new_html):
    old_text, new_text = visible_text(old_html), visible_text(new_html)
    comments = conn.execute("SELECT * FROM comments WHERE document_id=?", (document_id,)).fetchall()
    reanchored = orphaned = 0
    for comment in comments:
        quote = comment["quote"]
        positions, cursor = [], 0
        while True:
            cursor = new_text.find(quote, cursor)
            if cursor < 0:
                break
            positions.append(cursor)
            cursor += max(1, len(quote))
        prefix = comment["prefix"] or old_text[max(0, comment["start_offset"] - 64):comment["start_offset"]]
        suffix = comment["suffix"] or old_text[comment["end_offset"]:comment["end_offset"] + 64]
        selected = None
        if len(positions) == 1:
            selected = positions[0]
        elif positions:
            scored = []
            for position in positions:
                before = new_text[max(0, position - len(prefix)):position]
                after = new_text[position + len(quote):position + len(quote) + len(suffix)]
                score = common_prefix(prefix[::-1], before[::-1]) + common_prefix(suffix, after)
                scored.append((score, position))
            scored.sort(reverse=True)
            if len(scored) == 1 or scored[0][0] > scored[1][0]:
                selected = scored[0][1]
        if selected is None:
            conn.execute("UPDATE comments SET orphaned=1 WHERE id=?", (comment["id"],))
            orphaned += 1
        else:
            end = selected + len(quote)
            conn.execute(
                "UPDATE comments SET start_offset=?,end_offset=?,prefix=?,suffix=?,orphaned=0 WHERE id=?",
                (selected, end, new_text[max(0, selected - 64):selected], new_text[end:end + 64], comment["id"]),
            )
            reanchored += 1
    return {"comments_reanchored": reanchored, "comments_orphaned": orphaned}


def password_ok(value):
    configured = os.environ.get("QUOMODOC_UPLOAD_PASSWORD_SHA256", "")
    candidate = hashlib.sha256((value or "").encode()).hexdigest()
    return bool(configured) and hmac.compare_digest(candidate, configured)


def document_or_404(slug):
    conn = db()
    doc = conn.execute("SELECT * FROM documents WHERE slug=?", (slug,)).fetchone()
    conn.close()
    if not doc:
        abort(404)
    return doc


SHELL_STYLE = """
@font-face{font-family:IBMPlexSans;src:url(/quomodoc/assets/ibm-plex-sans.woff2) format(woff2);font-style:normal;font-weight:400 700;font-display:swap}
:root{--ink:#17202a;--muted:#697386;--line:#d9dee7;--paper:#fff;--accent:#3757d5;--mark:#ffe88b}
*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:var(--ink);font:15px/1.5 IBMPlexSans,sans-serif}
a{color:var(--accent)}header{height:58px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:16px;padding:0 22px;position:sticky;top:0;z-index:20}.brand{display:inline-flex;align-items:center;gap:8px;font-weight:750;font-size:18px;text-decoration:none;color:var(--ink)}.brand img{width:31px;height:31px;display:block}.spacer{flex:1}.button,button{border:0;border-radius:8px;background:var(--accent);color:#fff;padding:9px 14px;font-weight:650;cursor:pointer;text-decoration:none}.secondary{background:#edf0f7;color:#24324a}.container{max-width:1080px;margin:32px auto;padding:0 22px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}.card{display:block;background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px;text-decoration:none;color:inherit;box-shadow:0 2px 8px #17202a0a}.card:hover{border-color:#aeb9d0}.card h2{margin:0 0 7px;font-size:18px}.meta{color:var(--muted);font-size:13px}.empty{background:#fff;border:1px dashed #bbc3d1;border-radius:12px;padding:44px;text-align:center;color:var(--muted)}dialog{border:0;border-radius:14px;box-shadow:0 20px 70px #17202a44;width:min(560px,calc(100vw - 30px));padding:0}dialog::backdrop{background:#17202a88}.dialog-body{padding:22px}.dialog-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:18px}label{display:block;font-weight:650;margin:12px 0 5px}input,textarea{width:100%;border:1px solid #b9c1cf;border-radius:8px;padding:10px;font:inherit}.reader{height:calc(100dvh - 58px);display:grid;grid-template-columns:minmax(0,1fr) 330px}.viewport{padding:20px;background:#dfe3e9;min-width:0}.viewport iframe{width:100%;height:100%;border:1px solid #c4cad5;border-radius:8px;background:#fff;box-shadow:0 3px 16px #17202a18}.sidebar{background:#fff;border-left:1px solid var(--line);overflow:auto;padding:18px}.sidebar h2{font-size:17px;margin:0 0 12px}.hint{color:var(--muted);font-size:13px}.comment{border:1px solid var(--line);border-radius:9px;padding:11px;margin:10px 0;cursor:pointer}.comment:hover{border-color:#9aa8c4}.quote{font-size:13px;color:#5f6776;border-left:3px solid #e2c33f;padding-left:8px;margin-bottom:7px}.comment-body{white-space:pre-wrap}.comment-meta{color:var(--muted);font-size:11px;margin-top:7px}.selectionbar{display:none;position:fixed;z-index:50;background:#17202a;color:#fff;border-radius:9px;padding:9px 14px;box-shadow:0 5px 20px #0005;cursor:pointer;font-weight:650}@media(max-width:760px){.reader{display:block;height:auto}.viewport{height:62dvh;padding:10px}.sidebar{border-left:0;border-top:1px solid var(--line);min-height:38dvh}.hide-mobile{display:none}.selectionbar{left:50%!important;right:auto;top:auto!important;bottom:max(18px,env(safe-area-inset-bottom));transform:translateX(-50%)}}
.comment.resolved{opacity:.62;background:#f7f8fa}.comment.orphaned{border-color:#e09a52}.comment-actions{display:flex;gap:6px;margin-top:9px}.comment-actions button,.reply-form button{padding:5px 8px;font-size:12px}.badge{display:inline-block;border-radius:99px;padding:2px 7px;margin:0 0 7px;font-size:11px;font-weight:700;background:#fff0de;color:#8a4b08}.reply-list{margin:10px 0 0 12px;border-left:2px solid var(--line);padding-left:10px}.reply{margin:8px 0}.reply-body{white-space:pre-wrap;font-size:13px}.reply-form{display:none;margin-top:9px}.reply-form.open{display:block}.reply-form input,.reply-form textarea{margin:4px 0;font-size:13px}.focus-link{white-space:nowrap}.open-count{font-weight:400;color:var(--muted);font-size:12px}@media(max-width:760px){.doc-title{display:none}.focus-link{padding:7px 9px}}
"""


HOME = """
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quomodoc</title><link rel="icon" type="image/svg+xml" href="{{base}}/assets/quomodoc-mark.svg"><style>{{style}}</style></head>
<body><header><a class="brand" href="{{base}}/"><img src="{{base}}/assets/quomodoc-mark.svg" alt="">Quomodoc</a><span class="meta">HTML documents with anchored comments</span><span class="spacer"></span><button onclick="upload.showModal()">Upload HTML</button></header>
<main class="container"><h1>Documents</h1>
{% if docs %}<div class="grid">{% for d in docs %}<a class="card" href="{{base}}/docs/{{d.slug}}"><h2>{{d.title}}</h2><div class="meta">{{d.comment_count}} comment{{'' if d.comment_count == 1 else 's'}} · updated {{d.updated_at[:10]}}</div></a>{% endfor %}</div>{% else %}<div class="empty">No documents yet. Upload an HTML file to begin reviewing.</div>{% endif %}</main>
<dialog id="upload"><form class="dialog-body" method="post" action="{{base}}/upload" enctype="multipart/form-data"><h2>Upload a document</h2><label>Title</label><input name="title" required><label>Slug</label><input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="optional-url-slug"><label>HTML file</label><input name="file" type="file" accept="text/html,.html,.htm" required><label>Upload password</label><input name="password" type="password" required><div class="dialog-actions"><button type="button" class="secondary" onclick="upload.close()">Cancel</button><button type="submit">Upload</button></div></form></dialog>
</body></html>
"""


READER = """
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{doc.title}} · Quomodoc</title><link rel="icon" type="image/svg+xml" href="{{base}}/assets/quomodoc-mark.svg"><style>{{style}}</style></head>
<body><header><a class="brand" href="{{base}}/"><img src="{{base}}/assets/quomodoc-mark.svg" alt="">Quomodoc</a><strong class="doc-title">{{doc.title}}</strong><span class="spacer"></span><span class="meta hide-mobile">Select text to comment</span><a class="button secondary focus-link" href="{{base}}/raw/{{doc.slug}}" target="_blank" rel="noopener">Focus ↗</a></header>
<main class="reader"><section class="viewport"><iframe id="docframe" sandbox="allow-same-origin" src="{{base}}/raw/{{doc.slug}}"></iframe></section><aside class="sidebar"><h2>Comments <span id="count" class="open-count"></span></h2><p class="hint">Highlight text in the document, then choose “Comment”.</p><div id="comments"></div></aside></main><button id="selectionbar" class="selectionbar">Comment</button>
<dialog id="commentDialog"><form id="commentForm" class="dialog-body"><h2>Add comment</h2><div id="selectedQuote" class="quote"></div><label>Name</label><input id="author" value="Anonymous" maxlength="80"><label>Comment</label><textarea id="body" rows="5" maxlength="5000" required></textarea><div class="dialog-actions"><button type="button" class="secondary" onclick="commentDialog.close()">Cancel</button><button type="submit">Save</button></div></form></dialog>
<script>
const BASE={{base|tojson}}, SLUG={{doc.slug|tojson}};
let comments={{comments|tojson}}, pending=null;
const frame=document.getElementById('docframe'), bar=document.getElementById('selectionbar');
function textNodes(root){const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement&&!["SCRIPT","STYLE","NOSCRIPT"].includes(n.parentElement.tagName)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT});let out=[],n;while(n=w.nextNode())out.push(n);return out}
function absoluteRange(range){let total=0,start=null,end=null;for(const n of textNodes(frame.contentDocument.body)){if(n===range.startContainer)start=total+range.startOffset;if(n===range.endContainer)end=total+range.endOffset;total+=n.data.length}return start!==null&&end!==null?{start,end}:null}
function applyHighlights(){const doc=frame.contentDocument;doc.querySelectorAll('mark[data-quomodoc]').forEach(m=>m.replaceWith(...m.childNodes));const nodes=textNodes(doc.body),items=comments.filter(c=>!c.orphaned).sort((a,b)=>b.start_offset-a.start_offset);for(const c of items){let total=0,sn=null,en=null,so=0,eo=0;for(const n of nodes){const next=total+n.data.length;if(sn===null&&c.start_offset>=total&&c.start_offset<=next){sn=n;so=c.start_offset-total}if(c.end_offset>=total&&c.end_offset<=next){en=n;eo=c.end_offset-total;break}total=next}if(sn&&en){try{const r=doc.createRange();r.setStart(sn,so);r.setEnd(en,eo);const mark=doc.createElement('mark');mark.dataset.quomodoc=c.id;mark.style.cssText=`background:${c.resolved?'#dce1e8':'#ffe88b'};color:inherit;cursor:pointer`;r.surroundContents(mark);mark.onclick=()=>document.getElementById('comment-'+c.id)?.scrollIntoView({behavior:'smooth'})}catch(e){}}}}
function textEl(cls,text){const el=document.createElement('div');el.className=cls;el.textContent=text;return el}
function renderComments(){const box=document.getElementById('comments');box.innerHTML='';comments.sort((a,b)=>Number(a.resolved)-Number(b.resolved)||a.id-b.id).forEach(c=>{const el=document.createElement('div');el.className='comment'+(c.resolved?' resolved':'')+(c.orphaned?' orphaned':'');el.id='comment-'+c.id;if(c.orphaned)el.appendChild(textEl('badge','Needs re-anchoring'));el.appendChild(textEl('quote','“'+c.quote+'”'));el.appendChild(textEl('comment-body',c.body));el.appendChild(textEl('comment-meta',c.author+' · '+c.created_at.replace('T',' ').slice(0,16)+' UTC'));const replies=document.createElement('div');replies.className='reply-list';(c.replies||[]).forEach(r=>{const item=document.createElement('div');item.className='reply';item.appendChild(textEl('reply-body',r.body));item.appendChild(textEl('comment-meta',r.author+' · '+r.created_at.replace('T',' ').slice(0,16)+' UTC'));replies.appendChild(item)});if((c.replies||[]).length)el.appendChild(replies);const actions=document.createElement('div');actions.className='comment-actions';const resolve=document.createElement('button');resolve.className='secondary';resolve.textContent=c.resolved?'Reopen':'Resolve';resolve.onclick=async e=>{e.stopPropagation();const res=await fetch(`${BASE}/api/comments/${c.id}/resolve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({resolved:!c.resolved})});if(!res.ok)return alert(await res.text());Object.assign(c,await res.json());renderComments();applyHighlights()};const reply=document.createElement('button');reply.className='secondary';reply.textContent='Reply';actions.append(resolve,reply);el.appendChild(actions);const form=document.createElement('form');form.className='reply-form';const name=document.createElement('input');name.placeholder='Name';name.value='Anonymous';name.maxLength=80;const body=document.createElement('textarea');body.placeholder='Reply';body.rows=2;body.maxLength=5000;body.required=true;const submit=document.createElement('button');submit.type='submit';submit.textContent='Add reply';form.append(name,body,submit);reply.onclick=e=>{e.stopPropagation();form.classList.toggle('open');if(form.classList.contains('open'))body.focus()};form.onclick=e=>e.stopPropagation();form.onsubmit=async e=>{e.preventDefault();const res=await fetch(`${BASE}/api/comments/${c.id}/replies`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({author:name.value,body:body.value})});if(!res.ok)return alert(await res.text());(c.replies||(c.replies=[])).push(await res.json());renderComments()};el.appendChild(form);el.onclick=e=>{if(!c.orphaned&&!e.target.closest('button,input,textarea'))frame.contentDocument.querySelector(`mark[data-quomodoc="${c.id}"]`)?.scrollIntoView({behavior:'smooth',block:'center'})};box.appendChild(el)});const open=comments.filter(c=>!c.resolved).length;document.getElementById('count').textContent=`${open} open · ${comments.length} total`}
function captureSelection(){const doc=frame.contentDocument,sel=doc.getSelection();if(!sel||sel.isCollapsed){bar.style.display='none';return}const quote=sel.toString().trim();if(!quote)return;const range=sel.getRangeAt(0),pos=absoluteRange(range);if(!pos)return;const all=textNodes(doc.body).map(n=>n.data).join('');pending={...pos,quote,prefix:all.slice(Math.max(0,pos.start-64),pos.start),suffix:all.slice(pos.end,pos.end+64)};if(!matchMedia('(max-width:760px)').matches){const rect=frame.getBoundingClientRect(),r=range.getBoundingClientRect();bar.style.left=Math.min(window.innerWidth-105,rect.left+r.left+r.width/2-42)+'px';bar.style.top=Math.max(65,rect.top+r.top-42)+'px'}bar.style.display='block'}
frame.addEventListener('load',()=>{applyHighlights();const doc=frame.contentDocument;doc.addEventListener('mouseup',captureSelection);doc.addEventListener('touchend',()=>setTimeout(captureSelection,120),{passive:true});doc.addEventListener('selectionchange',()=>setTimeout(captureSelection,80))});
bar.onclick=()=>{if(!pending)return;document.getElementById('selectedQuote').textContent='“'+pending.quote+'”';bar.style.display='none';commentDialog.showModal();document.getElementById('body').focus()};
document.getElementById('commentForm').onsubmit=async e=>{e.preventDefault();const payload={...pending,body:document.getElementById('body').value,author:document.getElementById('author').value};const res=await fetch(`${BASE}/api/documents/${SLUG}/comments`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!res.ok){alert(await res.text());return}comments.push(await res.json());renderComments();applyHighlights();document.getElementById('body').value='';commentDialog.close()};renderComments();
</script></body></html>
"""


@app.get(f"{BASE}/")
def home():
    conn = db()
    docs = conn.execute("""SELECT d.*, COUNT(c.id) comment_count FROM documents d LEFT JOIN comments c ON c.document_id=d.id GROUP BY d.id ORDER BY d.updated_at DESC""").fetchall()
    conn.close()
    return render_template_string(HOME, docs=docs, style=SHELL_STYLE, base=BASE)


@app.get(BASE)
def base_redirect():
    return redirect(f"{BASE}/")


@app.get(f"{BASE}/docs/<slug>")
def reader(slug):
    doc = document_or_404(slug)
    conn = db()
    comments = []
    for row in conn.execute("SELECT * FROM comments WHERE document_id=? ORDER BY resolved,id", (doc["id"],)):
        comment = dict(row)
        comment["replies"] = [dict(reply) for reply in conn.execute("SELECT * FROM replies WHERE comment_id=? ORDER BY id", (row["id"],))]
        comments.append(comment)
    conn.close()
    return render_template_string(READER, doc=doc, comments=comments, style=SHELL_STYLE, base=BASE)


@app.get(f"{BASE}/raw/<slug>")
def raw(slug):
    doc = document_or_404(slug)
    response = Response(doc["html"], content_type="text/html; charset=utf-8")
    # Quarto's self-contained output stores its stylesheets in data: URLs.
    # Permit only the exact audited KaTeX 0.16.22 bundle and Quarto renderer
    # used by trusted paper exports; all other uploaded JavaScript stays inert.
    katex_hash = "'sha256-QMvK7j+MFv6mQ7oISjOASkqwF2cjuG4bzXuAS3mDZsw='"
    katex_renderer_hash = "'sha256-67kRF6ir7uYcntligDJr9ckJ39fnGm98n5gLaDW7/a8='"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'unsafe-inline' data: https:; "
        "img-src data: https:; font-src data: https:; media-src https:; "
        f"script-src {katex_hash} {katex_renderer_hash}; "
        "connect-src 'none'; form-action 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def save_document(title, slug, html):
    if not title.strip() or not html.strip():
        abort(400, "title and html are required")
    slug = slugify(slug or title)
    if not SLUG_RE.fullmatch(slug):
        abort(400, "invalid slug")
    stamp = now()
    conn = db()
    existing = conn.execute("SELECT * FROM documents WHERE slug=?", (slug,)).fetchone()
    if existing:
        stats = reanchor_comments(conn, existing["id"], existing["html"], html)
        conn.execute(
            "UPDATE documents SET title=?,html=?,updated_at=? WHERE id=?",
            (title.strip(), html, stamp, existing["id"]),
        )
        conn.commit()
        conn.close()
        return {"slug": slug, "created": False, **stats}
    else:
        conn.execute("INSERT INTO documents(slug,title,html,created_at,updated_at) VALUES(?,?,?,?,?)", (slug, title.strip(), html, stamp, stamp))
        conn.commit()
    conn.close()
    return {"slug": slug, "created": True, "comments_reanchored": 0, "comments_orphaned": 0}


@app.post(f"{BASE}/upload")
def upload():
    if not password_ok(request.form.get("password")):
        abort(401, "invalid upload password")
    file = request.files.get("file")
    if not file:
        abort(400, "HTML file is required")
    html = file.read().decode("utf-8", errors="replace")
    result = save_document(request.form.get("title", ""), request.form.get("slug", ""), html)
    return redirect(f"{BASE}/docs/{result['slug']}")


@app.post(f"{BASE}/api/documents")
def api_upload():
    data = request.get_json(silent=True) or request.form
    if not password_ok(data.get("password")):
        return jsonify(error="invalid upload password"), 401
    if request.files.get("file"):
        html = request.files["file"].read().decode("utf-8", errors="replace")
    else:
        html = data.get("html", "")
    result = save_document(data.get("title", ""), data.get("slug", ""), html)
    result["url"] = f"https://lalten.org{BASE}/docs/{result['slug']}"
    return jsonify(result), 201 if result["created"] else 200


@app.post(f"{BASE}/api/documents/<slug>/comments")
def add_comment(slug):
    doc = document_or_404(slug)
    data = request.get_json(force=True)
    try:
        start, end = int(data["start"]), int(data["end"])
    except (KeyError, TypeError, ValueError):
        abort(400, "invalid text offsets")
    quote, body = str(data.get("quote", "")).strip(), str(data.get("body", "")).strip()
    prefix, suffix = str(data.get("prefix", ""))[-64:], str(data.get("suffix", ""))[:64]
    author = str(data.get("author", "Anonymous")).strip()[:80] or "Anonymous"
    if start < 0 or end <= start or not quote or not body or len(body) > 5000:
        abort(400, "invalid comment")
    stamp = now()
    conn = db()
    cur = conn.execute("INSERT INTO comments(document_id,start_offset,end_offset,quote,body,author,created_at,prefix,suffix) VALUES(?,?,?,?,?,?,?,?,?)", (doc["id"], start, end, quote[:1000], body, author, stamp, prefix, suffix))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM comments WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    row["replies"] = []
    return jsonify(row), 201


@app.post(f"{BASE}/api/comments/<int:comment_id>/resolve")
def resolve_comment(comment_id):
    data = request.get_json(force=True)
    resolved = data.get("resolved")
    if not isinstance(resolved, bool):
        abort(400, "resolved must be a boolean")
    conn = db()
    if not conn.execute("SELECT 1 FROM comments WHERE id=?", (comment_id,)).fetchone():
        conn.close()
        abort(404)
    resolved_at = now() if resolved else None
    conn.execute("UPDATE comments SET resolved=?,resolved_at=? WHERE id=?", (int(resolved), resolved_at, comment_id))
    conn.commit()
    conn.close()
    return jsonify(id=comment_id, resolved=resolved, resolved_at=resolved_at)


@app.post(f"{BASE}/api/comments/<int:comment_id>/replies")
def add_reply(comment_id):
    data = request.get_json(force=True)
    body = str(data.get("body", "")).strip()
    author = str(data.get("author", "Anonymous")).strip()[:80] or "Anonymous"
    if not body or len(body) > 5000:
        abort(400, "invalid reply")
    stamp = now()
    conn = db()
    if not conn.execute("SELECT 1 FROM comments WHERE id=?", (comment_id,)).fetchone():
        conn.close()
        abort(404)
    cur = conn.execute("INSERT INTO replies(comment_id,body,author,created_at) VALUES(?,?,?,?)", (comment_id, body, author, stamp))
    conn.commit()
    row = dict(conn.execute("SELECT * FROM replies WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return jsonify(row), 201


@app.get(f"{BASE}/api/documents")
def api_list():
    conn = db()
    rows = [dict(r) for r in conn.execute("SELECT slug,title,created_at,updated_at FROM documents ORDER BY updated_at DESC")]
    conn.close()
    return jsonify(rows)


@app.get(f"{BASE}/health")
def health():
    return jsonify(status="ok")


@app.get(f"{BASE}/assets/ibm-plex-sans.woff2")
def ibm_plex_sans():
    return send_file(ROOT / "ibm-plex-sans.woff2", mimetype="font/woff2", max_age=31536000)


@app.get(f"{BASE}/assets/quomodoc-mark.svg")
def quomodoc_mark():
    return send_file(ROOT / "quomodoc-mark.svg", mimetype="image/svg+xml", max_age=31536000)


@app.get(f"{BASE}/cli")
def download_cli():
    response = Response(UPLOAD_CLI, content_type="text/x-python; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="quomodoc-upload.py"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.errorhandler(413)
def too_large(_):
    return "HTML file exceeds 20 MiB", 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8761)
