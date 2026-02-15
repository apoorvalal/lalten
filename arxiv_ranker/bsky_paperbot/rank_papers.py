import argparse
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

DEFAULT_DB_PATH = Path(__file__).with_name("paper_scores.db")


@dataclass
class RankedPost:
    uri: str
    created_at: datetime
    text: str
    paper_link: str
    like_count: int
    reply_count: int
    repost_count: int
    quote_count: int
    arxiv_key: str

    @property
    def engagement(self) -> int:
        return self.like_count + self.reply_count + self.repost_count + self.quote_count


@dataclass
class SyncStats:
    scanned_items: int = 0
    paper_posts_seen: int = 0
    log_rows_upserted: int = 0


def parse_iso_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError(f"Unsupported datetime type: {type(value)}")
    return dt.astimezone(timezone.utc)


def parse_date_utc(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def extract_title_and_authors(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", ""

    if lines[0].lower().startswith("arxiv") and len(lines) >= 2:
        title = lines[1]
    else:
        title = lines[0]

    authors = ""
    for line in lines:
        if line.lower().startswith("by "):
            authors = line[3:].strip()
            break
    return title, authors


def extract_link_from_record(record: object) -> Optional[str]:
    facets = getattr(record, "facets", None) or []
    for facet in facets:
        for feature in getattr(facet, "features", []) or []:
            uri = getattr(feature, "uri", None)
            if uri:
                return uri
    return None


def extract_link_from_embed(embed: object) -> Optional[str]:
    media = getattr(embed, "media", None) if embed else None
    external = getattr(media, "external", None) if media else None
    if external and getattr(external, "uri", None):
        return external.uri
    return None


def canonicalize_arxiv_key(raw_url: str) -> Optional[str]:
    if not raw_url:
        return None

    parsed = urlparse(raw_url.strip())
    host = (parsed.netloc or "").lower()
    if "arxiv.org" not in host:
        return None

    path = (parsed.path or "").strip("/")
    if not path:
        return None

    if path.startswith("abs/"):
        ident = path[4:]
    elif path.startswith("pdf/"):
        ident = path[4:]
        if ident.endswith(".pdf"):
            ident = ident[:-4]
    else:
        ident = path

    ident = ident.strip("/")
    if not ident:
        return None

    if "/" in ident:
        prefix, tail = ident.rsplit("/", 1)
        tail = re.sub(r"v\d+$", "", tail)
        ident = f"{prefix}/{tail}"
    else:
        ident = re.sub(r"v\d+$", "", ident)

    ident = ident.strip("/")
    if not ident:
        return None

    return ident.lower()


def canonical_arxiv_abs_url(arxiv_key: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_key}"


def open_db(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_score_log (
            actor TEXT NOT NULL,
            arxiv_key TEXT NOT NULL,
            post_uri TEXT NOT NULL,
            created_at TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            text TEXT NOT NULL,
            paper_link TEXT NOT NULL,
            like_count INTEGER NOT NULL,
            reply_count INTEGER NOT NULL,
            repost_count INTEGER NOT NULL,
            quote_count INTEGER NOT NULL,
            engagement INTEGER NOT NULL,
            PRIMARY KEY (actor, post_uri)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_log_actor_created
        ON paper_score_log(actor, created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_log_actor_arxiv
        ON paper_score_log(actor, arxiv_key)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_scores (
            actor TEXT NOT NULL,
            arxiv_key TEXT NOT NULL,
            paper_link TEXT NOT NULL,
            representative_post_uri TEXT NOT NULL,
            representative_created_at TEXT NOT NULL,
            text TEXT NOT NULL,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            like_count INTEGER NOT NULL,
            reply_count INTEGER NOT NULL,
            repost_count INTEGER NOT NULL,
            quote_count INTEGER NOT NULL,
            engagement INTEGER NOT NULL,
            mention_count INTEGER NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (actor, arxiv_key)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            actor TEXT PRIMARY KEY,
            latest_created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get_latest_synced_created_at(conn: sqlite3.Connection, actor: str) -> Optional[datetime]:
    row = conn.execute(
        "SELECT latest_created_at FROM sync_state WHERE actor = ?",
        (actor,),
    ).fetchone()
    if not row:
        return None
    return parse_iso_datetime(row["latest_created_at"])


def get_oldest_cached_created_at(conn: sqlite3.Connection, actor: str) -> Optional[datetime]:
    row = conn.execute(
        "SELECT MIN(created_at) AS min_created FROM paper_score_log WHERE actor = ?",
        (actor,),
    ).fetchone()
    min_created = row["min_created"] if row else None
    if not min_created:
        return None
    return parse_iso_datetime(min_created)


def set_latest_synced_created_at(conn: sqlite3.Connection, actor: str, created_at: datetime) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO sync_state(actor, latest_created_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(actor) DO UPDATE SET
            latest_created_at = excluded.latest_created_at,
            updated_at = excluded.updated_at
        """,
        (actor, created_at.isoformat(), now),
    )


def _upsert_log_row(conn: sqlite3.Connection, actor: str, post: RankedPost, fetched_at: datetime) -> int:
    before = conn.total_changes
    conn.execute(
        """
        INSERT INTO paper_score_log(
            actor, arxiv_key, post_uri, created_at, fetched_at, text, paper_link,
            like_count, reply_count, repost_count, quote_count, engagement
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(actor, post_uri) DO UPDATE SET
            arxiv_key = excluded.arxiv_key,
            created_at = excluded.created_at,
            fetched_at = excluded.fetched_at,
            text = excluded.text,
            paper_link = excluded.paper_link,
            like_count = excluded.like_count,
            reply_count = excluded.reply_count,
            repost_count = excluded.repost_count,
            quote_count = excluded.quote_count,
            engagement = excluded.engagement
        """,
        (
            actor,
            post.arxiv_key,
            post.uri,
            post.created_at.isoformat(),
            fetched_at.isoformat(),
            post.text,
            post.paper_link,
            post.like_count,
            post.reply_count,
            post.repost_count,
            post.quote_count,
            post.engagement,
        ),
    )
    return conn.total_changes - before


def _upsert_paper_scores_row(conn: sqlite3.Connection, actor: str, post: RankedPost) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    title, authors = extract_title_and_authors(post.text)
    row = conn.execute(
        """
        SELECT engagement, mention_count, first_seen_at, last_seen_at
        FROM paper_scores
        WHERE actor = ? AND arxiv_key = ?
        """,
        (actor, post.arxiv_key),
    ).fetchone()

    if not row:
        conn.execute(
            """
            INSERT INTO paper_scores(
                actor, arxiv_key, paper_link, representative_post_uri, representative_created_at,
                text, title, authors, like_count, reply_count, repost_count, quote_count,
                engagement, mention_count, first_seen_at, last_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                actor,
                post.arxiv_key,
                post.paper_link,
                post.uri,
                post.created_at.isoformat(),
                post.text,
                title,
                authors,
                post.like_count,
                post.reply_count,
                post.repost_count,
                post.quote_count,
                post.engagement,
                1,
                post.created_at.isoformat(),
                post.created_at.isoformat(),
                now_iso,
            ),
        )
        return

    prev_engagement = int(row["engagement"])
    mention_count = int(row["mention_count"]) + 1
    first_seen_at = min(row["first_seen_at"], post.created_at.isoformat())
    last_seen_at = max(row["last_seen_at"], post.created_at.isoformat())

    if post.engagement >= prev_engagement:
        conn.execute(
            """
            UPDATE paper_scores
            SET paper_link = ?,
                representative_post_uri = ?,
                representative_created_at = ?,
                text = ?,
                title = ?,
                authors = ?,
                like_count = ?,
                reply_count = ?,
                repost_count = ?,
                quote_count = ?,
                engagement = ?,
                mention_count = ?,
                first_seen_at = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE actor = ? AND arxiv_key = ?
            """,
            (
                post.paper_link,
                post.uri,
                post.created_at.isoformat(),
                post.text,
                title,
                authors,
                post.like_count,
                post.reply_count,
                post.repost_count,
                post.quote_count,
                post.engagement,
                mention_count,
                first_seen_at,
                last_seen_at,
                now_iso,
                actor,
                post.arxiv_key,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE paper_scores
            SET mention_count = ?,
                first_seen_at = ?,
                last_seen_at = ?,
                updated_at = ?
            WHERE actor = ? AND arxiv_key = ?
            """,
            (
                mention_count,
                first_seen_at,
                last_seen_at,
                now_iso,
                actor,
                post.arxiv_key,
            ),
        )


def _ingest_author_feed(
    conn: sqlite3.Connection,
    client: Any,
    actor: str,
    stop_when_older_than: Optional[datetime] = None,
    stop_when_at_or_before: Optional[datetime] = None,
    limit: int = 100,
) -> tuple[SyncStats, Optional[datetime]]:
    cursor = None
    fetched_at = datetime.now(timezone.utc)
    max_created_seen: Optional[datetime] = None
    stats = SyncStats()

    while True:
        params = {"actor": actor, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        response = client.app.bsky.feed.get_author_feed(params)
        if not response.feed:
            break

        stop = False
        for item in response.feed:
            stats.scanned_items += 1

            post = item.post
            record = post.record
            created_at = parse_iso_datetime(record.created_at)

            if stop_when_at_or_before and created_at <= stop_when_at_or_before:
                stop = True
                break
            if stop_when_older_than and created_at < stop_when_older_than:
                stop = True
                break
            if post.author.handle.lower() != actor.lower():
                continue

            if not max_created_seen or created_at > max_created_seen:
                max_created_seen = created_at

            paper_link = extract_link_from_record(record) or extract_link_from_embed(post.embed)
            arxiv_key = canonicalize_arxiv_key(paper_link or "")
            if not arxiv_key:
                continue

            ranked = RankedPost(
                uri=post.uri,
                created_at=created_at,
                text=record.text or "",
                paper_link=canonical_arxiv_abs_url(arxiv_key),
                like_count=post.like_count or 0,
                reply_count=post.reply_count or 0,
                repost_count=post.repost_count or 0,
                quote_count=post.quote_count or 0,
                arxiv_key=arxiv_key,
            )
            stats.paper_posts_seen += 1
            stats.log_rows_upserted += _upsert_log_row(conn, actor, ranked, fetched_at)
            _upsert_paper_scores_row(conn, actor, ranked)

        if stop:
            break
        cursor = getattr(response, "cursor", None)
        if not cursor:
            break

    return stats, max_created_seen


def sync_cache_for_window(
    conn: sqlite3.Connection,
    actor: str,
    username: str,
    password: str,
    start: datetime,
) -> SyncStats:
    # Delay heavy atproto import until a sync is actually requested.
    from atproto import Client

    client: Any = Client()
    client.login(username, password)

    latest_synced = get_latest_synced_created_at(conn, actor)
    total = SyncStats()

    if latest_synced:
        inc_stats, inc_max = _ingest_author_feed(
            conn,
            client,
            actor,
            stop_when_at_or_before=latest_synced,
        )
        total.scanned_items += inc_stats.scanned_items
        total.paper_posts_seen += inc_stats.paper_posts_seen
        total.log_rows_upserted += inc_stats.log_rows_upserted

        if inc_max and inc_max > latest_synced:
            set_latest_synced_created_at(conn, actor, inc_max)
    else:
        seed_stats, seed_max = _ingest_author_feed(
            conn,
            client,
            actor,
            stop_when_older_than=start,
        )
        total.scanned_items += seed_stats.scanned_items
        total.paper_posts_seen += seed_stats.paper_posts_seen
        total.log_rows_upserted += seed_stats.log_rows_upserted

        if seed_max:
            set_latest_synced_created_at(conn, actor, seed_max)

    oldest_cached = get_oldest_cached_created_at(conn, actor)
    if latest_synced and oldest_cached and oldest_cached > start:
        backfill_stats, _ = _ingest_author_feed(
            conn,
            client,
            actor,
            stop_when_older_than=start,
        )
        total.scanned_items += backfill_stats.scanned_items
        total.paper_posts_seen += backfill_stats.paper_posts_seen
        total.log_rows_upserted += backfill_stats.log_rows_upserted

    conn.commit()
    return total


def get_ranked_posts_for_window(
    conn: sqlite3.Connection,
    actor: str,
    start: datetime,
    end: datetime,
) -> list[RankedPost]:
    rows = conn.execute(
        """
        SELECT post_uri, created_at, text, paper_link,
               like_count, reply_count, repost_count, quote_count,
               engagement, arxiv_key
        FROM paper_score_log
        WHERE actor = ? AND created_at >= ? AND created_at < ?
        ORDER BY engagement DESC, created_at DESC
        """,
        (actor, start.isoformat(), end.isoformat()),
    ).fetchall()

    seen_keys: set[str] = set()
    posts: list[RankedPost] = []
    for row in rows:
        arxiv_key = row["arxiv_key"]
        if arxiv_key in seen_keys:
            continue
        seen_keys.add(arxiv_key)
        posts.append(
            RankedPost(
                uri=row["post_uri"],
                created_at=parse_iso_datetime(row["created_at"]),
                text=row["text"],
                paper_link=row["paper_link"],
                like_count=int(row["like_count"]),
                reply_count=int(row["reply_count"]),
                repost_count=int(row["repost_count"]),
                quote_count=int(row["quote_count"]),
                arxiv_key=arxiv_key,
            )
        )
    return posts


def fetch_posts_cached(
    actor: str,
    username: str,
    password: str,
    start: datetime,
    end: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> tuple[list[RankedPost], SyncStats]:
    conn = open_db(db_path)
    try:
        stats = sync_cache_for_window(conn, actor, username, password, start)
        posts = get_ranked_posts_for_window(conn, actor, start, end)
        return posts, stats
    finally:
        conn.close()


def fetch_posts_from_cache(
    actor: str,
    start: datetime,
    end: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[RankedPost]:
    conn = open_db(db_path)
    try:
        return get_ranked_posts_for_window(conn, actor, start, end)
    finally:
        conn.close()


def format_post(name: str, post: RankedPost) -> str:
    return (
        f"{name}\n"
        f"  created_at: {post.created_at.isoformat()}\n"
        f"  arxiv_key: {post.arxiv_key}\n"
        f"  likes: {post.like_count}\n"
        f"  replies: {post.reply_count}\n"
        f"  reposts: {post.repost_count}\n"
        f"  quotes: {post.quote_count}\n"
        f"  engagement(likes+replies+reposts+quotes): {post.engagement}\n"
        f"  paper_link: {post.paper_link}\n"
        f"  uri: {post.uri}\n"
        f"  text: {post.text}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch paper posts from a Bluesky account and rank by engagement."
    )
    parser.add_argument("--actor", default="paperposterbot.bsky.social")
    parser.add_argument(
        "--start", default="2026-01-01", help="UTC start date, inclusive (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", default="2026-02-01", help="UTC end date, exclusive (YYYY-MM-DD)"
    )
    parser.add_argument("--username", default=os.getenv("BSKYUSR"))
    parser.add_argument("--password", default=os.getenv("BSKYPWD"))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit(
            "Missing credentials. Set BSKYUSR and BSKYPWD, or pass --username and --password."
        )

    start = parse_date_utc(args.start)
    end = parse_date_utc(args.end)
    if end <= start:
        raise SystemExit("--end must be later than --start.")

    posts, sync_stats = fetch_posts_cached(
        actor=args.actor,
        username=args.username,
        password=args.password,
        start=start,
        end=end,
        db_path=Path(args.db_path),
    )
    print(f"actor: {args.actor}")
    print(f"window_utc: [{start.isoformat()}, {end.isoformat()})")
    print(f"paper_posts_found: {len(posts)}")
    print(
        f"sync: scanned_items={sync_stats.scanned_items}, "
        f"paper_posts_seen={sync_stats.paper_posts_seen}, "
        f"log_rows_upserted={sync_stats.log_rows_upserted}"
    )
    if not posts:
        return

    most_liked = max(posts, key=lambda p: p.like_count)
    most_commented = max(posts, key=lambda p: p.reply_count)
    most_engaged = max(posts, key=lambda p: p.engagement)

    print()
    print(format_post("MOST LIKED", most_liked))
    print(format_post("MOST COMMENTED", most_commented))
    print(format_post("MOST ENGAGED", most_engaged))


if __name__ == "__main__":
    main()
