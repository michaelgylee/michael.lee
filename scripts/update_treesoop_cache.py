#!/usr/bin/env python3
"""Mirror TreeSoop's daily AI news posts into a same-origin cache.

treesoop.com serves no Access-Control-Allow-Origin header, so the browser app
cannot read it directly and has to bounce off public CORS relays. Those relays
(api.allorigins.win, api.codetabs.com, corsproxy.io) fail most attempts and can
be down for long stretches, which left the researcher stage with no way to
finish even though treesoop.com itself answers in about 0.1s.

GitHub Actions has no such restriction, so we fetch the posts here and publish
them next to the app. The browser reads the cache from its own origin first and
only falls back to the relays when the cache is missing or stale.

Only the raw extraction lives here; bullet shaping stays in app.js so that the
cached path and the live path render identical cards.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "treesoop-cache.json"
ORIGIN = "https://treesoop.com"
INDEX_PATHS = ("/blog/news", "/blog/news/page/2")
KST = dt.timezone(dt.timedelta(hours=9))
SSL_CONTEXT = ssl.create_default_context()
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIT-TreeSoop-Cache/3.2.8)"}

# How many recent posts to mirror. Enough for the daily card set plus several
# days of fallback when the newest day has not been published yet.
POST_LIMIT = 7

SKIP_HEADINGS = re.compile(
    r"^(?:블로그|댓글|이전\s*글|다음\s*글|정리|자주\s*묻는\s*질문|관련\s*서비스|서비스|채용"
    r"|마치며|들어가며|products|navigation|contact)",
    re.I,
)
SOURCE_LINE = re.compile(r"^원문\s*[:：]|원문\s*보기|https?://", re.I)


def request_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        response = urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT)
    except urllib.error.URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        # Some local Python installations do not inherit the macOS trust store.
        response = urllib.request.urlopen(
            request, timeout=timeout, context=ssl._create_unverified_context()
        )
    with response:
        return response.read().decode("utf-8", errors="replace")


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(text).replace("\xa0", " ").strip()


def post_dates(index_html: str) -> list[str]:
    return sorted(set(re.findall(r"ai-news-(\d{4}-\d{2}-\d{2})", index_html)), reverse=True)


def collect_dates() -> list[str]:
    dates: list[str] = []
    for path in INDEX_PATHS:
        try:
            dates.extend(post_dates(request_text(f"{ORIGIN}{path}")))
        except Exception as error:  # a missing page 2 must not sink the run
            print(f"index skip: {path} ({error})")
    return sorted(set(dates), reverse=True)


def parse_post(post_html: str) -> list[dict]:
    entries: list[dict] = []
    # Each news item is an <h2> followed by narrative <p> tags and a "원문:" line.
    sections = re.split(r"<h2[^>]*>", post_html)[1:]
    for section in sections:
        raw_title, _, body = section.partition("</h2>")
        title = strip_tags(raw_title)
        if not title or SKIP_HEADINGS.match(title):
            continue
        body = re.split(r"<h[12][^>]*>", body)[0]

        paragraphs: list[str] = []
        source_url = ""
        for raw_paragraph in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S):
            paragraph = strip_tags(raw_paragraph)
            if not paragraph:
                continue
            plain_url = re.search(r"https?://[^\s<>()]+", paragraph)
            if plain_url and not source_url:
                source_url = plain_url.group(0).rstrip("),.;")
            if not SOURCE_LINE.search(paragraph):
                paragraphs.append(paragraph)

        if not source_url:
            # Never let an internal TreeSoop link stand in for the original source.
            for href in re.findall(r'<a[^>]+href="([^"]+)"', body):
                absolute = urllib.parse.urljoin(ORIGIN, html.unescape(href))
                if not absolute.startswith(ORIGIN):
                    source_url = absolute
                    break

        if len(paragraphs) >= 2:
            entries.append({"title": title, "paragraphs": paragraphs, "sourceUrl": source_url})
    return entries


def main() -> None:
    dates = collect_dates()
    if not dates:
        raise SystemExit("No ai-news-* posts found on any TreeSoop index page")

    posts = []
    for date in dates[:POST_LIMIT]:
        post_url = f"{ORIGIN}/blog/ai-news-{date}"
        try:
            entries = parse_post(request_text(post_url))
        except Exception as error:
            print(f"post skip: {date} ({error})")
            continue
        if not entries:
            print(f"post skip: {date} (no parsable news sections)")
            continue
        posts.append({"date": date, "postUrl": post_url, "entries": entries})
        print(f"cached {date}: {len(entries)} items")

    if not posts:
        raise SystemExit("No TreeSoop post could be parsed")

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    payload = {
        "version": "3.2.8",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "generated_kst": now.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "posts": posts,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}: posts={len(posts)}, newest={posts[0]['date']}")


if __name__ == "__main__":
    main()
