#!/usr/bin/env python3
"""Build browser-safe, original-source summaries for the static GitHub Pages app."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news-cache.json"
KST = dt.timezone(dt.timedelta(hours=9))
SSL_CONTEXT = ssl.create_default_context()
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIT-News-Cache/3.2.4)"}
CATEGORY_QUERIES = {
    "genai": "(생성형 AI OR LLM OR GPT OR Claude OR Gemini)",
    "biz": "(AI 산업 OR AI 비즈니스 OR 인공지능 시장)",
    "tech": "(AI 기술 OR 인공지능 모델 OR AI 개발)",
    "policy": "(AI 정책 OR AI 규제 OR 인공지능 법)",
}


def request_text(url: str, data: bytes | None = None, timeout: int = 25) -> str:
    headers = dict(HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT)
    except urllib.error.URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        # Some local Python installations do not inherit the macOS trust store.
        response = urllib.request.urlopen(request, timeout=timeout, context=ssl._create_unverified_context())
    with response:
        return response.read().decode("utf-8", errors="replace")


def decode_google_news_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    page = request_text(f"{url}{separator}hl=ko&gl=KR&ceid=KR:ko")
    article_id = re.search(r'data-n-a-id="([^"]+)"', page)
    timestamp = re.search(r'data-n-a-ts="([^"]+)"', page)
    signature = re.search(r'data-n-a-sg="([^"]+)"', page)
    if not all((article_id, timestamp, signature)):
        raise ValueError("Google News decoding metadata missing")

    inner = [
        "garturlreq",
        [["ko", "KR", ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"], None, None, 1, 1,
          "KR:ko", None, 540, None, None, None, None, None, 0, None, None,
          [1608992183, 723341000]], "ko", "KR", 1, [2, 3, 4, 8], 1, 0,
         "655000234", 0, 0, None, 0],
        article_id.group(1), int(timestamp.group(1)), signature.group(1),
    ]
    batch = [[["Fbv4je", json.dumps(inner, separators=(",", ":"), ensure_ascii=False), None, "generic"]]]
    form = urllib.parse.urlencode({"f.req": json.dumps(batch, separators=(",", ":"), ensure_ascii=False)}).encode()
    response = request_text(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je",
        data=form,
    )
    body = response.split("\n\n", 1)[-1]
    outer = json.loads(body)
    decoded = json.loads(outer[0][2])
    if decoded[0] != "garturlres" or not str(decoded[1]).startswith("http"):
        raise ValueError("Google News URL decoding failed")
    return decoded[1]


def clean_markdown_line(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"!\[[^]]*]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>|[*_`>#]", " ", text)
    text = re.sub(r"(?<=[가-힣A-Za-z])\d{2,3}(?=[(‘’'\"])", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -•\t")
    return text


def extract_three_facts(reader_text: str, title: str) -> list[str]:
    content = reader_text.split("Markdown Content:", 1)[-1]
    stop_markers = ("핫뉴스", "함께 볼만한", "관련 기사", "추천 뉴스", "저작권자", "Copyright")
    sentences: list[str] = []
    normalized_title = re.sub(r"[^가-힣A-Za-z0-9]", "", title).lower()
    ui_noise = re.compile(
        r"댓글|답글|추천수|다시 복구|글자크기|구글 검색|선호 출처|검색창|메뉴 열기|"
        r"기념사진|사진[=·:]|이미지 확대|제공[.。]?$|광고|구독|로그인|회원가입|"
        r"기사의 본문|BEST|재판매|DB 금지|무단 전재|Copyright|저작권자|"
        r"음성\s*재생|데이터 요금|글자 수|다음뉴스|비밀번호|마이페이지|"
        r"시사월드|인사이트를 제공합니다|본문에서 확인|원문에서 확인",
        re.I,
    )
    for raw_line in content.splitlines():
        if any(marker in raw_line for marker in stop_markers):
            if sentences:
                break
            continue
        line = clean_markdown_line(raw_line)
        line_key = re.sub(r"[^가-힣A-Za-z0-9]", "", line).lower()
        if not line or line_key == normalized_title or ui_noise.search(line) or line.startswith("▲"):
            continue
        if re.search(r"(?:기자|특파원)\s*$|^(?:송고|입력|수정)\s*20\d{2}|메뉴|검색창|광고|재판매|DB 금지|무단 전재", line):
            continue
        line = re.sub(r"^\([^)]{2,30}=.?\S+\)\s*[^=]{0,24}(?:기자|특파원)\s*=\s*", "", line)
        line = re.sub(r"^\[[^]]{2,40}(?:기자|특파원)]\s*", "", line)
        line = re.sub(r"^[A-Za-z0-9.-]{2,20}\s*-\s*", "", line)
        for sentence in re.split(r"(?<=[.!?。！？])\s+", line):
            sentence = sentence.strip()
            if not (22 <= len(sentence) <= 125) or not re.search(r"[가-힣]", sentence):
                continue
            if "?" in sentence or "？" in sentence or ui_noise.search(sentence):
                continue
            if not re.search(r"(?:다|했다|됐다|한다|밝혔다|설명했다|전망했다|예정이다|수준이다)[.!?。！？]$", sentence):
                continue
            sentence_key = re.sub(r"[^가-힣A-Za-z0-9]", "", sentence).lower()
            overlap = len(set(sentence_key[i:i + 3] for i in range(max(0, len(sentence_key) - 2))) & set(normalized_title[i:i + 3] for i in range(max(0, len(normalized_title) - 2))))
            title_grams = max(1, len(set(normalized_title[i:i + 3] for i in range(max(0, len(normalized_title) - 2)))))
            if sentence_key == normalized_title or (len(sentence) < 65 and overlap / title_grams > 0.82):
                continue
            key = re.sub(r"[^가-힣A-Za-z0-9]", "", sentence).lower()
            if any(key == re.sub(r"[^가-힣A-Za-z0-9]", "", prior).lower() for prior in sentences):
                continue
            sentences.append(sentence)
            if len(sentences) == 3:
                return sentences
    return sentences


def parse_feed(category: str, mode: str) -> list[dict]:
    when = "1d" if mode == "daily" else "7d"
    query = f"{CATEGORY_QUERIES[category]} when:{when}"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"
    })
    root = ET.fromstring(request_text(url))
    items = []
    for node in root.findall(".//item")[:10]:
        raw_title = (node.findtext("title") or "").strip()
        source_node = node.find("source")
        source = ((source_node.text if source_node is not None else "") or raw_title.rsplit(" - ", 1)[-1]).strip()
        title = raw_title[:-(len(source) + 3)].strip() if raw_title.endswith(f" - {source}") else raw_title
        items.append({
            "title": title,
            "source": source,
            "google_link": (node.findtext("link") or "").strip(),
            "publishedAt": (node.findtext("pubDate") or "").strip(),
            "category": category,
        })
    return items


def enrich(item: dict) -> dict | None:
    try:
        original = decode_google_news_url(item["google_link"])
        reader = request_text(f"https://r.jina.ai/{original}", timeout=35)
        bullets = extract_three_facts(reader, item["title"])
        if len(bullets) != 3:
            return None
        return {
            "title": item["title"],
            "source": item["source"],
            "link": original,
            "publishedAt": item["publishedAt"],
            "date": dt.datetime.strptime(item["publishedAt"], "%a, %d %b %Y %H:%M:%S %Z").astimezone(KST).date().isoformat(),
            "category": item["category"],
            "bullets": bullets,
            "contentVerified": True,
        }
    except Exception as error:
        print(f"skip: {item.get('title', '')[:45]} ({error})")
        return None


def build_mode(mode: str) -> list[dict]:
    candidates: list[dict] = []
    for category in CATEGORY_QUERIES:
        candidates.extend(parse_feed(category, mode))
    unique = {}
    for item in candidates:
        unique.setdefault(re.sub(r"\s+", "", item["title"]).lower(), item)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        enriched = list(pool.map(enrich, unique.values()))
    results = [item for item in enriched if item]
    results.sort(key=lambda item: item["publishedAt"], reverse=True)
    # Keep enough per category for category-filtered runs while bounding repository size.
    selected = []
    for category in CATEGORY_QUERIES:
        selected.extend([item for item in results if item["category"] == category][:4])
    return selected


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    payload = {
        "version": "3.2.4",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "daily": build_mode("daily"),
        "weekly": build_mode("weekly"),
    }
    if len(payload["daily"]) < 3 or len(payload["weekly"]) < 3:
        raise SystemExit("Not enough original-source articles passed three-sentence validation")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}: daily={len(payload['daily'])}, weekly={len(payload['weekly'])}")


if __name__ == "__main__":
    main()
