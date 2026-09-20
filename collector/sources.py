"""수집 단계: 네이버 뉴스 검색 + 기사 본문 추출"""
import logging
from dataclasses import dataclass
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; GachaCalendarBot/0.2; +https://github.com)"
MAX_BODY_CHARS = 6000

# 언론사마다 본문 컨테이너가 달라서 후보를 순서대로 시도
BODY_SELECTORS = [
    ".se-main-container",         # 네이버 블로그 (스마트에디터 ONE)
    "#postViewArea",              # 네이버 블로그 (예전 에디터)
    "#dic_area",                  # 네이버 뉴스
    "#article-view-content-div",  # ND소프트 CMS (다수 게임 매체)
    "#articleBody", ".article_body", ".news_body", ".article-body",
    "article",
]


@dataclass
class NewsItem:
    title: str
    url: str
    description: str
    published_at: datetime
    source: str = "news"  # "news" 또는 "blog"


def _strip_html(s: str) -> str:
    return BeautifulSoup(s or "", "html.parser").get_text()


# NAVER API HUB (네이버 클라우드 플랫폼). 기존 openapi.naver.com 검색 API가 이관된 곳
NAVER_API_HUB = "https://naverapihub.apigw.ntruss.com"


def search_news(client_id: str, client_secret: str, query: str, display: int = 10) -> list[NewsItem]:
    res = requests.get(
        f"{NAVER_API_HUB}/search/v1/news",
        params={"query": query, "display": display, "sort": "date", "format": "json"},
        headers={"X-NCP-APIGW-API-KEY-ID": client_id, "X-NCP-APIGW-API-KEY": client_secret},
        timeout=10,
    )
    res.raise_for_status()
    items = []
    for i in res.json().get("items", []):
        url = i.get("originallink") or i.get("link")
        try:
            pub = parsedate_to_datetime(i["pubDate"])
        except (KeyError, TypeError, ValueError):
            continue
        items.append(NewsItem(_strip_html(i.get("title")), url, _strip_html(i.get("description")), pub))
    return items


KST = timezone(timedelta(hours=9))


def search_blog(client_id: str, client_secret: str, query: str, display: int = 10) -> list[NewsItem]:
    """네이버 블로그 검색. 팬들이 정리한 픽업 일정 글로 뉴스에서 빠진 일정을 보충한다"""
    res = requests.get(
        f"{NAVER_API_HUB}/search/v1/blog",
        params={"query": query, "display": display, "sort": "date", "format": "json"},
        headers={"X-NCP-APIGW-API-KEY-ID": client_id, "X-NCP-APIGW-API-KEY": client_secret},
        timeout=10,
    )
    res.raise_for_status()
    items = []
    for i in res.json().get("items", []):
        try:
            # 블로그 결과는 작성일만 "YYYYMMDD" 로 준다
            pub = datetime.strptime(i.get("postdate", ""), "%Y%m%d").replace(hour=12, tzinfo=KST)
        except ValueError:
            continue
        items.append(NewsItem(_strip_html(i.get("title")), i.get("link"), _strip_html(i.get("description")),
                              pub, source="blog"))
    return items


_NAVER_BLOG = re.compile(r"https?://(?:m\.)?blog\.naver\.com/([^/?#]+)/(\d+)")
_NAVER_BLOG_QS = re.compile(r"blogId=([^&]+).*?logNo=(\d+)")


def _readable_url(url: str) -> str:
    """네이버 블로그 PC 주소는 본문이 iframe 안에 있어서 모바일 주소로 바꿔서 읽는다"""
    m = _NAVER_BLOG.match(url) or (_NAVER_BLOG_QS.search(url) if "blog.naver.com" in url else None)
    return f"https://m.blog.naver.com/{m.group(1)}/{m.group(2)}" if m else url


def fetch_article_text(url: str) -> str | None:
    url = _readable_url(url)
    try:
        res = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        res.raise_for_status()
    except requests.RequestException as e:
        log.warning("본문 가져오기 실패: %s (%s)", url, e)
        return None
    # 인코딩 표기가 없는 EUC-KR 페이지 대비
    if res.encoding is None or res.encoding.lower() == "iso-8859-1":
        res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")
    for sel in BODY_SELECTORS:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(" ", strip=True)
            if len(text) > 200:
                return text[:MAX_BODY_CHARS]
    body = soup.body.get_text(" ", strip=True) if soup.body else ""
    return body[:MAX_BODY_CHARS] or None
