"""수집 단계: 네이버 뉴스 검색 + 기사 본문 추출"""
import logging
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; GachaCalendarBot/0.2; +https://github.com)"
MAX_BODY_CHARS = 6000

# 언론사마다 본문 컨테이너가 달라서 후보를 순서대로 시도
BODY_SELECTORS = [
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


def _strip_html(s: str) -> str:
    return BeautifulSoup(s or "", "html.parser").get_text()


def search_news(client_id: str, client_secret: str, query: str, display: int = 10) -> list[NewsItem]:
    res = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": query, "display": display, "sort": "date"},
        headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
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


def fetch_article_text(url: str) -> str | None:
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
