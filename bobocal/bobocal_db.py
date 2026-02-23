import os
import sqlite3
from contextlib import contextmanager

DEFAULT_DB_PATH = "/root/lalten/data/bobocal.sqlite"


def get_db_path() -> str:
    return os.environ.get("BOBOCAL_DB_PATH", DEFAULT_DB_PATH)


@contextmanager
def connect():
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sort_order INTEGER NOT NULL,
                label TEXT NOT NULL,
                scheduled_time TEXT NOT NULL -- HH:MM (24h)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_actual (
                day TEXT NOT NULL, -- YYYY-MM-DD
                template_id INTEGER NOT NULL,
                actual_time TEXT, -- HH:MM
                notes TEXT,
                PRIMARY KEY (day, template_id),
                FOREIGN KEY (template_id) REFERENCES schedule_template(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS night_feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                feed_time TEXT NOT NULL, -- HH:MM
                amount TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS archive_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                md_path TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )

        # Seed default template if empty
        cur = conn.execute("SELECT COUNT(*) AS c FROM schedule_template")
        if cur.fetchone()["c"] == 0:
            defaults = [
                (1, "Wake", "07:00"),
                (2, "Feed", "07:30"),
                (3, "Nap 1", "09:00"),
                (4, "Feed", "11:00"),
                (5, "Nap 2", "12:30"),
                (6, "Feed", "14:30"),
                (7, "Nap 3", "16:00"),
                (8, "Bedtime", "19:30"),
            ]
            conn.executemany(
                "INSERT INTO schedule_template(sort_order,label,scheduled_time) VALUES (?,?,?)",
                defaults,
            )

        default_md_template = """
# Bobo diary {{ day }}

## Schedule

| Item | Scheduled | Actual | Offset |
|---|---:|---:|---:|
{% for row in schedule %}
| {{ row.label }} | {{ row.scheduled_time }} | {{ row.actual_time or "" }} | {{ row.offset_str }} |
{% endfor %}

## Night feeds

{% if night_feeds|length == 0 %}
- (none)
{% else %}
{% for f in night_feeds %}
- {{ f.feed_time }}{% if f.amount %} ({{ f.amount }}){% endif %}{% if f.notes %}: {{ f.notes }}{% endif %}
{% endfor %}
{% endif %}

## Notes

""".lstrip()

        conn.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
            ("md_template", default_md_template),
        )
