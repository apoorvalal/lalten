import json
import os
from datetime import date, datetime

import pandas as pd
import streamlit as st
from dateutil import tz
from jinja2 import Template

import bobocal_db as db

LOCAL_TZ = tz.gettz(os.environ.get("TZ", "America/Los_Angeles"))

DEFAULT_OBSIDIAN_BASE = "/Users/alal/Documents/PersonalVault/KrabbiePatties"


def obsidian_path_for_day(day: str) -> str:
    base = os.environ.get("BOBOCAL_OBSIDIAN_BASE", DEFAULT_OBSIDIAN_BASE)
    fname = f"Bobo diary {day}.md"
    return os.path.join(base, fname)


def parse_hhmm(s: str):
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        return None


def offset_minutes(scheduled: str, actual: str):
    stt = parse_hhmm(scheduled)
    act = parse_hhmm(actual)
    if not stt or not act:
        return None
    # Same-day assumption; if you need overnight, adjust later.
    d0 = datetime(2000, 1, 1, stt.hour, stt.minute)
    d1 = datetime(2000, 1, 1, act.hour, act.minute)
    return int((d1 - d0).total_seconds() // 60)


def fmt_offset(mins):
    if mins is None:
        return ""
    sign = "+" if mins > 0 else ""
    return f"{sign}{mins}m"


def load_template_rows(conn):
    rows = conn.execute(
        "SELECT id, sort_order, label, scheduled_time FROM schedule_template ORDER BY sort_order"
    ).fetchall()
    return [dict(r) for r in rows]


def load_daily(conn, day: str):
    template = load_template_rows(conn)
    actual_rows = conn.execute(
        "SELECT template_id, actual_time, notes FROM daily_actual WHERE day=?",
        (day,),
    ).fetchall()
    actual_map = {r["template_id"]: dict(r) for r in actual_rows}

    out = []
    for trow in template:
        a = actual_map.get(trow["id"], {})
        actual = a.get("actual_time")
        mins = offset_minutes(trow["scheduled_time"], actual) if actual else None
        out.append(
            {
                "template_id": trow["id"],
                "sort_order": trow["sort_order"],
                "label": trow["label"],
                "scheduled_time": trow["scheduled_time"],
                "actual_time": actual,
                "notes": a.get("notes") or "",
                "offset_min": mins,
                "offset_str": fmt_offset(mins),
            }
        )
    return out


def load_night_feeds(conn, day: str):
    rows = conn.execute(
        "SELECT id, feed_time, amount, notes FROM night_feed WHERE day=? ORDER BY feed_time, id",
        (day,),
    ).fetchall()
    return [dict(r) for r in rows]


def set_setting(conn, key: str, value: str):
    conn.execute(
        "INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_setting(conn, key: str, default: str = ""):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def render_markdown(day: str, schedule, night_feeds, md_template: str) -> str:
    t = Template(md_template)
    return t.render(day=day, schedule=schedule, night_feeds=night_feeds)


st.set_page_config(page_title="bobocal", page_icon="🗓️", layout="wide")

st.title("bobocal")

# Light auto-refresh for "live" offsets when entering times
st.autorefresh(interval=30_000, key="autorefresh")

with db.connect() as conn:
    db.init_db()

st.sidebar.header("Date")
selected_day = st.sidebar.date_input("Day", value=date.today())
day = selected_day.isoformat()

colA, colB = st.columns([2, 1])

with colA:
    st.subheader(f"Daily view — {day}")

with colB:
    st.subheader("Archive")

with db.connect() as conn:
    schedule = load_daily(conn, day)

# Schedule editor grid
st.markdown("### Schedule")

df = pd.DataFrame(
    [
        {
            "Label": r["label"],
            "Scheduled": r["scheduled_time"],
            "Actual": r["actual_time"] or "",
            "Offset": r["offset_str"],
            "Notes": r["notes"],
            "_template_id": r["template_id"],
        }
        for r in schedule
    ]
)

edited = st.data_editor(
    df.drop(columns=["_template_id"]),
    use_container_width=True,
    num_rows="fixed",
    key="daily_editor",
)

# Persist any edits to Actual/Notes
if st.button("Save daily changes", type="primary"):
    with db.connect() as conn:
        template_rows = load_template_rows(conn)
        by_label = {r["label"]: r for r in template_rows}
        # Use row order to map by schedule order
        for i, row in edited.iterrows():
            template_id = schedule[i]["template_id"]
            actual = str(row.get("Actual") or "").strip()
            notes = str(row.get("Notes") or "").strip()
            if actual == "":
                conn.execute(
                    "DELETE FROM daily_actual WHERE day=? AND template_id=?",
                    (day, template_id),
                )
            else:
                if parse_hhmm(actual) is None:
                    st.error(f"Invalid time HH:MM in row {i+1}: {actual}")
                    st.stop()
                conn.execute(
                    "INSERT INTO daily_actual(day,template_id,actual_time,notes) VALUES (?,?,?,?)\n                     ON CONFLICT(day,template_id) DO UPDATE SET actual_time=excluded.actual_time, notes=excluded.notes",
                    (day, template_id, actual, notes),
                )
    st.success("Saved")
    st.rerun()

with st.expander("Edit template schedule (global)"):
    with db.connect() as conn:
        template_rows = load_template_rows(conn)
    tdf = pd.DataFrame(template_rows)
    tdf = tdf[["sort_order", "label", "scheduled_time", "id"]].rename(columns={"id": "_id"})
    tedit = st.data_editor(
        tdf.drop(columns=["_id"]),
        use_container_width=True,
        num_rows="dynamic",
        key="template_editor",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Save template"):
            # Validate
            clean = []
            for i, row in tedit.iterrows():
                label = str(row.get("label") or "").strip()
                sch = str(row.get("scheduled_time") or "").strip()
                so = int(row.get("sort_order") or (i + 1))
                if not label:
                    st.error(f"Missing label at row {i+1}")
                    st.stop()
                if parse_hhmm(sch) is None:
                    st.error(f"Invalid scheduled_time HH:MM at row {i+1}: {sch}")
                    st.stop()
                clean.append((so, label, sch))

            with db.connect() as conn:
                conn.execute("DELETE FROM schedule_template")
                conn.executemany(
                    "INSERT INTO schedule_template(sort_order,label,scheduled_time) VALUES (?,?,?)",
                    clean,
                )
            st.success("Template saved")
            st.rerun()

    with col2:
        st.caption("Edits apply to all days. After changes, return to Daily view and save actuals.")

st.markdown("### Night feeds")
with db.connect() as conn:
    feeds = load_night_feeds(conn, day)

fcol1, fcol2, fcol3, fcol4 = st.columns([1, 1, 2, 1])
with fcol1:
    feed_time = st.text_input("Time (HH:MM)", value="", key="nf_time")
with fcol2:
    amount = st.text_input("Amount", value="", key="nf_amount")
with fcol3:
    feed_notes = st.text_input("Notes", value="", key="nf_notes")
with fcol4:
    if st.button("Add feed"):
        if parse_hhmm(feed_time) is None:
            st.error("Invalid time. Use HH:MM")
        else:
            with db.connect() as conn:
                conn.execute(
                    "INSERT INTO night_feed(day,feed_time,amount,notes) VALUES (?,?,?,?)",
                    (day, feed_time.strip(), amount.strip() or None, feed_notes.strip() or None),
                )
            st.rerun()

if feeds:
    fdf = pd.DataFrame(feeds)
    fdf = fdf[["feed_time", "amount", "notes"]]
    st.dataframe(fdf, use_container_width=True, hide_index=True)
else:
    st.caption("No night feeds yet")

st.markdown("### Markdown template")
with db.connect() as conn:
    md_template = get_setting(conn, "md_template")
md_template_new = st.text_area("Obsidian note template (Jinja2)", value=md_template, height=240)
if st.button("Save markdown template"):
    with db.connect() as conn:
        set_setting(conn, "md_template", md_template_new)
    st.success("Template saved")

st.markdown("---")

with colB:
    st.write("On archive: writes snapshot to sqlite + generates an Obsidian markdown note.")
    obs_path = obsidian_path_for_day(day)
    st.code(obs_path)

    if st.button("Archive day", type="secondary"):
        with db.connect() as conn:
            schedule_now = load_daily(conn, day)
            feeds_now = load_night_feeds(conn, day)
            md_template = get_setting(conn, "md_template")

            md = render_markdown(day, schedule_now, feeds_now, md_template)
            md_path = obs_path

            # Write MD file
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md)

            payload = {"day": day, "schedule": schedule_now, "night_feeds": feeds_now}
            conn.execute(
                "INSERT INTO archive_log(day, md_path, payload_json) VALUES (?,?,?)",
                (day, md_path, json.dumps(payload, ensure_ascii=False)),
            )

        st.success(f"Archived. Wrote: {md_path}")
