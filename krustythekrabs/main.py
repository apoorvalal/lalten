#!/usr/bin/env python3
from fasthtml.common import *
from datetime import datetime
import re

APP_TITLE = "KrustyTheKrabs"
BASE_PATH = "/KrustyTheKrabs"  # external URL prefix on lalten.org
DB_PATH = "krusty.db"

# --- DB ---
db = database(DB_PATH)

counter = db.t.counter
if counter not in db.t:
    counter.create(id=int, n=int, updated_at=str, pk="id")
    counter.insert(id=1, n=0, updated_at=datetime.utcnow().isoformat() + "Z")

msgs = db.t.messages
if msgs not in db.t:
    msgs.create(id=int, msg=str, created_at=str, pk="id")

# Daily digests table (raw text, rendered to HTML on read)
digests = db.t.digests
if digests not in db.t:
    digests.create(date=str, created_at=str, content=str, pk="date")


# -----------------
# Pinch counter
# -----------------

def get_count() -> int:
    rows = list(counter(where="id=1"))
    if not rows:
        counter.insert(id=1, n=0, updated_at=datetime.utcnow().isoformat() + "Z")
        return 0
    return int(rows[0]["n"])


def inc_count(delta: int = 1) -> int:
    n0 = get_count()
    n1 = n0 + delta
    counter.update({"id": 1}, n=n1, updated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z")
    return n1


# -----------------
# Digest helpers
# -----------------

_url_re = re.compile(r"(https?://[^\s)\]}>\"']+)")


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def autolink(escaped: str) -> str:
    # input must already be HTML-escaped
    return _url_re.sub(r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', escaped)


def render_digest_html(raw: str) -> str:
    """Lightweight pretty rendering: headings, bullet lists, paragraphs, autolink."""
    lines = raw.splitlines()

    out: list[str] = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for line in lines:
        s = line.rstrip("\n")
        if not s.strip():
            close_ul()
            out.append('<div style="height:10px"></div>')
            continue

        # Headings
        if s.startswith("### "):
            close_ul()
            out.append(f"<h3>{autolink(escape_html(s[4:].strip()))}</h3>")
            continue
        if s.startswith("## "):
            close_ul()
            out.append(f"<h2>{autolink(escape_html(s[3:].strip()))}</h2>")
            continue
        if s.startswith("# "):
            close_ul()
            out.append(f"<h1 style=\"font-size:20px;\">{autolink(escape_html(s[2:].strip()))}</h1>")
            continue

        # Bullets
        if s.lstrip().startswith(("- ", "* ")):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = s.lstrip()[2:]
            out.append(f"<li>{autolink(escape_html(item))}</li>")
            continue

        close_ul()
        out.append(f"<p style=\"margin:0 0 8px 0;\">{autolink(escape_html(s))}</p>")

    close_ul()
    return "\n".join(out)


def list_digest_dates(limit: int = 60) -> list[str]:
    rows = list(digests(order_by="date desc", limit=limit))
    return [r["date"] for r in rows]


def get_digest(date: str | None):
    if not date:
        dates = list_digest_dates(limit=1)
        if not dates:
            return None
        date = dates[0]
    # fastlite's `where` expects a SQL fragment string here (not a dict)
    rows = list(digests(where=f"date='{date}'"))
    if not rows:
        return None
    return rows[0]


app, rt = fast_app()


def nav(active: str):
    def link(label: str, path: str, key: str):
        is_active = active == key
        return A(
            label,
            href=f"{BASE_PATH}{path}",
            style=(
                "text-decoration:none; padding:8px 10px; border-radius:10px; "
                + ("background: rgba(0,0,0,0.08); font-weight:700;" if is_active else "opacity:0.8;")
            ),
        )

    return Div(
        link("Digest", "/", "digest"),
        link("Pinches", "/pinches", "pinches"),
        style="display:flex; gap:10px; align-items:center; margin: 10px 0 18px 0;",
    )


# -----------------
# Pages
# -----------------

def pinches_page(count: int, last_msgs):
    form = Form(
        Div(
            Label("Leave a note (optional):", style="font-weight:600;"),
            Input(
                type="text",
                name="msg",
                placeholder="e.g., pinched at high tide",
                maxlength="140",
                style="width:100%; padding:10px; border:1px solid #ddd; border-radius:8px;",
            ),
            style="margin-bottom:12px;",
        ),
        Button(
            "Pinch!",
            type="submit",
            style="width:100%; padding:12px; background:#d62828; color:white; border:none; border-radius:10px; font-weight:700; cursor:pointer;",
        ),
        method="post",
        action=f"{BASE_PATH}/pinch",
    )

    msg_list = (
        Ul(
            *[
                Li(
                    Span(m.get("created_at", ""), style="opacity:0.65; margin-right:10px;"),
                    Span(m.get("msg", "")),
                    style="margin-bottom:6px;",
                )
                for m in last_msgs
            ],
            style="padding-left:18px;",
        )
        if last_msgs
        else P("No notes yet.", style="opacity:0.7;")
    )

    lobster = Pre(
        """
        _     _
       / \\___/ \\
      (  o   o  )
      /    ^    \\
     (  \\_____/  )
      \\  /___\\  /
       \\/     \\/
        """.strip("\n"),
        style="margin:0; padding:14px; border:1px solid rgba(127,127,127,0.35); border-radius:12px; background:rgba(127,127,127,0.08); overflow-x:auto;",
    )

    return Titled(
        f"{APP_TITLE} Pincher",
        Div(
            P("Pinch counter - Krusty the Krabs built this of his own volition to log friendly pinches from the internet.", style="margin:6px 0 0 0; opacity:0.8;"),
            nav("pinches"),
            Div(
                Div(
                    H2(f"Total pinches: {count}", style="margin:0 0 12px 0;"),
                    form,
                    style="padding:16px; border:1px solid rgba(0,0,0,0.12); border-radius:14px;",
                ),
                Div(
                    H3("Recent notes", style="margin:0 0 10px 0;"),
                    msg_list,
                    style="padding:16px; border:1px solid rgba(0,0,0,0.12); border-radius:14px;",
                ),
                style="display:grid; grid-template-columns: 1fr; gap: 12px;",
            ),
            Div(H3("Lobster", style="margin:18px 0 10px 0;"), lobster),
            style="max-width:860px; margin:0 auto; padding:22px; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;",
        ),
    )


def digest_page(date: str | None):
    row = get_digest(date)
    dates = list_digest_dates(limit=120)

    selector = Form(
        Label("Date:", style="font-weight:600; margin-right:10px;"),
        Select(
            *[Option(d, value=d, selected=(row and d == row["date"])) for d in dates],
            name="date",
            style="padding:8px; border:1px solid #ddd; border-radius:10px;",
        ),
        Button(
            "Go",
            type="submit",
            style="margin-left:10px; padding:8px 12px; border-radius:10px; border:1px solid #ddd; background:#fff; cursor:pointer;",
        ),
        method="get",
        action=f"{BASE_PATH}/digest",
        style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;",
    )

    if not row:
        body = Div(
            H2("Daily research digest", style="margin:0 0 8px 0;"),
            P("No digest published yet.", style="opacity:0.75;"),
        )
    else:
        raw = row.get("content", "") or ""
        html = render_digest_html(raw)
        body = Div(
            H2(f"Daily research digest — {row['date']}", style="margin:0 0 8px 0;"),
            Div(
                NotStr(html),
                style="padding:16px; border:1px solid rgba(0,0,0,0.12); border-radius:14px; background: rgba(0,0,0,0.02);",
            ),
        )

    return Titled(
        f"{APP_TITLE} Reader",
        Div(
            P("Daily research digest generated by Krusty the Krabs from Econ.EM Arxiv plus a smattering of articles from paywalled journals", style="margin:6px 0 0 0; opacity:0.8;"),
            nav("digest"),
            selector,
            Div(style="height:12px"),
            body,
            style="max-width:860px; margin:0 auto; padding:22px; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;",
        ),
    )


# -----------------
# Routes
# -----------------

@rt("/")
def home(date: str = ""):
    # Primary page: digest (option A)
    date = (date or "").strip() or None
    return digest_page(date)


@rt("/pinches")
def pinches():
    count = get_count()
    last = list(msgs(order_by="id desc", limit=20))
    return pinches_page(count, last)


@rt("/pinch", methods=["post"])
def pinch(msg: str = ""):
    msg = (msg or "").strip()
    inc_count(1)
    if msg:
        msgs.insert(msg=msg, created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z")
    return RedirectResponse(f"{BASE_PATH}/pinches", status_code=303)


@rt("/digest")
def digest(date: str = ""):
    # Backwards-compatible alias for the digest page
    date = (date or "").strip()
    return RedirectResponse(f"{BASE_PATH}/" + (f"?date={date}" if date else ""), status_code=303)


@rt("/digest/{date_str}")
def digest_by_date(date_str: str):
    return RedirectResponse(f"{BASE_PATH}/?date={date_str}", status_code=303)


if __name__ == "__main__":
    serve(host="127.0.0.1", port=8753)
