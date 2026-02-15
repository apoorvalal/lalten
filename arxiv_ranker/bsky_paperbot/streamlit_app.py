import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from rank_papers import (
    RankedPost,
    extract_title_and_authors,
    fetch_posts_cached,
    fetch_posts_from_cache,
)


def at_uri_to_bsky_url(handle: str, at_uri: str) -> str:
    parts = at_uri.split("/")
    post_id = parts[-1] if parts else ""
    return f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else ""


def fetch_posts(
    actor: str, username: str, password: str, start_dt: datetime, end_exclusive_dt: datetime
) -> list[RankedPost]:
    posts, _ = fetch_posts_cached(actor, username, password, start_dt, end_exclusive_dt)
    return posts


def fetch_posts_from_local_cache(
    actor: str, start_dt: datetime, end_exclusive_dt: datetime
) -> list[RankedPost]:
    return fetch_posts_from_cache(actor, start_dt, end_exclusive_dt)


def build_table_rows(actor: str, posts: list[RankedPost]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for post in posts:
        title, authors = extract_title_and_authors(post.text)
        rows.append(
            {
                "timestamp": post.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "title": title,
                "authors": authors,
                "link": post.paper_link,
                "bsky_link": at_uri_to_bsky_url(actor, post.uri),
                "engagement": post.engagement,
            }
        )
    return rows


def main() -> None:
    st.set_page_config(page_title="bsky arxiv methods charts", layout="wide")
    st.title("bsky arxiv methods charts")
    st.caption(
        "Fetch papers posted by paperposterbot within a time filter, sorted by engagement or timestamp."
    )

    today_utc = datetime.now(timezone.utc).date()
    default_start = today_utc - timedelta(days=30)

    with st.sidebar:
        st.header("Filters")
        actor = st.text_input("Actor handle", value="paperposterbot.bsky.social")
        start_date = st.date_input("Start date (UTC, inclusive)", value=default_start)
        end_date = st.date_input("End date (UTC, inclusive)", value=today_utc)
        sort_label = st.selectbox(
            "Sort by",
            options=[
                "engagement (likes+replies+reposts+quotes)",
                "timestamp",
            ],
            index=0,
        )
        max_rows = st.number_input("Max rows to display", min_value=20, max_value=5000, value=20)
        run_sync = st.button("Sync now", type="primary", use_container_width=True)

    username = os.getenv("BSKYUSR", "")
    password = os.getenv("BSKYPWD", "")

    if end_date < start_date:
        st.error("Invalid date range: end date must be on or after start date.")
        return

    start_dt = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
    end_exclusive_dt = datetime.combine(end_date + timedelta(days=1), time.min).replace(
        tzinfo=timezone.utc
    )
    selected_key = f"{actor}|{start_dt.isoformat()}|{end_exclusive_dt.isoformat()}"
    default_key = (
        "paperposterbot.bsky.social|"
        f"{datetime.combine(default_start, time.min).replace(tzinfo=timezone.utc).isoformat()}|"
        f"{datetime.combine(today_utc + timedelta(days=1), time.min).replace(tzinfo=timezone.utc).isoformat()}"
    )
    last_synced_key = st.session_state.get("last_synced_key")
    should_auto_sync = selected_key != default_key and last_synced_key != selected_key
    should_sync = run_sync or should_auto_sync

    with st.spinner("Reading cached posts..."):
        try:
            posts = fetch_posts_from_local_cache(actor, start_dt, end_exclusive_dt)
        except Exception as exc:
            st.error(f"Failed to read cache: {exc}")
            return

    if should_sync:
        if not username or not password:
            st.error("Missing credentials. Set BSKYUSR and BSKYPWD in the environment.")
            return
        with st.spinner("Syncing from Bluesky..."):
            try:
                posts = fetch_posts(actor, username, password, start_dt, end_exclusive_dt)
                st.session_state["last_synced_key"] = selected_key
            except Exception as exc:  # Surface API/auth/network errors directly in UI
                st.error(f"Failed to sync posts: {exc}")
                return
    elif selected_key == default_key:
        st.caption("Showing cached results for the default 30-day window. Use 'Sync now' to refresh.")

    st.write(
        f"Window: `{start_dt.date().isoformat()}` to `{end_date.isoformat()}` (UTC, inclusive)  \n"
        f"Paper posts found: `{len(posts)}`"
    )

    if not posts:
        st.warning("No paper posts found in this window.")
        return

    top_liked = max(posts, key=lambda p: p.like_count)
    top_commented = max(posts, key=lambda p: p.reply_count)
    top_engaged = max(posts, key=lambda p: p.engagement)

    cols = st.columns(3)
    top_specs = [
        ("Most liked", top_liked),
        ("Most commented", top_commented),
        ("Most engaged", top_engaged),
    ]
    for col, (label, post) in zip(cols, top_specs):
        title, _ = extract_title_and_authors(post.text)
        col.subheader(label)
        col.write(title or "(title unavailable)")
        col.write(
            f"Likes: {post.like_count} | Replies: {post.reply_count} | Engagement: {post.engagement}"
        )
        col.markdown(
            f"[Paper]({post.paper_link}) | [Bluesky post]({at_uri_to_bsky_url(actor, post.uri)})"
        )

    rows = build_table_rows(actor, posts)
    df = pd.DataFrame(rows)

    sort_map = {
        "engagement (likes+replies+reposts+quotes)": ("engagement", False),
        "timestamp": ("timestamp", False),
    }
    sort_column, ascending = sort_map[sort_label]
    df_sorted = df.sort_values(by=sort_column, ascending=ascending).head(int(max_rows))
    df_sorted = df_sorted[["timestamp", "title", "authors", "link", "bsky_link", "engagement"]]

    st.subheader("Posts")
    st.dataframe(
        df_sorted,
        use_container_width=True,
        hide_index=True,
        column_config={
            "link": st.column_config.LinkColumn("Link"),
            "bsky_link": st.column_config.LinkColumn("bsky_link"),
        },
    )


if __name__ == "__main__":
    main()
