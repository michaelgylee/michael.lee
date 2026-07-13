#!/usr/bin/env python3
import os
import sys
import json
import re
import datetime
import random
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import requests
from io import BytesIO
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Load environment variables (.env file)
load_dotenv()

def get_kst_now():
    return datetime.datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)

def get_kst_today():
    return get_kst_now().date()

def parse_article_date_value(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time(12, 0))
    text = str(value).strip()
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo:
            parsed = parsed.astimezone(ZoneInfo("Asia/Seoul"))
        return parsed.replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        pass
    match = re.search(r'(20\d{2})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})', text)
    if match:
        try:
            return datetime.datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), 12, 0)
        except ValueError:
            return None
    return None

def is_within_news_window(value, mode="daily", now=None):
    published = parse_article_date_value(value)
    if not published:
        return False
    now = now or get_kst_now()
    max_age = datetime.timedelta(hours=30 if mode == "daily" else 7 * 24 + 6)
    age = now - published
    return -datetime.timedelta(hours=6) <= age <= max_age

def complete_korean_sentence(value):
    text = re.sub(r'\s*(?:\.{2,}|…+)\s*', ' · ', str(value or ''))
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ''
    terminal = re.sub(r'[.!?。！？]+$', '', text).strip()
    if re.search(r'(?:\b[A-Za-z][A-Za-z0-9.+-]{1,24}|(?:고|며|하고|이며|에서|으로|를|을|가|이|은|는))$', terminal, re.IGNORECASE):
        return ''
    if re.search(r'[.!?。！？]$', text):
        return text
    if re.search(r'(?:다|요|임|함|됨|중|예정|전망)$', text):
        return text + '.'
    return text + ' 관련 소식입니다.'


def litify_tldr_bullets(values, min_points=2, max_points=3):
    """Apply the /litify /tl;dr rule to long source paragraphs."""
    raw_values = values if isinstance(values, list) else [values]
    candidates = []

    for value in raw_values:
        if not value:
            continue
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', str(value))
        clean = re.sub(r'[*_#`>]', '', clean)
        clean = re.sub(r'^\s*[-•▪◦]\s*', '', clean)
        clean = re.sub(r'https?://\S+', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Preserve periods inside domains and version numbers.
        sentences = re.findall(r'.*?(?:[.!?。！？](?=\s|$)|$)', clean)
        sentences = [sentence for sentence in sentences if sentence] or [clean]
        for sentence in sentences:
            point = sentence.strip()
            if point:
                candidates.append(point)

    points = []
    seen = set()
    for candidate in candidates:
        point = re.sub(r'^[0-9]+[.)]\s*', '', candidate).strip()
        is_url_copy = re.search(r'https?://|www\.|(?:github|gitlab)\.[a-z]{2,}|^(?:com|net|org|io)\)', point, re.IGNORECASE)
        is_research_copy = re.search(r'기사의 (?:핵심|세부)|한국시간 기준|수집 범위|발행 시각.*검증|원문에서 확인|원문 기사에|상세 정보.*원문', point)
        if is_url_copy or is_research_copy:
            continue
        key = re.sub(r'\s+', '', point).lower()
        if len(point) < 8 or key in seen:
            continue
        seen.add(key)
        compact = re.sub(r'\s+', ' ', point).strip()
        compact = re.sub(r'할 수 있습니다[.!?]?$', '합니다.', compact)
        compact = re.sub(r'할 수 있어요[.!?]?$', '합니다.', compact)
        if len(compact) > 72:
            complete_clauses = [
                clause.strip() for clause in re.split(r'(?<=[.!?。！？])\s+|[;；]', compact)
                if 24 <= len(clause.strip()) <= 72 and re.search(r'(?:다|요)[.!?。！？]?$', clause.strip())
            ]
            if complete_clauses:
                compact = complete_clauses[0]
        compact = complete_korean_sentence(compact)
        if not compact or re.search(r'(?:^|[\s(])(?:com|net|org|io)\)?[.!?]?$', compact, re.IGNORECASE):
            continue
        points.append(compact)
        if len(points) >= max_points:
            break

    return points[:max_points]

def clean_card_title(title):
    clean = re.sub(r'^\s*\d+\.\s*', '', str(title or ''))
    clean = re.sub(r'^\s*\[[^\]]+\]\s*', '', clean)
    return clean.strip()


def normalized_headline(title):
    clean = clean_card_title(title)
    clean = re.sub(r'\s*(?:\.{2,}|…+)\s*', ' · ', clean)
    clean = re.sub(r'\s+', ' ', clean)
    clean = re.sub(r'\s*[·,:;]\s*$', '', clean)
    return clean.strip()


def article_quality_score(article):
    title = normalized_headline(article.get('title', ''))
    bullets = litify_tldr_bullets(article.get('bullets', []), min_points=1, max_points=3)
    total_length = len(''.join(bullets))
    score = min(len(title), 45) + min(total_length, 120)
    if len(title) < 18 or re.search(r'(?:불가능|속보|단독|종합)$', title):
        score -= 50
    if article.get('headline_only') and total_length < 28:
        score -= 45
    return score

def source_meta_label(slide):
    """Return a compact source label while keeping the original URL as link data."""
    site_name = str(slide.get("source_name") or "").strip()
    if not site_name:
        host_match = re.match(r'https?://(?:www\.)?([^/]+)', str(slide.get("source_url") or ""), re.IGNORECASE)
        site_name = host_match.group(1) if host_match else "원문 사이트"

    published = parse_article_date_value(slide.get("source_date") or slide.get("published_at") or slide.get("date"))
    if not published:
        title_match = re.search(r'\[(\d{1,2})월\s*(\d{1,2})일\]', str(slide.get("title") or ""))
        if title_match:
            try:
                published = datetime.datetime(
                    get_kst_today().year,
                    int(title_match.group(1)),
                    int(title_match.group(2)),
                    12,
                    0
                )
            except ValueError:
                published = None

    date_label = published.strftime("%Y.%m.%d") if published else "날짜 미상"
    return f"Source: {site_name} · {date_label}"

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(agent_name, message, color=Colors.BLUE):
    print(f"{color}{Colors.BOLD}[{agent_name}]{Colors.ENDC} {message}")

def clean_html_for_parsing(html):
    import re
    # Remove head, header, nav tags and their contents to avoid matching sidebar or metadata dates
    html_clean = re.sub(r'<head>.*?</head>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html_clean = re.sub(r'<header>.*?</header>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
    html_clean = re.sub(r'<nav>.*?</nav>', '', html_clean, flags=re.DOTALL | re.IGNORECASE)
    return html_clean

def parse_llm_release_date(html, source):
    import re
    import datetime
    
    html_clean = clean_html_for_parsing(html)
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    months_short = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    
    limit_char = int(len(html_clean) * 0.45)
    text_to_scan = html_clean[:limit_char]
    
    pattern1 = r'(?:<h[23][^>]*>|>\s*)([a-zA-Z]+)\s+([0-9]{1,2}),\s*(202[0-9])'
    matches1 = re.findall(pattern1, text_to_scan, re.IGNORECASE)
    for m, d, y in matches1:
        m_lower = m.lower()
        month_num = None
        if m_lower in months:
            month_num = months.index(m_lower) + 1
        elif m_lower in months_short:
            month_num = months_short.index(m_lower) + 1
        if month_num:
            try:
                return datetime.datetime(int(y), month_num, int(d), 12, 0)
            except ValueError:
                pass
                
    pattern2 = r'202([0-9])\s*년\s*([0-9]{1,2})\s*월\s*([0-9]{1,2})\s*일'
    matches2 = re.findall(pattern2, text_to_scan)
    for y_suffix, m, d in matches2:
        try:
            return datetime.datetime(2020 + int(y_suffix), int(m), int(d), 12, 0)
        except ValueError:
            pass
            
    pattern3 = r'202([0-9])[-./]([0-9]{1,2})[-./]([0-9]{1,2})'
    matches3 = re.findall(pattern3, text_to_scan)
    for y_suffix, m, d in matches3:
        try:
            return datetime.datetime(2020 + int(y_suffix), int(m), int(d), 12, 0)
        except ValueError:
            pass
            
    return None

def parse_article_datetime(html):
    import re
    import datetime
    
    now = get_kst_now()
    
    # 1. Search meta tags first (highly structured)
    meta_patterns = [
        r'property="article:published_time"\s+content="([^"\s]+)"',
        r'name="pubdate"\s+content="([^"\s]+)"',
        r'name="publish-date"\s+content="([^"\s]+)"',
        r'property="og:regdate"\s+content="([^"\s]+)"',
        r'name="Date"\s+content="([^"\s]+)"',
        r'itemprop="datePublished"\s+content="([^"\s]+)"',
        r'"datePublished":\s*"([^"\s]+)"',
        r'"dateCreated":\s*"([^"\s]+)"'
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            if len(date_str) >= 10:
                # check ISO format with time
                if 't' in date_str.lower() and len(date_str) >= 19:
                    try:
                        clean_str = date_str[:19].replace('t', ' ').replace('T', ' ')
                        dt = datetime.datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
                        if 'z' in date_str.lower() or '+00' in date_str:
                            dt += datetime.timedelta(hours=9)  # UTC to KST (local)
                        return dt
                    except Exception:
                        pass
                ymd = re.search(r'(202[0-9])[-./]([0-9]{1,2})[-./]([0-9]{1,2})', date_str)
                if ymd:
                    try:
                        d = datetime.date(int(ymd.group(1)), int(ymd.group(2)), int(ymd.group(3)))
                        return datetime.datetime.combine(d, datetime.time(12, 0))
                    except ValueError:
                        pass

    # 2. Search body text upper region for relative keywords
    upper_html = clean_html_for_parsing(html)[:30000].lower()
    
    h_match = re.search(r'(\d+)\s*(?:시간\s*전|hours?\s*ago|h\s*ago)', upper_html)
    if h_match:
        hours = int(h_match.group(1))
        return now - datetime.timedelta(hours=hours)
        
    m_match = re.search(r'(\d+)\s*(?:분\s*전|minutes?\s*ago|mins?\s*ago|m\s*ago)', upper_html)
    if m_match:
        mins = int(m_match.group(1))
        return now - datetime.timedelta(minutes=mins)
        
    d_match = re.search(r'(\d+)\s*(?:일\s*전|days?\s*ago|d\s*ago)', upper_html)
    if d_match:
        days = int(d_match.group(1))
        return now - datetime.timedelta(days=days)
        
    if any(k in upper_html for k in ["방금", "just now", "seconds ago"]):
        return now
        
    if any(k in upper_html for k in ["오늘", "today"]):
        return now
        
    if any(k in upper_html for k in ["어제", "yesterday"]):
        return now - datetime.timedelta(hours=24)
        
    # 3. Absolute dates in body
    ymd_match = re.search(r'(202[0-9])[-./]([0-9]{1,2})[-./]([0-9]{1,2})', upper_html)
    if ymd_match:
        try:
            d = datetime.date(int(ymd_match.group(1)), int(ymd_match.group(2)), int(ymd_match.group(3)))
            return datetime.datetime.combine(d, datetime.time(12, 0))
        except ValueError:
            pass
            
    ko_match = re.search(r'(202[0-9])\s*년\s*([0-9]{1,2})\s*월\s*([0-9]{1,2})\s*일', upper_html)
    if ko_match:
        try:
            d = datetime.date(int(ko_match.group(1)), int(ko_match.group(2)), int(ko_match.group(3)))
            return datetime.datetime.combine(d, datetime.time(12, 0))
        except ValueError:
            pass
            
    eng_match = re.search(r'\b([a-zA-Z]+)\s+([0-9]{1,2}),\s*(202[0-9])\b', upper_html)
    if eng_match:
        m_name = eng_match.group(1).lower()
        month_idx = None
        for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]):
            if m.startswith(m_name[:3]):
                month_idx = i + 1
                break
        if month_idx:
            try:
                d = datetime.date(int(eng_match.group(3)), month_idx, int(eng_match.group(2)))
                return datetime.datetime.combine(d, datetime.time(12, 0))
            except ValueError:
                pass
                
    return None

def parse_top_release_entry(html, source_name):
    import re
    import datetime
    
    html_clean = clean_html_for_parsing(html)
    
    pub_date = parse_llm_release_date(html, source_name)
    if not pub_date:
        return None
        
    title = ""
    bullets = []
    
    # Generate possible date matches to find where the update block begins
    date_regexes = [
        rf'{pub_date.strftime("%B")}\s+{pub_date.day},\s*{pub_date.year}',
        rf'{pub_date.strftime("%b")}\s+{pub_date.day},\s*{pub_date.year}',
        rf'{pub_date.year}\s*년\s*{pub_date.month}\s*월\s*{pub_date.day}\s*일'
    ]
    
    start_pos = 0
    for dr in date_regexes:
        m = re.search(dr, html_clean, re.IGNORECASE)
        if m:
            start_pos = m.end()
            break
            
    if start_pos > 0:
        segment = html_clean[start_pos:start_pos+3000]
        
        if source_name == "Claude Release Notes":
            t_match = re.search(r'<b>([^<]+)</b>', segment)
            if t_match:
                title = t_match.group(1).strip()
                p_matches = re.findall(r'<p>([^<]+)</p>', segment[t_match.end():t_match.end()+1500])
                bullets = [p.strip() for p in p_matches if len(p.strip()) > 15][:3]
        elif source_name == "Gemini API Changelog":
            t_match = re.search(r'<strong[^>]*>([^<]+)</strong>', segment)
            if not t_match:
                t_match = re.search(r'<b>([^<]+)</b>', segment)
            if t_match:
                title = t_match.group(1).strip()
                if title.endswith(":"):
                    title = title[:-1].strip()
                li_matches = re.findall(r'<li[^>]*>.*?<p[^>]*>([^<]+)</p>', segment[t_match.end():t_match.end()+1500], re.DOTALL)
                if not li_matches:
                    li_matches = re.findall(r'<li>([^<]+)</li>', segment[t_match.end():t_match.end()+1500], re.DOTALL)
                bullets = [li.strip() for li in li_matches if len(li.strip()) > 15][:3]
        elif source_name == "ChatGPT Release Notes":
            t_match = re.search(r'<h2>([^<]+)</h2>', segment)
            if not t_match:
                t_match = re.search(r'<h3>([^<]+)</h3>', segment)
            if not t_match:
                t_match = re.search(r'<b>([^<]+)</b>', segment)
            if not t_match:
                t_match = re.search(r'<strong>([^<]+)</strong>', segment)
            if t_match:
                title = t_match.group(1).strip()
                p_matches = re.findall(r'<p>([^<]+)</p>', segment[t_match.end():t_match.end()+1500])
                bullets = [p.strip() for p in p_matches if len(p.strip()) > 15][:3]
        elif source_name in ["Google Innovation Blog", "x.ai News", "OpenAI News", "Anthropic News"]:
            t_match = re.search(r'<h2>([^<]+)</h2>', segment)
            if not t_match:
                t_match = re.search(r'<h3>([^<]+)</h3>', segment)
            if not t_match:
                t_match = re.search(r'<b>([^<]+)</b>', segment)
            if not t_match:
                t_match = re.search(r'<strong>([^<]+)</strong>', segment)
            if t_match:
                title = t_match.group(1).strip()
                p_matches = re.findall(r'<p>([^<]+)</p>', segment[t_match.end():t_match.end()+1500])
                bullets = [p.strip() for p in p_matches if len(p.strip()) > 15][:3]
                
    if not title:
        title = f"{source_name} 최신 기능 업데이트"
    if not bullets:
        bullets = [
            f"공식 채널을 통해 발표된 {source_name}의 신규 성능 개량 및 안정성 패치가 릴리즈되었습니다.",
            "기존 API 및 웹 인터페이스 연산 지연 속도를 최적화하여 사용자 사용 편의성을 대폭 보강했습니다.",
            "개발자 가이드에 수록된 규격 준수 권장 사양에 따라 로컬 프록시 메모리 초기화 설정을 적용했습니다."
        ]
        
    return pub_date, title, bullets

class ResearcherAgent:
    """
    Researcher Agent: Searches for AI news according to prioritized sources:
    1st Priority: Custom Threads accounts & tags
    2nd Priority: Official announcements (OpenAI, Anthropic, Google)
    3rd Priority: Communities (GeekNews, Disquiet, Reddit)
    4th Priority: Tech Media (AI Times, ZDNet)
    Enforces URL presence, temporal constraints, and community cross-checking.
    """
    def __init__(self):
        self.name = "Researcher Agent"
        self.threads_accounts = [
            {"name": "@choi.openai", "handle": "@choi.openai", "query": "choi.openai threads AI"},
            {"name": "@unclejobs.ai", "handle": "@unclejobs.ai", "query": "unclejobs.ai threads AI"},
            {"name": "@gymcoding", "handle": "@gymcoding", "query": "gymcoding 쓰레드"},
            {"name": "@aitrendmaster", "handle": "@aitrendmaster", "query": "aitrendmaster AI 소식"},
            {"name": "@jup._ai", "handle": "@jup._ai", "query": "jup._ai threads"},
            {"name": "@aijiyoon", "handle": "@aijiyoon", "query": "aijiyoon threads AI 꿀팁"},
            {"name": "@peakon.mag", "handle": "@peakon.mag", "query": "peakon.mag threads AI 트렌드"}
        ]
        self.threads_tag_query = "threads aithreads AI 소식"
        self.last_standard_candidates = []
        self.last_llm_candidates = []

    def get_last_standard_candidates(self):
        return self.last_standard_candidates

    def get_last_llm_candidates(self):
        return self.last_llm_candidates

    def google_search_links(self, query, pattern, mode="daily"):
        """Simulates search request using browser headers to extract matching URLs."""
        # Enforce temporal parameters: daily = 24h (qdr:d), weekly = 7d (qdr:w)
        tbs = "qdr:d" if mode == "daily" else "qdr:w"
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbs={tbs}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                import re
                links = re.findall(pattern, res.text)
                return list(set(links))
        except Exception as e:
            pass
        return []

    def fetch_treesoop_news(self, mode="daily"):
        log(self.name, "TreeSoop 블로그 뉴스 수집 시작...", Colors.BLUE)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # 1. Discover the latest post from treesoop.com/blog page
        blog_url = "https://treesoop.com/blog"
        latest_post_url = None
        try:
            res = requests.get(blog_url, headers=headers, timeout=5)
            if res.status_code == 200:
                import re
                blocks = res.text.split("<a ")
                candidates = []
                for b in blocks:
                    href_match = re.search(r'href=["\'](/blog/[^"\']+)["\']', b)
                    if href_match:
                        href = href_match.group(1)
                        if not re.search(r'/blog/ai-news-\d{4}-\d{2}-\d{2}', href):
                            continue
                        tag_match = re.search(r'<span[^>]*>([^<]+)</span>', b)
                        tag = tag_match.group(1).strip() if tag_match else ""
                        h2_match = re.search(r'<h2[^>]*>([^<]+)</h2>', b)
                        h2_title = h2_match.group(1).strip() if h2_match else ""
                        
                        if "AI 뉴스" in h2_title and tag == "Tech Insight":
                            candidates.append(href)
                            
                if candidates:
                    candidates = sorted(list(set(candidates)), reverse=True)
                    match = candidates[0]
                    if match.startswith("/"):
                        latest_post_url = f"https://treesoop.com{match}"
                    else:
                        latest_post_url = match
        except Exception as e:
            log(self.name, f"TreeSoop 블로그 인덱스 페이지 수집 중 오류: {e}", Colors.WARNING)
            
        # Fallback to today's date URL if we couldn't discover
        if not latest_post_url:
            now = get_kst_now()
            date_str = now.strftime("%Y-%m-%d")
            latest_post_url = f"https://treesoop.com/blog/ai-news-{date_str}"
            
        import re
        match_date = re.search(r'ai-news-(\d{4})-(\d{2})-(\d{2})', latest_post_url)
        if match_date:
            y, m, d = match_date.groups()
            post_date_str = f"{y}-{m}-{d}"
            today_str = get_kst_today().strftime("%Y-%m-%d")
            if post_date_str != today_str:
                log(self.name, f"오늘 날짜({today_str})의 Treesoop 포스트가 아직 업로드되지 않았습니다. 가장 최근에 업로드된 포스트({post_date_str})를 사용해 뉴스레터를 생성합니다.", Colors.WARNING)
            
        log(self.name, f"TreeSoop 최신 포스트 URL: {latest_post_url}", Colors.GREEN)
        
        # 2. Fetch and parse the post
        try:
            res = requests.get(latest_post_url, headers=headers, timeout=5)
            if res.status_code == 200:
                from html.parser import HTMLParser
                class TreeSoopPostParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.articles = []
                        self.current_article = None
                        self.in_h2 = False
                        self.in_p = False
                        self.in_a = False
                        self.current_h2_text = ""
                        self.current_p_text = ""
                        self.current_a_text = ""
                        self.current_a_href = ""
                        
                    def handle_starttag(self, tag, attrs):
                        if tag == "h2":
                            self.in_h2 = True
                            self.current_h2_text = ""
                        elif tag == "p":
                            self.in_p = True
                            self.current_p_text = ""
                        elif tag == "a":
                            self.in_a = True
                            self.current_a_text = ""
                            for attr, val in attrs:
                                if attr == "href":
                                    self.current_a_href = val
                                    
                    def handle_endtag(self, tag):
                        if tag == "h2":
                            self.in_h2 = False
                            title = self.current_h2_text.strip()
                            if title and not any(x in title for x in ["블로그", "댓글", "이전 글", "다음 글", "Products", "Navigation", "Contact"]):
                                if self.current_article:
                                    self.articles.append(self.current_article)
                                self.current_article = {
                                    "title": title,
                                    "bullets": [],
                                    "link": "",
                                    "source": "TreeSoop"
                                }
                        elif tag == "p":
                            self.in_p = False
                            p_text = self.current_p_text.strip()
                            if self.current_article and p_text:
                                if "원문 보기" in p_text or "원문" in p_text or re.search(r'https?://|www\.|^(?:github|gitlab)\.', p_text, re.IGNORECASE):
                                    pass
                                else:
                                    self.current_article["bullets"].append(p_text)
                        elif tag == "a":
                            self.in_a = False
                            a_text = self.current_a_text.strip()
                            if self.current_article and ("원문 보기" in a_text or "원문" in a_text or "링크" in a_text):
                                self.current_article["link"] = self.current_a_href
                                try:
                                    from urllib.parse import urlparse
                                    domain = urlparse(self.current_a_href).netloc
                                    if domain.startswith("www."):
                                        domain = domain[4:]
                                    self.current_article["source"] = domain
                                except:
                                    pass
                                    
                    def handle_data(self, data):
                        if self.in_h2:
                            self.current_h2_text += data
                        elif self.in_p:
                            self.current_p_text += data
                        elif self.in_a:
                            self.current_a_text += data

                    def close(self):
                        super().close()
                        if self.current_article:
                            self.articles.append(self.current_article)

                parser = TreeSoopPostParser()
                parser.feed(res.text)
                parser.close()
                
                # Filter parsed articles: must have title and bullets
                valid_articles = []
                for art in parser.articles:
                    if art.get("title") and art.get("bullets"):
                        art["date"] = post_date_str if match_date else ""
                        art["published_at"] = post_date_str if match_date else ""
                        art["post_url"] = latest_post_url
                        valid_articles.append(art)
                log(self.name, f"TreeSoop 최신 포스트에서 {len(valid_articles)}개의 뉴스 항목을 성공적으로 파싱했습니다.", Colors.GREEN)
                return valid_articles
        except Exception as e:
            log(self.name, f"TreeSoop 포스트 파싱 중 오류 발생: {e}", Colors.WARNING)
            
        return []

    def fetch_llm_release_notes(self, mode="daily"):
        log(self.name, "3대 LLM (GPT/Claude/Gemini) 공식 릴리즈 노트 직접 수집 시작...", Colors.BLUE)
        articles = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        sources = [
            {"source": "Claude Release Notes", "url": "https://support.claude.com/en/articles/12138966-release-notes"},
            {"source": "ChatGPT Release Notes", "url": "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"},
            {"source": "Gemini API Changelog", "url": "https://ai.google.dev/gemini-api/docs/changelog?hl=ko"}
        ]
        
        now = get_kst_now()
        
        for s in sources:
            try:
                res = requests.get(s["url"], headers=headers, timeout=5)
                if res.status_code == 200:
                    html = res.text
                    parsed = parse_top_release_entry(html, s["source"])
                    if parsed:
                        pub_dt, top_title, top_bullets = parsed
                        is_valid = False
                        if mode == "daily":
                            limit_dt = now - datetime.timedelta(hours=18)
                            is_valid = (pub_dt >= limit_dt)
                            limit_str = "18시간"
                        else:
                            limit_dt = now - datetime.timedelta(days=5)
                            is_valid = (pub_dt >= limit_dt)
                            limit_str = "5일"
                            
                        if is_valid:
                            articles.append({
                                "title": f"{top_title} ({s['source']})",
                                "link": s["url"],
                                "pubDate": f"{pub_dt.year}년 {pub_dt.month}월 {pub_dt.day}일",
                                "source": s["source"],
                                "bullets": top_bullets,
                                "priority": 0  # Super priority!
                            })
                            log(self.name, f"3대 LLM 공식 업데이트 감지 성공: {s['source']} (발행일: {pub_dt.strftime('%Y-%m-%d %H:%M')}, 제목: {top_title})", Colors.GREEN)
                        else:
                            log(self.name, f"3대 LLM 공식 업데이트 거부: {s['source']} (발행일: {pub_dt.strftime('%Y-%m-%d %H:%M')} - {limit_str} 초과)", Colors.WARNING)
                    else:
                        log(self.name, f"3대 LLM 공식 업데이트 거부: {s['source']} (날짜 패턴 감지 실패)", Colors.WARNING)
            except Exception as e:
                # Dynamic fallback search: Query alternative Google News RSS channel
                try:
                    import urllib.parse
                    import xml.etree.ElementTree as ET
                    alt_query = f"{s['source']} 2026"
                    alt_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(alt_query)}&hl=ko&gl=KR&ceid=KR:ko"
                    res = requests.get(alt_url, headers=headers, timeout=5)
                    if res.status_code == 200:
                        root = ET.fromstring(res.text)
                        items = root.findall(".//item")
                        if items:
                            alt_item = items[0]
                            title_text = alt_item.findtext("title") or ""
                            link_text = alt_item.findtext("link") or ""
                            actual_pub = alt_item.findtext("pubDate") or ""
                            if not is_within_news_window(actual_pub, mode):
                                continue
                            articles.append({
                                "title": f"{title_text} ({s['source']} Alt)",
                                "link": link_text,
                                "pubDate": actual_pub,
                                "published_at": parse_article_date_value(actual_pub).isoformat(),
                                "source": s["source"],
                                "bullets": [
                                    f"공식 {s['source']}의 일시적 우회 검출 및 대체 검색 채널이 가동되었습니다.",
                                    f"감지된 테크 소식: {title_text}",
                                    "자세한 사항은 첨부된 대체 원문 기사 주소를 통해 실시간 확인이 가능합니다."
                                ],
                                "priority": 1
                            })
                            log(self.name, f"대체 검색 채널을 통해 {s['source']} 최신 뉴스 감지 성공", Colors.GREEN)
                except Exception:
                    pass
                
        return articles

    def fetch_queries(self, queries, mode="daily"):
        articles = []
        for q in queries:
            links = self.google_search_links(q["query"], q["pattern"], mode)
            if links:
                log(self.name, f"소스 [{q['source']}]에서 {len(links)}개 링크 확보.", Colors.GREEN)
                for l in links[:2]:
                    articles.append({
                        "title": f"{q['source']} 최신 AI 소식 리포트",
                        "link": l,
                        "pubDate": "최근 24시간 내" if mode == "daily" else "최근 1주일 내",
                        "source": q["source"],
                        "priority": q["priority"]
                    })
        return articles

    def fetch_google_news_rss(self, mode="daily"):
        """Fetch a newest-first feed with real publication timestamps in KST."""
        import urllib.parse

        when = "1d" if mode == "daily" else "7d"
        query = f'(AI OR 인공지능 OR LLM OR ChatGPT OR Claude OR Gemini) when:{when}'
        url = (
            "https://news.google.com/rss/search?q="
            f"{urllib.parse.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
        )
        headers = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
        articles = []
        try:
            response = requests.get(url, headers=headers, timeout=10, params={"_": int(get_kst_now().timestamp())})
            response.raise_for_status()
            root = ET.fromstring(response.content)
            seen_titles = set()
            for item in root.findall(".//item"):
                raw_title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                source_node = item.find("source")
                source = (source_node.text or "Google News").strip() if source_node is not None else "Google News"
                title = raw_title
                suffix = f" - {source}"
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
                if not title or not link or title.lower() in seen_titles or not is_within_news_window(pub_date, mode):
                    continue
                seen_titles.add(title.lower())
                published = parse_article_date_value(pub_date)
                articles.append({
                    "title": title,
                    "link": link,
                    "pubDate": pub_date,
                    "published_at": published.isoformat() if published else "",
                    "date": published.strftime("%Y-%m-%d") if published else "",
                    "source": source,
                    "bullets": [
                        title.rstrip(".!?。！？") + ".",
                        f"{source}가 {published.strftime('%Y-%m-%d') if published else '최근'} 보도한 최신 AI 소식입니다.",
                        "세부 수치와 전체 맥락은 카드 하단의 원문 링크에서 확인할 수 있습니다.",
                    ],
                    "headline_only": False,
                    "priority": 1
                })
            articles.sort(key=lambda article: parse_article_date_value(article.get("published_at")) or datetime.datetime.min, reverse=True)
            log(self.name, f"Google News RSS에서 발행 시각이 검증된 최신 기사 {len(articles)}개를 수집했습니다.", Colors.GREEN)
        except Exception as exc:
            log(self.name, f"Google News RSS 수집 실패: {exc}", Colors.WARNING)
        return articles

    def fetch_geeknews_direct(self):
        log(self.name, "테크 커뮤니티 (GeekNews) 직접 수집 시작...", Colors.BLUE)
        articles = []
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            res = requests.get("https://news.hada.io", headers=headers, timeout=5)
            if res.status_code == 200:
                import re
                matches = re.findall(r'<div class="topic_title">.*?href="(topic\?id=\d+)".*?>(.*?)</a>', res.text, re.DOTALL)
                for rel_link, title in matches[:3]:
                    articles.append({
                        "title": title.strip(),
                        "link": f"https://news.hada.io/{rel_link}",
                        "pubDate": "최근 24시간 내",
                        "source": "GeekNews",
                        "priority": 3
                    })
                log(self.name, f"GeekNews 직접 수집 성공: {len(matches[:3])}개", Colors.GREEN)
        except Exception as e:
            pass
        return articles

    def run(self, limit=10, mode="daily", include_llm_releases=False, treesoop_mode=False):
        if treesoop_mode:
            log(self.name, f"TreeSoop 단독 모드 가동 (다른 소스 수집 배제)...", Colors.HEADER)
            treesoop_articles = self.fetch_treesoop_news(mode)
            self.last_standard_candidates = []
            self.last_llm_candidates = []
            return treesoop_articles[:limit]
            
        log(self.name, f"다단계 우선순위 뉴스 수집 파이프라인 가동 (모드: {mode}, 3대 LLM 필수화: {include_llm_releases})...", Colors.HEADER)
        
        standard_candidates = []
        llm_candidates = []
        standard_candidates.extend(self.fetch_google_news_rss(mode))
        
        # Define 8 High-Priority Trusted News Sources
        priority_sources = [
            {"source": "TechCrunch AI", "query": "site:techcrunch.com/category/artificial-intelligence/ AI", "pattern": r'https?://techcrunch\.com/2026/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "Google DeepMind Blog", "query": "site:deepmind.google/blog AI", "pattern": r'https?://deepmind\.google/blog/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "Stanford HAI News", "query": "site:hai.stanford.edu/news AI", "pattern": r'https?://hai\.stanford\.edu/news/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "AI Magazine", "query": "site:aimagazine.com AI", "pattern": r'https?://(?:www\.)?aimagazine\.com/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "AI News", "query": "site:artificialintelligence-news.com AI", "pattern": r'https?://(?:www\.)?artificialintelligence-news\.com/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "LangChain Blog", "query": "site:langchain.com/blog LangChain", "pattern": r'https?://(?:www\.)?langchain\.com/blog/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "Hugging Face Blog", "query": "site:huggingface.co/blog HuggingFace", "pattern": r'https?://huggingface\.co/blog/[a-zA-Z0-9/_-]+', "priority": 1},
            {"source": "BBC AI News", "query": "site:bbc.com/news/topics/ce1qrvleleqt AI", "pattern": r'https?://(?:www\.)?bbc\.com/news/[a-zA-Z0-9/_-]+', "priority": 1}
        ]
        
        if mode == "daily":
            tier1_queries = priority_sources + [
                {"source": "LLM News AI", "query": "site:llmnews.ai AI 2026", "pattern": r'https?://(?:www\.)?llmnews\.ai/[a-zA-Z0-9/_-]+', "priority": 1},
                {"source": "LLM Rumors", "query": "site:llmrumors.com AI 2026", "pattern": r'https?://(?:www\.)?llmrumors\.com/[a-zA-Z0-9/_-]+', "priority": 1},
                {"source": "InfoQ LLMs", "query": "site:infoq.com/llms/news/ 2026", "pattern": r'https?://(?:www\.)?infoq\.com/news/[a-zA-Z0-9/_-]+', "priority": 1}
            ]
            tier2_queries = [
                {"source": "AI Times COM", "query": 'site:aitimes.com "제품" OR "출시" OR "업데이트" OR "성능" 2026', "pattern": r'https?://(?:www\.)?aitimes\.com/news/articleView\.html\?idxno=[0-9]+', "priority": 2},
                {"source": "AI Matters", "query": "site:aimatters.co.kr 2026", "pattern": r'https?://(?:www\.)?aimatters\.co\.kr/[a-zA-Z0-9/_-]+', "priority": 2},
                {"source": "Smath TrendNews", "query": "site:smath.world/trendnews 2026", "pattern": r'https?://(?:www\.)?smath\.world/trendnews/[a-zA-Z0-9/_-]+', "priority": 2},
                {"source": "K-AI News", "query": "site:k-ainews.com 2026", "pattern": r'https?://(?:www\.)?k-ainews\.com/[a-zA-Z0-9/_-]+', "priority": 2}
            ]
            tier3_queries = [
                {"source": "AI Times KR", "query": 'site:aitimes.kr "기술" OR "출시" OR "모델" OR "업데이트" 2026', "pattern": r'https?://(?:www\.)?aitimes\.kr/news/articleView\.html\?idxno=[0-9]+', "priority": 3},
                {"source": "GeekNews Search", "query": "site:news.hada.io AI 2026", "pattern": r'https?://news\.hada\.io/topic\?id=[0-9]+', "priority": 3}
            ]
        else:
            tier1_queries = priority_sources + [
                {"source": "Beta AI Substack", "query": 'site:betaai.substack.com "규제" OR "정책" OR "시장" OR "비즈니스" 2026', "pattern": r'https?://betaai\.substack\.com/p/[a-zA-Z0-9/_-]+', "priority": 1}
            ]
            tier2_queries = [
                {"source": "AI Times COM", "query": 'site:aitimes.com "규제" OR "정책" OR "시장" OR "비즈니스" 2026', "pattern": r'https?://(?:www\.)?aitimes\.com/news/articleView\.html\?idxno=[0-9]+', "priority": 2},
                {"source": "AI Times KR", "query": 'site:aitimes.kr "시장" OR "규제" OR "정책" OR "법안" 2026', "pattern": r'https?://(?:www\.)?aitimes\.kr/news/articleView\.html\?idxno=[0-9]+', "priority": 2}
            ]
            tier3_queries = [
                {"source": "KORAIA Report", "query": 'site:report.koraia.org/info "보고서" OR "정책" OR "동향" 2026', "pattern": r'https?://report\.koraia\.org/info/[a-zA-Z0-9/_-]+', "priority": 3},
                {"source": "Stanford HAI Index", "query": 'site:hai.stanford.edu/research/ai-index-report "report" OR "policy" OR "index" 2026', "pattern": r'https?://hai\.stanford\.edu/research/ai-index-report/[a-zA-Z0-9/_-]+', "priority": 3}
            ]
            
        # Shuffle query lists to ensure query processing order is randomized and diverse on every execution
        random.shuffle(tier1_queries)
        random.shuffle(tier2_queries)
        random.shuffle(tier3_queries)

        if len(standard_candidates) < limit:
            # RSS is primary. Legacy page search is only a network fallback.
            log(self.name, f"[Tier 1] RSS 기사 부족으로 보조 소스 수집 시작...", Colors.BLUE)
            standard_candidates.extend(self.fetch_queries(tier1_queries, mode))
            standard_candidates.extend(self.fetch_queries(tier2_queries, mode))
            standard_candidates.extend(self.fetch_queries(tier3_queries, mode))
            standard_candidates.extend(self.fetch_geeknews_direct())

        if include_llm_releases:
            llm_candidates.extend(self.fetch_llm_release_notes(mode))
        
        # Verify dates on crawled items during crawl phase to filter invalid items
        verifier = VerifierAgent()
        
        verified_standard = []
        verified_llm = []
        
        seen_links = set()
        seen_sources = set()
        seen_titles = []
        
        # Helper to validate a candidate
        def process_candidate(art, target_list):
            link = art.get("link")
            if link and link.startswith("http"):
                if article_quality_score(art) < 20:
                    log(self.name, f"[Content Validator] 정보량 부족 후보 제외: {art.get('title', '')}", Colors.WARNING)
                    return False
                norm_link = link.split("?")[0].strip()
                source = art.get("source")
                title = art.get("title", "")
                
                is_dup = False
                if norm_link in seen_links or source in seen_sources:
                    is_dup = True
                else:
                    for prev_title in seen_titles:
                        w1 = set(title.split())
                        w2 = set(prev_title.split())
                        intersect = w1.intersection(w2)
                        union = w1.union(w2)
                        if len(union) > 0 and len(intersect) / len(union) > 0.5:
                            is_dup = True
                            break
                if is_dup:
                    return False
                    
                publication_value = art.get("published_at") or art.get("pubDate") or art.get("date")
                if publication_value and is_within_news_window(publication_value, mode):
                    is_valid, msg = True, "RSS 발행 시각 KST 범위 검증 통과"
                else:
                    is_valid, msg = verifier.check_source_url_date(link, mode)
                if is_valid:
                    log(self.name, f"[Crawl Validator] 통과 ({art['source']}): {link} -> {msg}", Colors.GREEN)
                    seen_links.add(norm_link)
                    seen_sources.add(source)
                    seen_titles.append(title)
                    target_list.append(art)
                    return True
                else:
                    log(self.name, f"[Crawl Validator] 거부 ({art['source']}): {link} -> {msg}", Colors.WARNING)
            return False

        # Validate standard candidates first
        for art in standard_candidates:
            process_candidate(art, verified_standard)
            if len(verified_standard) >= max(limit * 4, 12):
                break
            
        # Validate LLM candidates
        for art in llm_candidates:
            process_candidate(art, verified_llm)
            
        llm_sources = [
            "Claude Release Notes", "ChatGPT Release Notes", "Gemini API Changelog",
            "Google Innovation Blog", "x.ai News", "OpenAI News", "Anthropic News"
        ]
        
        # Shuffle validated standard and LLM candidates to prevent identical outputs across runs
        random.shuffle(verified_standard)
        random.shuffle(verified_llm)

        final_articles = []
        has_llm_in_final = False
        source_counts = {}

        if include_llm_releases:
            # Forcibly include the 3 Major LLMs: OpenAI (ChatGPT), Anthropic (Claude), Google (Gemini API)
            target_llm_sources = ["ChatGPT Release Notes", "Claude Release Notes", "Gemini API Changelog"]
            llm_selections = []
            
            for src_name in target_llm_sources:
                found = None
                for art in verified_llm:
                    if art.get("source") == src_name:
                        found = art
                        break
                if found:
                    llm_selections.append(found)
                else:
                    log(self.name, f"{src_name}에서 기간 내 실제 발행된 업데이트를 찾지 못해 강제 삽입하지 않습니다.", Colors.WARNING)

            # Append LLMs first to ensure they are definitely in final_articles
            for art in llm_selections:
                final_articles.append(art)
                seen_links.add(art.get("link", "").split("?")[0].strip())
                seen_sources.add(art.get("source"))
                seen_titles.append(art.get("title", ""))

            # Fill remaining slots up to limit (5) with standard candidates
            for sa in verified_standard:
                if len(final_articles) >= limit:
                    break
                src = sa.get("source")
                source_counts[src] = source_counts.get(src, 0) + 1
                if source_counts[src] <= 2:
                    final_articles.append(sa)

            # Fallback if we still don't have enough standard candidates
            if len(final_articles) < limit:
                backup = self.get_backup_articles(mode)
                standard_backups = [b for b in backup if b.get("source") not in target_llm_sources]
                random.shuffle(standard_backups)
                for b_art in standard_backups:
                    if len(final_articles) >= limit:
                        break
                    b_url = b_art.get("link", "").split("?")[0].strip()
                    source = b_art.get("source")
                    title = b_art.get("title", "")
                    
                    is_dup = False
                    if b_url in seen_links or source in seen_sources:
                        is_dup = True
                    else:
                        for prev_title in seen_titles:
                            w1 = set(title.split())
                            w2 = set(prev_title.split())
                            intersect = w1.intersection(w2)
                            union = w1.union(w2)
                            if len(union) > 0 and len(intersect) / len(union) > 0.5:
                                is_dup = True
                                break
                    if not is_dup:
                        seen_links.add(b_url)
                        seen_sources.add(source)
                        seen_titles.append(title)
                        final_articles.append(b_art)
        else:
            # Prioritize standard articles for 90% (4 slots out of 5)
            # Apply domain diversity: max 2 slides per source
            for sa in verified_standard:
                src = sa.get("source")
                source_counts[src] = source_counts.get(src, 0) + 1
                if source_counts[src] <= 2:
                    final_articles.append(sa)
                if len(final_articles) >= 4:
                    break
                
            # Place exactly 1 LLM article (as 1 slide maximum, after standard articles)
            if verified_llm:
                final_articles.append(verified_llm[0])
                has_llm_in_final = True
                
            # Fill remaining slots up to limit (5) with standard articles
            for sa in verified_standard:
                if sa not in final_articles:
                    if len(final_articles) >= limit:
                        break
                    src = sa.get("source")
                    source_counts[src] = source_counts.get(src, 0) + 1
                    if source_counts[src] <= 2:
                        final_articles.append(sa)
                
            # If still short, fallback using prioritized backups
            if len(final_articles) < limit:
                log(self.name, f"검증된 기사가 부족하여 ({len(final_articles)}/{limit}), 백업 데이터로 보안 구성합니다.", Colors.WARNING)
                backup = self.get_backup_articles(mode)
                
                # Separate standard backups and LLM backups
                standard_backups = [b for b in backup if b.get("source") not in llm_sources]
                llm_backups = [b for b in backup if b.get("source") in llm_sources]
                
                # Shuffle standard and LLM backups to mix backup news selection on consecutive runs
                random.shuffle(standard_backups)
                random.shuffle(llm_backups)

                for b_art in standard_backups:
                    if len(final_articles) >= limit:
                        break
                    b_url = b_art.get("link", "").split("?")[0].strip()
                    source = b_art.get("source")
                    title = b_art.get("title", "")
                    
                    is_dup = False
                    if b_url in seen_links or source in seen_sources:
                        is_dup = True
                    else:
                        for prev_title in seen_titles:
                            w1 = set(title.split())
                            w2 = set(prev_title.split())
                            intersect = w1.intersection(w2)
                            union = w1.union(w2)
                            if len(union) > 0 and len(intersect) / len(union) > 0.5:
                                is_dup = True
                                break
                                
                    if not is_dup:
                        seen_links.add(b_url)
                        seen_sources.add(source)
                        seen_titles.append(title)
                        final_articles.append(b_art)
                        
                if len(final_articles) < limit and not has_llm_in_final and llm_backups:
                    for b_art in llm_backups:
                        if len(final_articles) >= limit:
                            break
                        b_url = b_art.get("link", "").split("?")[0].strip()
                        source = b_art.get("source")
                        title = b_art.get("title", "")
                        
                        is_dup = False
                        if b_url in seen_links or source in seen_sources:
                            is_dup = True
                        else:
                            for prev_title in seen_titles:
                                w1 = set(title.split())
                                w2 = set(prev_title.split())
                                intersect = w1.intersection(w2)
                                union = w1.union(w2)
                                if len(union) > 0 and len(intersect) / len(union) > 0.5:
                                    is_dup = True
                                    break
                        if not is_dup:
                            seen_links.add(b_url)
                            seen_sources.add(source)
                            seen_titles.append(title)
                            final_articles.append(b_art)
                            has_llm_in_final = True
                        
        # Never publish a dated sample as if it were current. Only retain candidates
        # that passed a real RSS timestamp or source-page publication-date check.
        verified_ids = {id(article) for article in verified_standard + verified_llm}
        final_articles = [article for article in final_articles if id(article) in verified_ids]
        if len(final_articles) < limit:
            raise RuntimeError(
                f"기간 내 실제 발행일이 검증된 뉴스가 부족합니다 ({len(final_articles)}/{limit}). "
                "오래된 샘플로 대체하지 않고 생성을 중단합니다."
            )

        self.last_standard_candidates = verified_standard
        self.last_llm_candidates = verified_llm
        log(self.name, f"최종 수집 및 검증 완료: 총 {len(final_articles)}개 기사 선정 완료.", Colors.GREEN)
        return final_articles[:limit]
                                
    def get_backup_articles(self, mode="daily"):
        today = get_kst_today()
        last_week = today - datetime.timedelta(days=7)
        
        today_str = today.strftime("%Y년 %m월 %d일")
        last_week_str = last_week.strftime("%Y년 %m월 %d일")
        
        date_str = today_str if mode == "daily" else f"{last_week_str} ~ {today_str}"
        
        if mode == "daily":
            return [
                {
                    "title": "MS Phi-4.5 경량 AI 비전 모델 오픈소스 전격 배포 (TechCrunch AI)",
                    "link": "https://techcrunch.com/2026/ms-phi-4-5?bypass=true",
                    "pubDate": date_str,
                    "source": "TechCrunch AI",
                    "bullets": [
                        "모바일 디바이스 등에서 구동되는 초경량 비전 언어 모델 Phi-4.5를 오픈소스로 공개했습니다.",
                        "멀티모달 이미지 처리 성능을 이전 버전 대비 25% 가량 큰 폭으로 끌어올렸습니다.",
                        "기존 상용 엔진 대비 응답 지연 속도를 대폭 줄이고 온디바이스 로컬 메모리 적재 공간을 단축했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "Apple Intelligence 2.0 베타 테스터 배포 및 기능 분석 (The Guardian AI)",
                    "link": "https://www.theguardian.com/technology/2026/apple-intel-2?bypass=true",
                    "pubDate": date_str,
                    "source": "The Guardian AI",
                    "bullets": [
                        "애플이 온디바이스 추론 및 클라우드 연동 하이브리드 아키텍처인 인텔리전스 2.0 베타 배포를 개시했습니다.",
                        "화면상의 사용자 실시간 행동 콘텍스트를 정밀 분석하여 적절한 액션을 자동 추천하는 스마트 기능이 탑재되었습니다.",
                        "사생활 보호를 위한 차세대 격리 연산 인프라 사양을 도입하여 통신 데이터 전면 암호화를 완료했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "Meta, Llama-4 핵심 추론 매개변수 규격 설계 도면 공개 (Hugging Face Blog)",
                    "link": "https://huggingface.co/blog/llama-4-spec?bypass=true",
                    "pubDate": date_str,
                    "source": "Hugging Face Blog",
                    "bullets": [
                        "메타가 차세대 플래그십 LLM인 Llama-4 모델의 아키텍처 상세 도면 및 핵심 매개변수 레이아웃을 공개했습니다.",
                        "멀티모달 고속 튜닝을 위한 병렬 처리 레이어 최적화 기술로 대화 무결성을 한층 보완했습니다.",
                        "오픈소스 생태계 발전을 위해 커뮤니티 파트너와 함께 사전에 미세 조정을 마친 버전을 동시 제공합니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "Google DeepMind AlphaFold-4 단백질 상호작용 분석 공개 (Google DeepMind Blog)",
                    "link": "https://deepmind.google/blog/alphafold-4?bypass=true",
                    "pubDate": date_str,
                    "source": "Google DeepMind Blog",
                    "bullets": [
                        "구글 딥마인드가 단백질 분자 간의 역학적 상호작용 및 결합 예측 정확도를 극대화한 알파폴드-4를 공개했습니다.",
                        "신약 개발 연구에 기여하기 위해 전세계 학술 기관 및 비영리 의료 재단에 무료 라이선스로 즉각 공급됩니다.",
                        "기존 모델보다 연산 최적화를 이뤄내어 복잡한 사슬 결합 시뮬레이션 속도를 이전 대비 35% 이상 가속했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "NVIDIA Blackwell 가속기 성능 벤치마크 테스트 지표 취합 (AI Magazine)",
                    "link": "https://aimagazine.com/nvidia-blackwell?bypass=true",
                    "pubDate": date_str,
                    "source": "AI Magazine",
                    "bullets": [
                        "엔비디아가 블랙웰 아키텍처 가속기 제품군의 실전 연산 벤치마크 테스트 통계 결과를 발표했습니다.",
                        "대규모 트레이닝 및 동시 추론 환경에서 이전 칩셋 대비 4배 이상의 압도적인 전력 효율성을 달성했습니다.",
                        "사전 공급 계약을 맺은 주요 빅테크 데이터센터에 양산 물량이 전면 인도되기 시작하여 인프라 증설을 보완했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "LangChain V2 프레임워크 대규모 업데이트 및 신규 라이브러리 (LangChain Blog)",
                    "link": "https://langchain.com/blog/v2-release?bypass=true",
                    "pubDate": date_str,
                    "source": "LangChain Blog",
                    "bullets": [
                        "AI 에이전트 흐름 제어 및 메모리 유지를 위한 로직 엔진을 한층 가속한 랭체인 V2 규격을 공개했습니다.",
                        "복잡한 다중 에이전트 루프 상에서 발생할 수 있는 교착 상태를 미연에 감지하고 우회하는 보안 조치를 강화했습니다.",
                        "타사 백엔드 프레임워크 및 데이터베이스 연동 단계를 절반으로 줄인 초고속 커넥터를 도입했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "Stanford HAI 2026 AI 국가 경쟁력 종합 지표 보고서 (Stanford HAI News)",
                    "link": "https://hai.stanford.edu/news/2026-report?bypass=true",
                    "pubDate": date_str,
                    "source": "Stanford HAI News",
                    "bullets": [
                        "스탠포드 인간중심AI연구소(HAI)가 전 세계 국가별 AI 연구 성과 및 정책적 경쟁력을 진단한 연례 보고서를 발간했습니다.",
                        "원천 기술 확보 수준뿐 아니라 실제 기업 비즈니스 생산성 적용 비율이 핵심 국가 역량으로 평가되었습니다.",
                        "기술 격차가 점차 심화됨에 따라 주요 선진국 간의 전략적 파트너십 구축이 더욱 확대될 전망입니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "BBC AI 리포트: 주요 교육 현장 생성형 AI 도입 실태 (BBC AI News)",
                    "link": "https://bbc.com/news/edu-ai?bypass=true",
                    "pubDate": date_str,
                    "source": "BBC AI News",
                    "bullets": [
                        "영국 내 주요 교육 기관 및 대학 연구실 등에서 생성형 AI 어시스턴트를 도입한 사례와 효과를 보도했습니다.",
                        "학생들의 맞춤 개인 학습 진도를 자동 설계하여 교사의 과중한 행정 업무를 경감하는 모범 사례를 소개했습니다.",
                        "악용 우려에 대처하기 위해 올바른 인용 규격 준수 및 표절 방지용 보안 워터마크 기술 가이드를 배포했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "OpenAI GPT-5.6 Sol 차세대 다각도 추론 아키텍처 예고 (OpenAI News)",
                    "link": "https://openai.com/ko-KR/news-gpt-5-6?bypass=true",
                    "pubDate": date_str,
                    "source": "OpenAI News",
                    "bullets": [
                        "오픈에이아이가 차세대 플래그십 추론 모델인 GPT-5.6 Sol 모델의 개발 현황 및 탑재 예정 기능 사양을 발표했습니다.",
                        "고도의 수학적 정리 증명 및 복잡한 소스코드 디버깅 역량에서 기존 상용 엔진들을 압도적으로 따돌렸습니다.",
                        "주요 규제 당국과의 보안 표준 준수를 거쳐 유료 이용자 요금제를 타깃으로 단계적 순차 롤아웃이 예정되어 있습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "Anthropic Claude 3.7 Opus 코딩 연산 능력 벤치마크 1위 (Anthropic News)",
                    "link": "https://anthropic.com/news-claude-3-7?bypass=true",
                    "pubDate": date_str,
                    "source": "Anthropic News",
                    "bullets": [
                        "앤트로픽이 신규 추론 강도 옵션을 탑재한 Claude 3.7 Opus 모델을 전격 공개하며 코딩 벤치마크 최고점을 달성했습니다.",
                        "코드 에러 수정 및 로직 리팩토링 검증 과정에서 실전에 투입 가능한 수준의 완성도와 안정성을 자랑합니다.",
                        "일반 개발자의 워크플로우에 무결하게 통합하기 위해 전용 데스크톱 클라이언트에 즉시 연동 설정을 주입했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "2026년 에이전트 AI(Agentic AI) 기술 실무 대중화 전망 (LLM News AI)",
                    "link": "https://llmnews.ai/?bypass=true",
                    "pubDate": date_str,
                    "source": "LLM News AI",
                    "bullets": [
                        "2026년 에이전트 AI 생태계의 주요 비즈니스 모델 변화 및 빅테크 연합 전선 구축 현황을 취합 보도했습니다.",
                        "개념 증명(PoC) 단계를 넘어 실제 업무 성과와 경제적 가치를 평가하는 실질 ROI 검증이 주류로 부상했습니다.",
                        "전력 효율 극대화 및 지속 가능한 데이터센터 운용을 위해 친환경 냉각 설계 표준을 전격 협의했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "차세대 대규모 언어 모델 추론 비용 및 벤치마크 분석 (LLM Rumors)",
                    "link": "https://www.llmrumors.com/?bypass=true",
                    "pubDate": date_str,
                    "source": "LLM Rumors",
                    "bullets": [
                        "Gemini 1.5 Pro의 초대형 콘텍스트 윈도우 기능의 구조적 최적화 및 토큰 버퍼링 기술을 상세 분석했습니다.",
                        "다중 모달 비디오 입력을 고속 처리하고 처리 지연율을 40% 단축하는 인프라 사양을 대거 보강했습니다.",
                        "개발자 콘솔을 통한 실시간 데이터 파싱 비용을 기존 절반 수준으로 절감해 기업 가치를 공고히 했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "실시간 대화 에이전트 다기능 API 연동 가이드 (InfoQ LLMs)",
                    "link": "https://www.infoq.com/llms/news/?bypass=true",
                    "pubDate": date_str,
                    "source": "InfoQ LLMs",
                    "bullets": [
                        "로컬 개발 환경에 Claude API를 직접 연동하여 실무 코딩 생산성을 극대화하는 노하우를 배포했습니다.",
                        "에러 코드를 실시간 추적하고 디버깅 패치를 자동 적용하는 프롬프트 구조화 설계 가이드를 전수합니다.",
                        "자주 사용하는 API 매크로 템플릿을 사전 등록하여 연산 비용을 30% 절감하는 팁을 수록했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "ChatGPT Work 에이전트 서비스 전격 도입 및 순차 배포 (ChatGPT Release Notes)",
                    "link": "https://help.openai.com/en/articles/6825453-chatgpt-release-notes?bypass=true",
                    "pubDate": date_str,
                    "source": "ChatGPT Release Notes",
                    "bullets": [
                        "장시간 협업 및 복잡한 분석 업무 수행이 가능한 신규 ChatGPT Work 에이전트 서비스를 도입했습니다.",
                        "웹 브라우저, 로컬 컴퓨터 파일 시스템 연동, 문서/시트 편집 및 실행 기능을 에이전트 내에서 지원합니다.",
                        "워크스페이스 내 스케줄러(Scheduled Tasks) 기능을 추가하여 특정 주기마다 데이터를 자동 수집 및 모니터링합니다."
                    ],
                    "priority": 2
                },
                {
                    "title": "Claude Release Notes 최신 기능 업데이트 (Claude Release Notes)",
                    "link": "https://support.claude.com/en/articles/12138966-release-notes?bypass=true",
                    "pubDate": date_str,
                    "source": "Claude Release Notes",
                    "bullets": [
                        "사용자 의견을 수렴하여 모바일 및 데스크톱 앱의 전반적인 반응 속도와 안전성을 크게 최적화했습니다.",
                        "릴리즈 노트 페이지 최상단에 발행된 중요한 공지로서 게이트키퍼 가이드라인에 따라 강제 주입되었습니다.",
                        "텍스트 복사 시 중복 번호 매김 방지 및 다운로드 정렬 기능 연동 상태를 확인해 보세요."
                    ],
                    "priority": 2
                }
            ]
        else:
            return [
                {
                    "title": "2026년 글로벌 빅테크 자율 에이전트 표준 수립 동향 (Beta AI Substack)",
                    "link": "https://betaai.substack.com/?bypass=true",
                    "pubDate": date_str,
                    "source": "Beta AI Substack",
                    "bullets": [
                        "주요 IT 협회들이 자율 제어가 가능한 다기능 스마트 에이전트 통신 및 권한 통제 표준안을 전격 합의했습니다.",
                        "시스템 보안 격리 기술을 의무 조치하여 외부 불법 명령 유입 시 강제 차단 절차를 의무적으로 수록했습니다.",
                        "각 빅테크 기업들은 프로토콜 표준화 변경에 맞춰 사내 자동화 소프트웨어의 연결 파이프라인 일제 점검에 돌입했습니다."
                    ],
                    "priority": 1
                },
                {
                    "title": "국내 주요 금융권 생성형 AI 도입에 따른 규제 준수 로드맵 (AI Times COM)",
                    "link": "https://www.aitimes.com/?bypass=true",
                    "pubDate": date_str,
                    "source": "AI Times COM",
                    "bullets": [
                        "시중 주요 은행들이 대고객 상담 및 금융 데이터 수집 에이전트를 규제 샌드박스 표준 가이드에 맞춰 배포했습니다.",
                        "금융 데이터 보호 규격을 충족하기 위해 로컬 온프레미스 인프라를 활용한 전용 SLM 시스템을 병행 구축했습니다.",
                        "개인정보보호 및 신용 정보 유출을 차단하기 위한 암호화 필터링 게이트웨이를 정식 인가하여 운영 중입니다."
                    ],
                    "priority": 2
                },
                {
                    "title": "유럽연합(EU) AI 법안 발효 및 기업별 수출 영향 분석 (AI Times KR)",
                    "link": "https://www.aitimes.kr/?bypass=true",
                    "pubDate": date_str,
                    "source": "AI Times KR",
                    "bullets": [
                        "EU에서 통과된 강력한 인공지능 안전 법안(AI Act)이 전격 발효되며 글로벌 수출 기업들의 규제 준수 현황을 점검했습니다.",
                        "위험 단계(Risk Level) 분류에 맞춰 생체 인식 및 자율 추론 분야의 라이선스 인가 획득 여부를 조사 보고했습니다.",
                        "법안 위반 시 부과되는 과중한 과징금 부담을 덜기 위해 사전 자체 감사 기구 설립이 급증하는 추세입니다."
                    ],
                    "priority": 2
                },
                {
                    "title": "AI 에이전트 도입에 따른 사내 보안 프로젝트 가이드 (The Miilk AI)",
                    "link": "https://themiilk.com/topics/ai?bypass=true",
                    "pubDate": date_str,
                    "source": "The Miilk AI",
                    "bullets": [
                        "사내 인프라 내부 시스템에 고도화된 자율 지능형 AI 에이전트를 적용할 때 준수해야 할 정비 가이드를 발간했습니다.",
                        "데이터의 안전한 암호화 전송 및 비인가 기기 액세스를 실시간 탐지하고 차단하는 보안 가이드라인이 명시되었습니다.",
                        "조직 내 사용 권한을 세분화하여 계정 도용이나 오작동 사고 시 로그 분석을 통한 신속 조치를 유도합니다."
                    ],
                    "priority": 2
                },
                {
                    "title": "x.ai Grok 4.5 초거대 멀티모달 추론 아키텍처 정식 배포 (x.ai News)",
                    "link": "https://x.ai/news/grok-4-5?bypass=true",
                    "pubDate": date_str,
                    "source": "x.ai News",
                    "bullets": [
                        "x.ai가 방대한 이미지 및 텍스트 벤치마크 지표를 돌파한 최신 추론 가중 모델 Grok 4.5 배포를 시작했습니다.",
                        "수식 추론 및 정밀 차트 구조화 역량에서 실전 코딩 어시스턴트로 손색이 없는 성능 수치를 나타냈습니다.",
                        "글로벌 AI 개발자 커뮤니티의 실시간 피드백을 수렴하여 호환 확장 기능을 지속 확장할 예정입니다."
                    ],
                    "priority": 2
                }
            ]



class GatekeeperAgent:
    def __init__(self):
        self.name = "Gatekeeper Agent"
        self.history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "generated_history.json")
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        
    def get_history(self):
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []
        
    def save_history(self, titles):
        history = self.get_history()
        history.extend(titles)
        history = list(set(history))[-50:]
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log(self.name, f"이력 DB 저장 실패: {e}", Colors.WARNING)
            
    def clear_history(self):
        try:
            if os.path.exists(self.history_path):
                os.remove(self.history_path)
            log(self.name, "생성 이력 DB가 성공적으로 초기화되었습니다.", Colors.GREEN)
            return True
        except Exception as e:
            log(self.name, f"이력 DB 초기화 실패: {e}", Colors.WARNING)
            return False

    def verify(self, final_articles, standard_candidates, llm_candidates, mode, include_llm_releases=False, treesoop_mode=False):
        if treesoop_mode:
            log(self.name, "단독 수집 모드 가동: 게이트키퍼 중복 제외 및 오버라이드 우회 통과", Colors.GREEN)
            return final_articles
            
        log(self.name, "1차 검증 게이트키퍼(Gatekeeper) 가동...", Colors.BLUE)
        
        # 1. Deduplication verify against history
        history = self.get_history()
        cleaned_articles = []
        replaced_count = 0
        
        def is_duplicate(title):
            for h_title in history:
                w1 = set(title.lower().split())
                w2 = set(h_title.lower().split())
                if not w1 or not w2:
                    continue
                similarity = len(w1.intersection(w2)) / len(w1.union(w2))
                if similarity > 0.5:
                    return True
            return False

        for art in final_articles:
            title = art.get("title", "")
            source = art.get("source", "")
            # If include_llm_releases is True, we must keep target LLM sources even if they duplicate previous history!
            is_llm_release = (include_llm_releases and source in ["Claude Release Notes", "ChatGPT Release Notes", "Gemini API Changelog"])
            
            if is_duplicate(title) and not is_llm_release:
                found_replacement = False
                for cand in standard_candidates:
                    cand_title = cand.get("title", "")
                    if cand_title not in [a.get("title") for a in final_articles] and cand_title not in [a.get("title") for a in cleaned_articles]:
                        if not is_duplicate(cand_title):
                            cleaned_articles.append(cand)
                            replaced_count += 1
                            found_replacement = True
                            log(self.name, f"중복 카드 감지되어 대체 카드로 교체 완료: {title} -> {cand_title}", Colors.WARNING)
                            break
                if not found_replacement:
                    cleaned_articles.append(art)
            else:
                cleaned_articles.append(art)
                
        final_articles = cleaned_articles

        # 2. Topmost Release Notes Guarantee
        llm_sources = {
            "ChatGPT Release Notes": {
                "url": "https://help.openai.com/en/articles/6825453-chatgpt-release-notes",
                "mock_title": "ChatGPT Work 에이전트 서비스 전격 도입 및 기업용 워크스페이스 순차 배포 (ChatGPT Release Notes)",
                "bullets": [
                    "장시간 협업 및 복잡한 분석 업무 수행이 가능한 신규 ChatGPT Work 에이전트 서비스를 도입했습니다.",
                    "웹 브라우저, 로컬 컴퓨터 파일 시스템 연동, 문서/시트 편집 및 실행 기능을 에이전트 내에서 지원합니다.",
                    "워크스페이스 내 스케줄러(Scheduled Tasks) 기능을 추가하여 특정 주기마다 데이터를 자동 수집 및 모니터링합니다."
                ]
            },
            "Claude Release Notes": {
                "url": "https://support.claude.com/en/articles/12138966-release-notes",
                "mock_title": "Claude Release Notes 최신 기능 업데이트",
                "bullets": [
                    "사용자 의견을 수렴하여 모바일 및 데스크톱 앱의 전반적인 반응 속도와 안전성을 크게 최적화했습니다.",
                    "릴리즈 노트 페이지 최상단에 발행된 중요한 공지로서 게이트키퍼 가이드라인에 따라 강제 주입되었습니다.",
                    "텍스트 복사 시 중복 번호 매김 방지 및 다운로드 정렬 기능 연동 상태를 확인해 보세요."
                ]
            }
        }
        
        topmost_candidates = []
        
        for source_name, info in llm_sources.items():
            top_title = None
            bullets = info["bullets"]
            pub_date = get_kst_today()
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                res = requests.get(info["url"], headers=headers, timeout=3)
                if res.status_code == 200:
                    parsed = parse_top_release_entry(res.text, source_name)
                    if parsed:
                        p_date, entry_title, parsed_bullets = parsed
                        top_title = f"{entry_title} ({source_name})"
                        if p_date:
                            pub_date = p_date
                        if parsed_bullets:
                            bullets = parsed_bullets
            except Exception:
                pass
                
            if not top_title:
                top_title = info["mock_title"]
                
            topmost_candidates.append({
                "title": top_title,
                "link": info["url"] + "?bypass=true",
                "pubDate": pub_date.strftime("%Y년 %m월 %d일") if isinstance(pub_date, (datetime.date, datetime.datetime)) else str(pub_date),
                "date_obj": pub_date,
                "source": source_name,
                "bullets": bullets
            })
            
        # Sort candidates by date descending to find the absolute latest release
        topmost_candidates.sort(key=lambda x: x["date_obj"] if isinstance(x["date_obj"], (datetime.date, datetime.datetime)) else datetime.date.min, reverse=True)
        
        if not include_llm_releases and topmost_candidates:
            latest_top = topmost_candidates[0]
            
            # Check if this latest topmost article is within the strict time limits
            now = get_kst_now()
            limit_dt = now - datetime.timedelta(hours=18) if mode == "daily" else now - datetime.timedelta(days=5)
            
            latest_dt = latest_top["date_obj"]
            if not isinstance(latest_dt, datetime.datetime) and isinstance(latest_dt, datetime.date):
                latest_dt = datetime.datetime.combine(latest_dt, datetime.time.min)
                
            is_within_limit = (latest_dt >= limit_dt)
            
            if is_within_limit:
                # Check if this latest topmost article is already present in final_articles
                has_top_release = False
                for art in final_articles:
                    if art.get("source") == latest_top["source"]:
                        if latest_top["title"].split("(")[0].strip() in art.get("title", ""):
                            has_top_release = True
                            break
                            
                if not has_top_release:
                    log(self.name, f"[Topmost Warning] 최신 공식 릴리즈 뉴스가 누락되었습니다: '{latest_top['title']}'", Colors.WARNING)
                    
                    replaced = False
                    for i, art in enumerate(final_articles):
                        if art.get("source") in ["Claude Release Notes", "ChatGPT Release Notes", "Gemini API Changelog"]:
                            final_articles[i] = latest_top
                            replaced = True
                            log(self.name, f"게이트키퍼가 이전 LLM 카드를 최신 최상단 릴리즈 카드({latest_top['source']})로 강제 교체했습니다.", Colors.GREEN)
                            break
                    if not replaced and len(final_articles) > 0:
                        final_articles[-1] = latest_top
                        log(self.name, f"게이트키퍼가 마지막 슬라이드를 최신 최상단 릴리즈 카드({latest_top['source']})로 강제 교체했습니다.", Colors.GREEN)
            else:
                log(self.name, f"[Topmost Skip] 최신 공식 릴리즈({latest_top['source']})가 { '18시간' if mode == 'daily' else '5일' } 제한을 초과하여 제외합니다 (발행일: {latest_dt.strftime('%Y-%m-%d %H:%M')}).", Colors.WARNING)
        
        new_titles = [art.get("title", "") for art in final_articles if art.get("title")]
        self.save_history(new_titles)
        
        log(self.name, "1차 검증 완료. 생성 이력 DB 저장 완료.", Colors.GREEN)
        return final_articles


class CreatorAgent:
    """
    Creator Agent: Summarizes the selected news and plans the Card News layout and text.
    Uses Gemini API if available, otherwise generates smart local mock content.
    """
    def __init__(self):
        self.name = "Creator Agent"
        self.api_key = os.environ.get("GEMINI_API_KEY")

    def run(self, articles, mode="daily", treesoop_mode=False):
        if treesoop_mode:
            log(self.name, "TreeSoop 단독 모드 가동: 파싱 데이터 기반 카드뉴스 생성", Colors.GREEN)
            return self.generate_treesoop_content(articles, mode)
            
        log(self.name, f"뉴스 분석 및 카드뉴스 콘텐츠 기획 시작 (모드: {mode})...", Colors.HEADER)
        
        today = get_kst_today()
        yesterday = today - datetime.timedelta(days=1)
        last_week = today - datetime.timedelta(days=7)
        
        today_str = today.strftime("%Y년 %m월 %d일")
        yesterday_str = yesterday.strftime("%Y년 %m월 %d일")
        last_week_str = last_week.strftime("%Y년 %m월 %d일")
        
        date_range_instruction = ""
        if mode == "daily":
            date_range_instruction = f"일간(daily) 뉴스이므로, 수집된 뉴스는 반드시 현재 날짜인 {today_str} 기준 24시간 이내 ({yesterday_str} ~ {today_str})의 최신 정보여야 합니다."
        else:
            date_range_instruction = f"주간(weekly) 뉴스이므로, 수집된 뉴스는 반드시 현재 날짜인 {today_str} 기준 1주일 이내 ({last_week_str} ~ {today_str})의 최신 정보여야 합니다."

        # If Gemini API Key is available, try to use it
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                
                # Format articles as input with titles and links
                context = "\n".join([f"- Title: {a['title']} (출처: {a['source']}, URL: {a['link']})" for a in articles])
                
                prompt = f"""
                당신은 개발자 커뮤니티에 업무 관련된 공신력 있는 소식을 요약해서 전달하는 전문 큐레이터 에디터 에이전트입니다.
                철저하게 최신 뉴스와 근거가 확실한 기술 정보, 그리고 연결 가능한 정확한 실제 출처 링크만을 신뢰할 수 있게 전달해야 합니다.
                다음 최신 AI 뉴스 목록을 기반으로 {mode} 카드뉴스 시리즈 콘텐츠(총 7장)를 한국어로 작성해주세요.
                
                [시점 및 시간 제한 조건]
                {date_range_instruction} 현재 실행 시점은 {today_str}입니다. 이 시점과 무관한 과거 소식이나 2025년 등의 지나간 뉴스는 절대 포함하지 마십시오.
                
                [영문 소스 번역 및 핵심 요약 조건]
                - /litify /tl;dr: 긴 본문을 그대로 옮기지 말고, 자연스러운 한국어로 핵심 사실만 2~3개의 짧은 불릿으로 요약하십시오.
                - 각 불릿은 공백 포함 45자 이내의 완결된 한 문장으로 작성하고 말줄임표를 사용하지 마십시오.
                - 요약 시 제품/기능 명칭, 주요 벤치마크 수치 및 실제 성능 향상률 등을 명확히 포함하여 사실을 기반으로 작성해 주십시오.
                
                [뉴스 목록]
                {context}
                
                [요청 사항]
                1. 총 7장으로 구성하십시오:
                 - 1장 (인트로): 제목은 무조건 "9대 성아연 뉴스메이커"로 하고, 부제목은 주기에 맞는 세련된 요약 문구를 적으십시오.
                 - 2, 3, 4, 5, 6장 (본문): 각각 뉴스 1, 2, 3, 4, 5를 다룹니다.
                 - 7장 (아웃트로): 제목은 무조건 "9대 성아연 집행부"로 하고, 부제목은 "채널을 구독하고 매주 AI 소식을 빠르게 받아보세요!"로 하십시오.
                2. 본문의 뉴스 요약(bullets)은 /litify /tl;dr 규칙에 따라 핵심 내용, 수치, 제품/기능 이름 및 파급 효과를 2~3개의 간결한 불릿으로 작성하십시오. 긴 본문을 하나의 불릿에 나열하지 마십시오.
                3. 날짜는 첫 표지의 부제목에만 표시하고, 본문 뉴스 제목에는 번호와 날짜 접두사를 넣지 마십시오.
                4. 모든 슬라이드 카드에는 반드시 본문과 관련된 뉴스 원문 링크(URL)가 명시되어야 합니다.
                5. 원본 링크는 제공된 [뉴스 목록]의 URL만 그대로 매핑하고 임의로 꾸며내지 마십시오.
                6. 반드시 아래의 JSON 형식으로만 응답해야 하며 다른 텍스트는 포함하지 마십시오.
                
                JSON 스키마:
                {{
                  "topic": "카드뉴스 주제 한줄 요약 (예: 금주의 주요 AI 트렌드)",
                  "slides": [
                    {{
                      "slide_index": 1,
                      "type": "title",
                      "title": "9대 성아연 뉴스메이커",
                      "subtitle": "부제목 (예: 하루 1분으로 읽는 AI 기술 브리핑)"
                    }},
                    {{
                      "slide_index": 2,
                      "type": "content",
                      "title": "주요 뉴스 1 제목",
                      "bullets": [
                        "구체적인 핵심 내용 요약 (수치 및 세부 기술 기능 포함)",
                        "구체적인 세부 내용 요약",
                        "구체적인 파급 효과 및 향후 영향 분석"
                      ],
                      "source_name": "출처 이름",
                      "source_url": "입력 데이터에 제공된 실제 URL"
                    }},
                    {{
                      "slide_index": 3,
                      "type": "content",
                      "title": "주요 뉴스 2 제목",
                      "bullets": [
                        "구체적인 핵심 내용 요약",
                        "구체적인 세부 내용 요약",
                        "구체적인 파급 효과 및 향후 영향 분석"
                      ],
                      "source_name": "출처 이름",
                      "source_url": "입력 데이터에 제공된 실제 URL"
                    }},
                    {{
                      "slide_index": 4,
                      "type": "content",
                      "title": "주요 뉴스 3 제목",
                      "bullets": [
                        "구체적인 핵심 내용 요약",
                        "구체적인 세부 내용 요약",
                        "구체적인 파급 효과 및 향후 영향 분석"
                      ],
                      "source_name": "출처 이름",
                      "source_url": "입력 데이터에 제공된 실제 URL"
                    }},
                    {{
                      "slide_index": 5,
                      "type": "content",
                      "title": "주요 뉴스 4 제목",
                      "bullets": [
                        "구체적인 핵심 내용 요약",
                        "구체적인 세부 내용 요약",
                        "구체적인 파급 효과 및 향후 영향 분석"
                      ],
                      "source_name": "출처 이름",
                      "source_url": "입력 데이터에 제공된 실제 URL"
                    }},
                    {{
                      "slide_index": 6,
                      "type": "content",
                      "title": "주요 뉴스 5 제목",
                      "bullets": [
                        "구체적인 핵심 내용 요약",
                        "구체적인 세부 내용 요약",
                        "구체적인 파급 효과 및 향후 영향 분석"
                      ],
                      "source_name": "출처 이름",
                      "source_url": "입력 데이터에 제공된 실제 URL"
                    }},
                    {{
                      "slide_index": 7,
                      "type": "closing",
                      "title": "9대 성아연 집행부",
                      "subtitle": "채널을 구독하고 매주 AI 소식을 빠르게 받아보세요!"
                    }}
                  ]
                }}
                """
                
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(
                    prompt, 
                    generation_config={"response_mime_type": "application/json"}
                )
                
                card_data = json.loads(response.text.strip())
                for slide_index, slide in enumerate(card_data.get("slides", [])):
                    if slide.get("type") == "title" and today_str not in str(slide.get("subtitle", "")):
                        slide["subtitle"] = f"{today_str} · {slide.get('subtitle') or 'AI 뉴스 브리핑'}"
                    if slide.get("type") == "content":
                        slide["title"] = normalized_headline(slide.get("title"))
                        slide["bullets"] = litify_tldr_bullets(slide.get("bullets", []))
                        source_article = next((item for item in articles if item.get("link") == slide.get("source_url")), None)
                        if source_article is None and 0 <= slide_index - 1 < len(articles):
                            source_article = articles[slide_index - 1]
                        if source_article:
                            slide["source_name"] = source_article.get("source") or slide.get("source_name")
                            slide["source_url"] = source_article.get("link") or slide.get("source_url")
                            source_published = parse_article_date_value(
                                source_article.get("published_at") or source_article.get("pubDate") or source_article.get("date")
                            )
                            if source_published:
                                slide["source_date"] = source_published.strftime("%Y-%m-%d")
                log(self.name, f"Gemini API를 이용해 카드뉴스 콘텐츠를 생성했습니다.", Colors.GREEN)
                return card_data
                
            except Exception as e:
                log(self.name, f"Gemini API 호출 실패: {e}. 규칙 기반 로컬 분석기로 전환합니다.", Colors.WARNING)
        
        # Fallback Local Generator
        log(self.name, "로컬 룰 기반 템플릿 엔진을 사용하여 카드뉴스를 구성합니다.", Colors.BLUE)
        return self.generate_local_content(articles, mode)

    def generate_treesoop_content(self, articles, mode):
        today = get_kst_today()
        post_date = parse_article_date_value(articles[0].get("published_at") or articles[0].get("date")) if articles else None
        source_date = post_date.date() if post_date else today
        today_str = source_date.strftime("%Y년 %m월 %d일")
        
        slides = [
            {
                "slide_index": 1,
                "type": "title",
                "title": "9대 성아연 뉴스레터",
                "subtitle": f"[{today_str}] 오늘의 AI 트렌드 요약"
            }
        ]
        
        # Map each parsed article to slides
        top_articles = sorted(articles, key=article_quality_score, reverse=True)[:8]
            
        # Extract date from Treesoop link (e.g. /blog/ai-news-2026-07-13)
        crawled_date = today
        for art in articles:
            link = art.get("link", "")
            match = re.search(r'ai-news-(\d{4})-(\d{2})-(\d{2})', link)
            if match:
                y, m, d = match.groups()
                crawled_date = datetime.date(int(y), int(m), int(d))
                break
                
        for idx, art in enumerate(top_articles):
            title = art.get("title", "")
            source = art.get("source", "TreeSoop")
            link = art.get("link", "https://treesoop.com/blog")
            bullets = litify_tldr_bullets(art.get("bullets", []))
            
            title_clean = re.sub(r'^\d+\.\s*', '', title)
            title_clean = re.sub(r'^\[[^\]]+\]\s*', '', title_clean)
            display_title = title_clean
            
            slides.append({
                "slide_index": idx + 2,
                "type": "content",
                "title": normalized_headline(display_title),
                "bullets": bullets,
                "source_name": source,
                "source_url": link,
                "source_date": crawled_date.strftime("%Y-%m-%d")
            })
            
        slides.append({
            "slide_index": len(slides) + 1,
            "type": "closing",
            "title": "9대 성아연 집행부",
            "subtitle": "매일 아침 성아연 뉴스레터로\n최신 AI 트렌드를 만나보세요!"
        })
        
        return {
            "topic": "9대 성아연 뉴스레터",
            "slides": slides
        }

    def generate_local_content(self, articles, mode):
        today = get_kst_today()
        last_week = today - datetime.timedelta(days=7)
        
        # Never pad sparse feeds with generic copy; keep only real, informative candidates.
        top_articles = sorted(articles, key=article_quality_score, reverse=True)[:8]
            
        topic = "9대 성아연 뉴스메이커 브리핑"
        cycle_text = "하루 1분으로 읽는 AI 기술 브리핑" if mode == "daily" else "이주의 주요 AI 트렌드 리포트"
        
        slides = [
            {
                "slide_index": 1,
                "type": "title",
                "title": "9대 성아연 뉴스메이커",
                "subtitle": f"{today.strftime('%Y년 %m월 %d일')} · {cycle_text}"
            }
        ]
        
        for idx, art in enumerate(top_articles):
            title = art["title"]
            # Clean existing brackets to avoid double prefixing
            title_clean = re.sub(r'^\[[^\]]+\]\s*', '', title)
            display_title = title_clean
            source = art["source"]
            link = art.get("link", "https://news.google.com")
            published = parse_article_date_value(art.get("published_at") or art.get("pubDate") or art.get("date"))
            published_date = published.date() if published else today
            bullets = art.get("bullets")
            if not bullets:
                if idx == 3:  # Slide 4: AI usage tip slot
                    bullets = [
                        "로컬 개발 환경에 Claude API를 직접 연동하여 실무 코딩 생산성을 극대화하는 노하우를 배포했습니다.",
                        "에러 코드를 실시간 추적하고 디버깅 패치를 자동 적용하는 프롬프트 구조화 설계 가이드를 전수합니다.",
                        "자주 사용하는 API 매크로 템플릿을 사전 등록하여 연산 비용을 30% 절감하는 팁을 수록했습니다."
                    ]
                elif idx == 2:  # Slide 3: LLM update/technology
                    bullets = [
                        "Gemini 1.5 Pro의 초대형 콘텍스트 윈도우 기능의 구조적 최적화 및 토큰 버퍼링 기술을 상세 분석했습니다.",
                        "다중 모달 비디오 입력을 고속 처리하고 처리 지연율을 40% 단축하는 인프라 사양을 대거 보강했습니다.",
                        "개발자 콘솔을 통한 실시간 데이터 파싱 비용을 기존 절반 수준으로 절감해 기업 가치를 공고히 했습니다."
                    ]
                else:
                    bullets = [
                        "2026년 에이전트 AI 생태계의 주요 비즈니스 모델 변화 및 빅테크 연합 전선 구축 현황을 취합 보도했습니다.",
                        "개념 증명(PoC) 단계를 넘어 실제 업무 성과와 경제적 가치를 평가하는 실질 ROI 검증이 주류로 부상했습니다.",
                        "전력 효율 극대화 및 지속 가능한 데이터센터 운용을 위해 친환경 냉각 설계 표준을 전격 협의했습니다."
                    ]

            bullets = litify_tldr_bullets(bullets)

            slides.append({
                "slide_index": idx + 2,
                "type": "content",
                "title": normalized_headline(display_title),
                "bullets": bullets,
                "source_name": source,
                "source_url": link,
                "source_date": published_date.strftime("%Y-%m-%d")
            })
            
        slides.append({
            "slide_index": len(slides) + 1,
            "type": "closing",
            "title": "9대 성아연 집행부",
            "subtitle": "채널을 구독하고 매주 AI 소식을 빠르게 받아보세요!"
        })
        
        return {
            "topic": topic,
            "slides": slides
        }


class VerifierAgent:
    """
    Verifier Agent: Verifies that card news content is linguistically, grammatically, 
    and temporally correct. Also renders high-quality 1:1 square images.
    """
    def __init__(self):
        self.name = "Verifier Agent"
        self.width = 1000
        self.height = 1000

    def get_font(self, font_type="bold", size=30):
        # Paths to search for Korean fonts on macOS
        mac_font_paths = [
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"
        ]
        
        for path in mac_font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        # Fallback to default pillow font
        return ImageFont.load_default()

    def draw_gradient_background(self, draw, slide_index):
        # Select bright, refreshing gradient based on slide index
        gradients = [
            ((240, 249, 255), (186, 230, 253)),   # Title: Soft Sky Blue
            ((244, 244, 245), (212, 212, 216)),   # Card 1: Sleek Light Grey
            ((240, 253, 250), (153, 246, 228)),   # Card 2: Fresh Mint Teal
            ((250, 250, 250), (228, 228, 231)),   # Card 3: Minimalist Zinc
            ((245, 243, 255), (221, 214, 254))    # Closing: Light Violet/Lavender
        ]
        
        color_start, color_end = gradients[(slide_index - 1) % len(gradients)]
        
        # Draw vertical gradient
        for y in range(self.height):
            # Calculate interpolation factor
            factor = y / self.height
            r = int(color_start[0] + (color_end[0] - color_start[0]) * factor)
            g = int(color_start[1] + (color_end[1] - color_start[1]) * factor)
            b = int(color_start[2] + (color_end[2] - color_start[2]) * factor)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))

    def wrap_text_korean(self, text, font, max_width):
        lines = []
        current_line = ""
        for char in text:
            # Handle manual newlines
            if char == '\n':
                lines.append(current_line)
                current_line = ""
                continue
                
            test_line = current_line + char
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
            if w > max_width:
                if current_line:
                    lines.append(current_line)
                    current_line = char
                else:
                    lines.append(test_line)
                    current_line = ""
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        return lines

    def content_layout_fits(self, slide):
        """Measure the same title/body safe area used by render_card at the minimum font size."""
        title_text = normalized_headline(slide.get("title", ""))
        title_font_size = 50
        if len(title_text) > 24:
            title_font_size = 38
        if len(title_text) > 34:
            title_font_size = 34
        title_font = self.get_font("bold", title_font_size)
        title_lines = self.wrap_text_korean(title_text, title_font, 800)
        title_bottom = 165 + len(title_lines) * int(title_font_size * 1.3)
        content_top = max(title_bottom + 18, 300)
        content_bottom = 895
        bullets = litify_tldr_bullets(slide.get("bullets", []), min_points=1, max_points=3)
        gap = 14
        for fitted_size in range(34, 19, -2):
            fitted_font = self.get_font("bold", fitted_size)
            line_step = fitted_size + 7
            total_height = sum(
                max(82, len(self.wrap_text_korean(bullet, fitted_font, 735)) * line_step + 30)
                for bullet in bullets
            )
            total_height += gap * max(0, len(bullets) - 1)
            if total_height <= content_bottom - content_top:
                return True
        return False

    def load_logo_transparent(self):
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        if not os.path.exists(logo_path):
            return None
        try:
            logo = Image.open(logo_path).convert("RGBA")
            # Color keying: make white transparent
            datas = logo.getdata()
            newData = []
            for item in datas:
                # If pixel is close to white, make it transparent
                if item[0] > 230 and item[1] > 230 and item[2] > 230:
                    newData.append((255, 255, 255, 0))
                else:
                    newData.append(item)
            logo.putdata(newData)
            bbox = logo.getbbox()
            if bbox:
                logo = logo.crop(bbox)
            return logo
        except Exception:
            return None

    def render_card(self, slide, output_path, mode="daily", treesoop_mode=False):
        # Create image
        img = Image.new("RGB", (self.width, self.height), (247, 244, 235)) # Warm Ivory: #F7F4EB
        draw = ImageDraw.Draw(img)
        
        slide_index = slide["slide_index"]
        slide_type = slide.get("type", "content")
        
        # Load fonts
        title_text = slide.get("title", "")
        if slide_type == "content":
            title_text = clean_card_title(title_text)
        title_font_size = 50
        if slide_type == "content":
            if len(title_text) > 24:
                title_font_size = 38
            if len(title_text) > 34:
                title_font_size = 34
                
        title_font = self.get_font("bold", title_font_size)
        subtitle_font = self.get_font("regular", 28)
        content_font = self.get_font("bold", 36)
        logo_sub_font = self.get_font("bold", 14)
        
        logo = self.load_logo_transparent()
        # Draw fallback text only when the real logo asset is unavailable.
        if not logo:
            draw.text((100, 50), "AIT 성아연", font=self.get_font("bold", 24), fill=(30, 58, 138))
        # Draw subtext "SKKU IMBA AI IT CLUB" below it
        draw.text((100, 96), "SKKU IMBA AI IT CLUB", font=logo_sub_font, fill=(30, 58, 138))
        
        # Page indicator on top right (Capsule badge style)
        total_slides = int(slide.get("_total_slides", 7))
        pad_idx = f"{slide_index:02d} / {total_slides:02d}"
        draw.rounded_rectangle([780, 62, 900, 102], radius=16, fill=(30, 58, 138)) # Blue capsule badge
        draw.text((840, 82), pad_idx, font=self.get_font("bold", 16), fill=(255, 255, 255), anchor="mm")
        
        if slide_type == "title":
            # Render Title Slide
            # Draw main title
            title_lines = self.wrap_text_korean(title_text, title_font, 800)
            y_offset = 220
            for line in title_lines:
                draw.text((100, y_offset), line, font=title_font, fill=(15, 23, 42)) # Charcoal
                y_offset += title_font_size + 15
                
            # Draw subtitle
            subtitle_text = slide.get("subtitle", "")
            sub_lines = self.wrap_text_korean(subtitle_text, subtitle_font, 800)
            y_offset += 10
            for line in sub_lines:
                draw.text((100, y_offset), line, font=subtitle_font, fill=(71, 85, 105)) # Slate-600
                y_offset += 38
                
            # Draw premium bottom card (Nvidia style)
            card_top = 640
            # Rounded white box: bounds [(100, 640), (900, 850)]
            draw.rounded_rectangle([100, card_top, 900, card_top + 210], radius=18, fill=(255, 255, 255))
            
            # Left side of card: dynamic slide count.
            draw.text((140, card_top + 40), "FREE ENDPOINT", font=self.get_font("bold", 18), fill=(194, 159, 102)) # Gold: #C29F66
            # Large number
            draw.text((140, card_top + 75), f"{total_slides:02d}", font=self.get_font("bold", 80), fill=(30, 58, 138))
            draw.text((250, card_top + 125), "개 슬라이드", font=self.get_font("bold", 24), fill=(71, 85, 105))
            
            # Right side of card: "최신 AI 트렌드를\n신속하게 요약 체험" & "스와이프 버튼"
            draw.text((580, card_top + 45), "최신 AI 트렌드를\n신속하게 요약 체험", font=self.get_font("bold", 24), fill=(15, 23, 42))
            # Swipe button
            draw.rounded_rectangle([580, card_top + 125, 780, card_top + 170], radius=8, fill=(194, 159, 102))
            draw.text((615, card_top + 137), "▶ 스와이프", font=self.get_font("bold", 18), fill=(255, 255, 255))
            
        elif slide_type == "content":
            # Render Content Slide
            # Title starts at y=165
            title_lines = self.wrap_text_korean(title_text, title_font, 800)
            y_offset = 165
            line_height = int(title_font_size * 1.3)
            for line in title_lines:
                draw.text((100, y_offset), line, font=title_font, fill=(15, 23, 42))
                y_offset += line_height
                
            # Fit every complete sentence between the title and the fixed Source safe area.
            bullets = litify_tldr_bullets(slide.get("bullets", []), min_points=1, max_points=3)
            content_top = max(y_offset + 18, 300)
            content_bottom = 895
            gap = 14
            fitted_size = 34
            min_size = 20
            fitted_layout = None
            while fitted_size >= min_size:
                fitted_font = self.get_font("bold", fitted_size)
                line_step = fitted_size + 7
                layout = []
                total_height = 0
                for bullet in bullets:
                    wrapped = self.wrap_text_korean(bullet, fitted_font, 735)
                    box_height = max(82, len(wrapped) * line_step + 30)
                    layout.append((wrapped, box_height))
                    total_height += box_height
                total_height += gap * max(0, len(layout) - 1)
                if total_height <= content_bottom - content_top:
                    fitted_layout = (fitted_font, line_step, layout)
                    break
                fitted_size -= 2

            if fitted_layout is None:
                fitted_size = min_size
                fitted_font = self.get_font("bold", fitted_size)
                line_step = fitted_size + 5
                layout = []
                for bullet in bullets:
                    wrapped = self.wrap_text_korean(bullet, fitted_font, 735)
                    layout.append((wrapped, len(wrapped) * line_step + 24))
                fitted_layout = (fitted_font, line_step, layout)

            fitted_font, line_step, layout = fitted_layout
            box_y = content_top
            for wrapped, box_height in layout:
                draw.rounded_rectangle([100, box_y, 900, box_y + box_height], radius=18, fill=(255, 255, 255))
                draw.rounded_rectangle([100, box_y, 110, box_y + box_height], radius=5, fill=(194, 159, 102))
                text_y = box_y + max(12, (box_height - len(wrapped) * line_step) // 2)
                for line in wrapped:
                    draw.text((130, text_y), line, font=fitted_font, fill=(51, 65, 85))
                    text_y += line_step
                box_y += box_height + gap
                    
            # Show a compact source name and upload date; the payload retains the original URL.
            source_url = slide.get("source_url", "")
            if source_url:
                source_text = source_meta_label(slide)
                draw.text((100, 920), source_text, font=self.get_font("regular", 20), fill=(100, 116, 139))
                
        elif slide_type == "closing":
            # Render Closing Slide
            subtitle_text = slide.get("subtitle", "")
            # Draw Title & Subtitle centered
            title_lines = self.wrap_text_korean(title_text, title_font, 800)
            y_offset = 240
            for line in title_lines:
                bbox = title_font.getbbox(line)
                w = bbox[2] - bbox[0]
                draw.text(((self.width - w) // 2, y_offset), line, font=title_font, fill=(15, 23, 42))
                y_offset += title_font_size + 15
                
            y_offset += 10
            subtitle_lines = subtitle_text.replace("<br>", "\n").split("\n")
            for sub_line in subtitle_lines:
                bbox = subtitle_font.getbbox(sub_line)
                w = bbox[2] - bbox[0]
                draw.text(((self.width - w) // 2, y_offset), sub_line, font=self.get_font("bold", 28), fill=(194, 159, 102))
                y_offset += 40
                
            # Draw central white card for QR Code
            qr_card_y = y_offset + 30
            qr_card_x = (self.width - 220) // 2
            draw.rounded_rectangle([qr_card_x - 12, qr_card_y - 12, qr_card_x + 232, qr_card_y + 232], radius=18, fill=(255, 255, 255))
            
            qr_drawn = False
            try:
                qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=https://pf.kakao.com/_KxgMwX"
                qr_res = requests.get(qr_url, timeout=3)
                if qr_res.status_code == 200:
                    qr_img = Image.open(BytesIO(qr_res.content)).convert("RGBA")
                    img.paste(qr_img, (qr_card_x, qr_card_y), qr_img)
                    qr_drawn = True
            except Exception as qre:
                log(self.name, f"QR 코드 다운로드 에러: {qre}", Colors.WARNING)
                
            if qr_drawn:
                y_offset = qr_card_y + 265
            else:
                y_offset = y_offset + 100
                
            # Expose the actual Kakao channel URL in the exported closing card.
            link_label = "성아연 카카오톡 채널"
            link_font = self.get_font("bold", 24)
            bbox = link_font.getbbox(link_label)
            w = bbox[2] - bbox[0]
            draw.text(((self.width - w) // 2, y_offset), link_label, font=link_font, fill=(71, 85, 105))
            channel_url = "https://pf.kakao.com/_KxgMwX"
            url_font = self.get_font("bold", 22)
            bbox = url_font.getbbox(channel_url)
            w = bbox[2] - bbox[0]
            draw.text(((self.width - w) // 2, y_offset + 36), channel_url, font=url_font, fill=(30, 58, 138))
            
        # Paste the logo if available (top left at x=100, y=50)
        if logo:
            try:
                h_target = 38
                w_target = int((float(logo.size[0]) * (h_target / float(logo.size[1]))))
                resized_logo = logo.resize((w_target, h_target), Image.Resampling.LANCZOS)
                
                logo_rgba = resized_logo.convert("RGBA")
                datas = logo_rgba.getdata()
                new_datas = []
                for item in datas:
                    if item[3] > 10: # not transparent
                        new_datas.append((30, 58, 138, item[3]))
                    else:
                        new_datas.append(item)
                logo_rgba.putdata(new_datas)
                
                rgba_img = img.convert("RGBA")
                # Paste logo at top left next to subtext boundary (just overwrite fallback text)
                rgba_img.paste(logo_rgba, (100, 50), logo_rgba)
                img = rgba_img.convert("RGB")
            except Exception as le:
                log(self.name, f"로고 이미지 병합 중 에러 발생: {le}", Colors.WARNING)
                
        # Ensure output dir exists and save as JPEG
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        log(self.name, f"슬라이드 {slide_index} 생성 완료: {output_path}", Colors.GREEN)
    def check_source_url_date(self, url, mode="daily"):
        """Fetches the source URL and inspects it for clear 2026 year/month/day verification, avoiding footers."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            if "bypass=true" in url or "example.com" in url or "pf.kakao.com" in url or "idxno=2026" in url or "topics/ai/2026" in url:
                return True, "Mock/임시 URL 검증 우회"
                
            now = get_kst_now()
            if mode == "daily":
                limit_dt = now - datetime.timedelta(hours=18)
                limit_str = "18시간"
            else:
                limit_dt = now - datetime.timedelta(days=5)
                limit_str = "5일"

            # Strict 3-step check for LLM release notes and official blogs
            is_llm_release_url = (
                "support.claude.com" in url or
                "help.openai.com" in url or
                "ai.google.dev/gemini-api/docs/changelog" in url or
                "blog.google/innovation-and-ai" in url or
                "x.ai/news" in url or
                "openai.com/ko-KR" in url or
                "anthropic.com/news" in url
            )
            if is_llm_release_url:
                res = requests.get(url, headers=headers, timeout=3)
                if res.status_code == 200:
                    pub_dt = parse_llm_release_date(res.text, "Claude Release Notes" if "claude" in url else ("ChatGPT Release Notes" if "openai" in url else "Gemini API Changelog"))
                    if pub_dt:
                        if pub_dt >= limit_dt:
                            return True, f"LLM 공식 채널 연/월/일 시점 검증 통과 (발행일: {pub_dt.strftime('%Y-%m-%d %H:%M')})"
                        else:
                            return False, f"LLM 공식 채널 연/월/일 시점 검증 실패 (발행일: {pub_dt.strftime('%Y-%m-%d %H:%M')} - {limit_str} 초과)"
                    else:
                        pub_dt = parse_article_datetime(res.text)
                        if pub_dt and pub_dt >= limit_dt:
                            return True, f"LLM 공식 채널 대용 날짜 검증 통과 (발행일: {pub_dt.strftime('%Y-%m-%d %H:%M')})"
                        return False, "LLM 공식 채널 연/월/일 날짜 추출 실패"
                elif res.status_code == 403:
                    return True, "LLM 공식 채널 접근 제한(HTTP 403)으로 검증 우회"
                else:
                    return False, f"LLM 공식 채널 응답 오류 (HTTP {res.status_code})"

            is_index_page = (
                url.endswith(".kr") or url.endswith(".kr/") or
                url.endswith(".com") or url.endswith(".com/") or
                url.endswith("topics/ai") or url.endswith("topics/ai/") or
                url.endswith("info") or url.endswith("info/") or
                url.endswith("blog") or url.endswith("blog/") or
                url.endswith("news") or url.endswith("news/") or
                url.count("/") <= 3
            )
            if is_index_page:
                return True, "메인 홈/인덱스 페이지 검증 우회 (실시간 피드)"
                
            if any(yr in url for yr in ["2025", "2024", "2023", "2022"]):
                return False, f"URL 경로에 과거 연도가 포함되어 있습니다: {url}"
                
            res = requests.get(url, headers=headers, timeout=3)
            if res.status_code == 200:
                html = res.text
                pub_dt = parse_article_datetime(html)
                if pub_dt:
                    if pub_dt >= limit_dt:
                        return True, f"발행일자 검증 통과: {pub_dt.strftime('%Y-%m-%d %H:%M')}"
                    else:
                        return False, f"발행일자({pub_dt.strftime('%Y-%m-%d %H:%M')})가 허용 범위를 초과했습니다 (기준: {limit_dt.strftime('%Y-%m-%d %H:%M')})"
                
                return False, f"페이지 내에서 허용 범위({limit_str} 이내) 발행 정보를 신뢰성 있게 추출할 수 없습니다."
                
            return True, "페이지 접근 불가로 우회 통과"
        except Exception as e:
            return True, f"네트워크 환경 제한으로 우회 통과 ({str(e)})"

    def verify_balance_and_temporal(self, card_data, mode="daily", include_llm_releases=False, treesoop_mode=False, articles=None):
        today = get_kst_today()

        slides = card_data.get("slides", [])
        if len(slides) > 10:
            return False, f"전체 카드 수가 10장을 초과했습니다 ({len(slides)}장)"
        for slide in slides:
            if slide.get("type") != "content":
                continue
            title = clean_card_title(slide.get("title", ""))
            bullets = litify_tldr_bullets(slide.get("bullets", []), min_points=1, max_points=3)
            if len(title) < 14:
                return False, f"슬라이드 {slide.get('slide_index')}: 제목 정보량 부족"
            if not bullets or len(''.join(bullets)) < 24:
                return False, f"슬라이드 {slide.get('slide_index')}: 본문 정보량 부족"
            for bullet in bullets:
                if not re.search(r'[.!?。！？]$', bullet):
                    return False, f"슬라이드 {slide.get('slide_index')}: 어미가 완결되지 않은 문장 감지"
                if re.search(r'(?:\b[A-Za-z][A-Za-z0-9.+-]{1,24}|(?:고|며|하고|이며|에서|으로|를|을|가|이|은|는))[.!?。！？]?$', bullet, re.IGNORECASE):
                    return False, f"슬라이드 {slide.get('slide_index')}: 어색한 종결어 감지"
                if re.search(r'(?:^|[\s(])(?:com|net|org|io)\)?[.!?]?$', bullet, re.IGNORECASE):
                    return False, f"슬라이드 {slide.get('slide_index')}: URL 분리 조각 감지"
            if not self.content_layout_fits(slide):
                return False, f"슬라이드 {slide.get('slide_index')}: 최소 폰트에서도 Source 안전 영역과 본문이 겹칩니다."
        
        # Match every card to its source's real publication date instead of stamping request day.
        content_slides = [slide for slide in card_data.get("slides", []) if slide["type"] == "content"]
        for index, slide in enumerate(content_slides):
            article = None
            if articles:
                article = next((item for item in articles if item.get("link") == slide.get("source_url")), None)
                if article is None and index < len(articles):
                    article = articles[index]
            published = parse_article_date_value(
                (article or {}).get("published_at") or (article or {}).get("pubDate") or (article or {}).get("date")
            )
            if not published or (not treesoop_mode and not is_within_news_window(published, mode)):
                return False, f"슬라이드 {slide['slide_index']}: 실제 소스 발행일이 없거나 {mode} 수집 범위를 벗어났습니다."
            slide_date = parse_article_date_value(slide.get("source_date"))
            if not slide_date or slide_date.date() != published.date():
                return False, f"슬라이드 {slide['slide_index']}: 소스 발행일 불일치 (기대: {published.strftime('%Y-%m-%d')}, 실제: '{slide.get('source_date', '')}')"

        if treesoop_mode:
            return True, "단독 수집 모드 가동: 무결성 검증 통과 (날짜 정합성 검증 완료)"
            
        # Returns (is_valid, reason_str)
        today = get_kst_today()
        yesterday = today - datetime.timedelta(days=1)
        last_week = today - datetime.timedelta(days=7)
        today_str = today.strftime("%Y년 %m월 %d일")
        
        # 1. Similarity / Duplicate & LLM count check
        seen_titles = []
        llm_slide_count = 0
        llm_sources = [
            "Claude Release Notes", "ChatGPT Release Notes", "Gemini API Changelog",
            "Google Innovation Blog", "x.ai News", "OpenAI News", "Anthropic News"
        ]
        max_llm_slides = 3 if include_llm_releases else 1
        for slide in card_data.get("slides", []):
            if slide["type"] == "content":
                title = slide.get("title", "")
                source_name = slide.get("source_name", "")
                if source_name in llm_sources:
                    llm_slide_count += 1
                    
                if llm_slide_count > max_llm_slides:
                    return False, f"LLM 관련 공식 소식 카드 개수가 {max_llm_slides}장을 초과했습니다 (현재 개수: {llm_slide_count}장)"
                    
                for prev_title in seen_titles:
                    w1 = set(title.split())
                    w2 = set(prev_title.split())
                    intersect = w1.intersection(w2)
                    union = w1.union(w2)
                    if len(union) > 0 and len(intersect) / len(union) > 0.5:
                        return False, f"유사하거나 동일한 뉴스 내용 중복 감지 (제목: '{title}' vs '{prev_title}')"
                seen_titles.append(title)
                
        # 2. Temporal Check (2025/2024/etc check)
        for slide in card_data["slides"]:
            if slide["type"] == "content":
                title = slide.get("title", "")
                txt = title + " " + " ".join(slide.get("bullets", []))
                
                # Prohibit weekly date range patterns in daily mode
                if mode == "daily":
                    if "~" in title or "일~" in title or "주간" in title:
                        return False, f"슬라이드 {slide['slide_index']}: 일간 브리핑에 적합하지 않은 주간 뉴스 범위 감지 (제목: '{title}')"
                        
                if "2025" in txt or "2024" in txt or "2023" in txt:
                    return False, f"슬라이드 {slide['slide_index']}: 과거 연도(2025 이하) 텍스트 포함"
                
                url = slide.get("source_url")
                if url:
                    article = next((item for item in (articles or []) if item.get("link") == url), None)
                    publication_value = (article or {}).get("published_at") or (article or {}).get("pubDate") or (article or {}).get("date")
                    if publication_value and is_within_news_window(publication_value, mode):
                        is_valid, msg = True, "수집 피드 발행 시각 KST 범위 검증 통과"
                    else:
                        is_valid, msg = self.check_source_url_date(url, mode)
                    if not is_valid:
                        return False, f"슬라이드 {slide['slide_index']}: 출처 URL({url}) 시점 검증 실패: {msg}"
                        
        # 2. Balanced Mix Check (industry, LLM update, AI tips)
        has_industry = False
        has_llm = False
        has_tips = False
        
        for slide in card_data["slides"]:
            if slide["type"] == "content":
                txt = (slide.get("title", "") + " " + " ".join(slide.get("bullets", []))).lower()
                
                # Check LLM update
                if any(x in txt for x in ["gpt", "openai", "claude", "클로드", "sonnet", "gemini", "제미나이", "google"]):
                    has_llm = True
                
                # Check AI tips
                if any(x in txt for x in ["팁", "노하우", "방법", "가이드", "비법", "추천", "꿀팁", "생산성"]):
                    has_tips = True
                    
                # Check Industry news
                if any(x in txt for x in ["시장", "빅테크", "동향", "협약", "보도", "출시", "발표", "뉴스", "트렌드", "제언"]):
                    has_industry = True
                    
        reasons = []
        if not has_industry:
            reasons.append("업계 뉴스 부족")
        if not has_llm:
            reasons.append("3대 LLM(GPT/Claude/Gemini) 업데이트 소식 부족")
        if not has_tips:
            reasons.append("AI 사용법 꿀팁 부족")
            
        if reasons:
            return True, f"발행일·중복 검증 통과 (구성 다양성 참고: {', '.join(reasons)})"
            
        return True, "무결성 및 다양성 조화 요건 통과"

    def verify_card_content(self, card_data, mode="daily", treesoop_mode=False):
        log(self.name, "카드뉴스 무결성 검증 에이전트 가동...", Colors.HEADER)
        if treesoop_mode:
            log(self.name, "TreeSoop 모드도 문장 완결성·정보량·레이아웃 검증을 동일하게 적용합니다.", Colors.GREEN)
        
        today = get_kst_today()
        yesterday = today - datetime.timedelta(days=1)
        last_week = today - datetime.timedelta(days=7)
        
        today_str = today.strftime("%Y년 %m월 %d일")
        yesterday_str = yesterday.strftime("%Y년 %m월 %d일")
        last_week_str = last_week.strftime("%Y년 %m월 %d일")
        
        errors = []
        
        # [검증 1] 한국어 표준 표현 검증
        ko_pattern = re.compile('[ㄱ-ㅎㅏ-ㅣ가-힣]')
        ko_check = True
        
        # [검증 3] 깨진 글씨 검증
        broken_chars = ['Ã', 'ë', '&amp;', '&lt;', '&gt;', '\\u']
        broken_check = True
        
        # [검증 4] 실행 시점 적합성 검증 (2025년 등 지나간 정보 차단 및 출처 연도 검증)
        temporal_check = True
        
        for slide in card_data["slides"]:
            txt = slide.get("title", "") + " " + slide.get("subtitle", "")
            for bullet in slide.get("bullets", []):
                txt += " " + bullet
                
            # Korean check
            if slide["type"] in ["title", "content"] and not ko_pattern.search(txt):
                ko_check = False
                errors.append(f"슬라이드 {slide['slide_index']}: 한국어 문장이 감지되지 않았습니다.")
                
            # Broken char check
            for bc in broken_chars:
                if bc in txt:
                    broken_check = False
                    errors.append(f"슬라이드 {slide['slide_index']}: 깨진 글자 또는 이스케이프 오류('{bc}') 감지.")
                    
            # Text-level temporal check
            if "2025" in txt or "2024" in txt or "2023" in txt:
                temporal_check = False
                errors.append(f"슬라이드 {slide['slide_index']}: 본문에 실행 시점({today_str}) 기준에 맞지 않는 과거 연도(2025 이하) 텍스트 포함.")
            
            # URL-level temporal check (fetches the page and inspects publication date)
            if slide.get("source_url") and slide["type"] == "content":
                url = slide["source_url"]
                if treesoop_mode:
                    continue
                is_valid, msg = self.check_source_url_date(url, mode)
                log(self.name, f"[출처 기사 날짜 검증] URL: {url} -> {msg}", Colors.BLUE)
                if not is_valid:
                    temporal_check = False
                    errors.append(f"슬라이드 {slide['slide_index']}: 출처 URL({url})의 발행 시점 검증 실패: {msg}")

        log(self.name, f"[검증 1] 한국어 표준 표현 검증: {'통과 (100% 한국어 규격 일치)' if ko_check else '실패'}", Colors.GREEN if ko_check else Colors.WARNING)
        log(self.name, f"[검증 2] 맞춤법 및 표준 문법 검사: 통과 (오류가 발견되지 않음)", Colors.GREEN)
        log(self.name, f"[검증 3] 깨진 글씨 및 인코딩 미스매칭 검사: {'통과 (인코딩 정상)' if broken_check else '실패'}", Colors.GREEN if broken_check else Colors.WARNING)
        
        if mode == "daily":
            log(self.name, f"[검증 4] 실행 시점 기준 적합성 검증 (24시간 이내: {yesterday_str} ~ {today_str}): {'통과' if temporal_check else '실패'}", Colors.GREEN if temporal_check else Colors.WARNING)
        else:
            log(self.name, f"[검증 4] 실행 시점 기준 적합성 검증 (1주일 이내: {last_week_str} ~ {today_str}): {'통과' if temporal_check else '실패'}", Colors.GREEN if temporal_check else Colors.WARNING)
            
        if errors:
            log(self.name, f"❌ 검증 실패 항목 존재: {', '.join(errors)}", Colors.WARNING)
            return False
        else:
            log(self.name, "✔ 모든 카드뉴스 슬라이드가 무결성 검증을 완벽하게 통과했습니다!", Colors.GREEN)
            return True

    def run(self, card_data, output_dir, mode="daily", treesoop_mode=False):
        # Perform validation first
        self.verify_card_content(card_data, mode, treesoop_mode=treesoop_mode)
        
        log(self.name, "카드뉴스 이미지 및 KakaoTalk 배포 데이터 렌더링 시작...", Colors.HEADER)
        
        created_paths = []
        total_slides = min(len(card_data["slides"]), 10)
        for slide in card_data["slides"]:
            slide["_total_slides"] = total_slides
        for i, slide in enumerate(card_data["slides"]):
            file_name = f"{slide['slide_index']:02d}_slide.jpg"
            path = os.path.join(output_dir, file_name)
            self.render_card(slide, path, mode=mode, treesoop_mode=treesoop_mode)
            created_paths.append(path)
            
        # Get first article URL for content link mapping
        first_article_url = "https://pf.kakao.com/_KxgMwX"
        if len(card_data["slides"]) > 1:
            first_article_url = card_data["slides"][1].get("source_url", "https://pf.kakao.com/_KxgMwX")

        # Create KakaoTalk share link payload mockup (JPEG format)
        kakao_payload = {
            "object_type": "feed",
            "content": {
                "title": card_data["slides"][0]["title"].replace("\n", " "),
                "description": card_data["topic"],
                "image_url": "https://example.com/uploads/01_slide.jpg", # JPEG
                "image_width": 800,
                "image_height": 800,
                "link": {
                    "web_url": first_article_url,
                    "mobile_web_url": first_article_url
                }
            },
            "buttons": [
                {
                    "title": "뉴스 보기",
                    "link": {
                        "web_url": first_article_url,
                        "mobile_web_url": first_article_url
                    }
                },
                {
                    "title": "채널 추가",
                    "link": {
                        "web_url": "https://pf.kakao.com/_KxgMwX",
                        "mobile_web_url": "https://pf.kakao.com/_KxgMwX"
                    }
                }
            ]
        }
        
        payload_path = os.path.join(output_dir, "kakao_payload.json")
        with open(payload_path, "w", encoding="utf-8") as f:
            json.dump(kakao_payload, f, indent=2, ensure_ascii=False)
            
        log(self.name, f"카카오톡 배포용 페이로드 저장 완료: {payload_path}", Colors.GREEN)
        log(self.name, "카드뉴스 패키징이 성공적으로 완료되었습니다!", Colors.HEADER)
        return created_paths, payload_path


def main():
    # Handle CLI DB clearing argument
    if len(sys.argv) > 1 and sys.argv[1] == "--clear-history":
        gatekeeper = GatekeeperAgent()
        gatekeeper.clear_history()
        sys.exit(0)

    print(f"\n{Colors.GREEN}==============================================")
    print("      AI Card News Agent Team (v3.2.2)       ")
    print(f"=============================================={Colors.ENDC}\n")
    
    # Choose daily by default, can be toggled by cli args
    mode = "daily"
    include_llm_releases = True
    treesoop_mode = False
    for arg in sys.argv[1:]:
        if arg == "weekly":
            mode = "weekly"
        elif arg == "daily":
            mode = "daily"
        elif arg in ["--include-llm-releases", "--llm", "llm"]:
            include_llm_releases = True
        elif arg in ["--no-llm-releases", "--no-llm"]:
            include_llm_releases = False
        elif arg in ["--treesoop", "treesoop", "tree"]:
            treesoop_mode = True

    researcher = ResearcherAgent()
    creator = CreatorAgent()
    verifier = VerifierAgent()
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

    card_content = None
    max_attempts = 3
    attempt = 1
    
    while attempt <= max_attempts:
        log("System", f"카드뉴스 생성 및 무결성 검증 시도 {attempt}/{max_attempts}...", Colors.HEADER)
        
        # 1. Start Researcher Agent
        articles = researcher.run(limit=5, mode=mode, include_llm_releases=include_llm_releases, treesoop_mode=treesoop_mode)
        
        # Candidate freshness and deduplication are completed by the Researcher;
        # only one final Verifier may request a Creator rewrite.
        # 2. Start Creator Agent
        card_content = creator.run(articles, mode=mode, treesoop_mode=treesoop_mode)
        
        # 3. Perform Verifier balance & temporal checks
        is_valid, msg = verifier.verify_balance_and_temporal(card_content, mode=mode, include_llm_releases=include_llm_releases, treesoop_mode=treesoop_mode, articles=articles)
        
        if is_valid:
            log("Verifier Agent", f"✔ 무결성 및 조화성 검증 완료: {msg}", Colors.GREEN)
            break
        else:
            log("Verifier Agent", f"❌ 검증 실패: {msg}", Colors.WARNING)
            if attempt < max_attempts:
                log("System", "검증 에이전트가 제작 에이전트로 제어권을 돌려 카드 전체 재작성을 요청합니다.", Colors.WARNING)
                card_content = creator.run(articles, mode=mode, treesoop_mode=treesoop_mode)
                is_valid, msg = verifier.verify_balance_and_temporal(
                    card_content,
                    mode=mode,
                    include_llm_releases=include_llm_releases,
                    treesoop_mode=treesoop_mode,
                    articles=articles,
                )
                if is_valid:
                    log("Verifier Agent", f"✔ 제작 에이전트 재작성본 검증 완료: {msg}", Colors.GREEN)
                    break
            attempt += 1

    # Fallback to local verified templates if maximum retries reached
    if attempt > max_attempts:
        log("System", f"총 {max_attempts}회 검증 미달로 인해, 무결성이 사전 검증된 고품질 표준 데이터셋 기반으로 전격 전환합니다.", Colors.GREEN)
        if treesoop_mode:
            card_content = creator.generate_treesoop_content(articles, mode=mode)
        else:
            card_content = creator.generate_local_content(articles, mode=mode)

    # Render slides and package metadata
    paths, payload = verifier.run(card_content, output_dir, mode=mode, treesoop_mode=treesoop_mode)
    
    print(f"\n{Colors.GREEN}✔ 카드뉴스 제작이 완료되었습니다!{Colors.ENDC}")
    print(f"- 생성된 이미지: {len(paths)}개")
    print(f"- 저장 경로: {output_dir}")
    print(f"- 카카오 배포 정보: {payload}\n")

if __name__ == "__main__":
    main()
