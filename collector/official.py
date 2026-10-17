"""공식 공지 수집. 뉴스보다 먼저, 가장 믿을 만한 1차 출처로 쓴다.

게임마다 게임사가 직접 올리는 공지를 읽어서 NewsItem(source="official") 으로 돌려준다.
본문(body)까지 채워서 돌려주므로 collect.py 는 기사 본문을 따로 가져오지 않는다.

| 게임 | 출처 |
|---|---|
| 원신 / 스타레일 / 젠존제 | 게임 안 공지 API (HoYoverse announcement getAnnList / getAnnContent) |
| 명조 | 공식 사이트 소식 JSON (kurogame G152/kr) |
| 블루 아카이브 | 넥슨 커뮤니티 공지 게시판 API |
| 엔드필드 | 게임 안 공지 API (game-hub.gryphline.com bulletin) |
| 이환 | 공식 사이트 소식 (nte.perfectworld.com/kr) |
| 명조 (튜닝 기간) | 네이버 게임 라운지 인게임 공지 게시판 (WutheringWaves / 28) |
| 니케 | 네이버 게임 라운지 공지 게시판 (nikke / 11) |
| 명일방주 | 아직 없음 |

공지 내용이 수정되면 다시 분석하도록, url 끝에 본문 해시(#v=...)를 붙여 seen 키를 바꾼다.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from sources import UA, NewsItem, fetch_article_text

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
MAX_BODY_CHARS = 8000
LOOKBACK_DAYS = 45          # 이보다 오래된 공지는 안 본다
TIMEOUT = 15


# ---------------- 공통 ----------------

def _get(url: str, **kw) -> requests.Response:
    res = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=TIMEOUT, **kw)
    res.raise_for_status()
    return res


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{2,}", "\n", text)


def _versioned(url: str, body: str) -> str:
    """같은 공지라도 내용이 바뀌면 다시 분석하도록 본문 해시를 붙인다"""
    h = hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]
    return f"{url}#v={h}"


def _wanted(title: str, keywords: list[str], exclude: list[str] | None = None) -> bool:
    t = (title or "").replace(" ", "")
    if exclude and any(x.replace(" ", "") in t for x in exclude):
        return False
    return any(k.replace(" ", "") in t for k in keywords)


def _walk(obj, has: tuple[str, ...]):
    """중첩된 JSON 안에서 has 키를 모두 가진 dict 를 전부 찾는다 (응답 구조가 조금 바뀌어도 버티게)"""
    if isinstance(obj, dict):
        if all(k in obj for k in has):
            yield obj
        for v in obj.values():
            yield from _walk(v, has)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, has)


def _recent(dt: datetime | None, now: datetime) -> bool:
    return dt is None or dt >= now - timedelta(days=LOOKBACK_DAYS)


# ---------------- HoYoverse (원신 / 스타레일 / 젠존제) ----------------

HOYO = {
    "genshin": {
        "base": "https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api",
        "params": {"game": "hk4e", "game_biz": "hk4e_global", "bundle_id": "hk4e_global", "platform": "pc",
                   "region": "os_asia", "level": "60", "uid": "100000000", "channel_id": "1"},
        # 캐릭터 기원: "「봄바람의 춤」 기원: ..." / 버전: "「...」 7.1 버전 업데이트 안내"
        "keywords": ["기원:", "버전업데이트"],
        "exclude": ["신의주조", "이벤트:", "세상여행"],  # 무기 기원, 이벤트 공지
        "link": "https://genshin.hoyoverse.com/ko/news",
    },
    "hsr": {
        "base": "https://sg-hkrpg-api.hoyoverse.com/common/hkrpg_global/announcement/api",
        "params": {"game": "hkrpg", "game_biz": "hkrpg_global", "bundle_id": "hkrpg_global", "platform": "pc",
                   "region": "prod_official_asia", "level": "70", "uid": "100000000", "channel_id": "1"},
        # "4.6 버전 이벤트 워프 (1)", "... 버전 업데이트 안내", "4.6 버전 업데이트 점검 예고"
        "keywords": ["이벤트워프", "콜라보워프", "버전업데이트안내", "업데이트점검"],
        "exclude": ["가입초대", "광추"],
        "link": "https://hsr.hoyoverse.com/ko-kr/news",
    },
    "zzz": {
        "base": "https://sg-announcement-api.hoyoverse.com/common/nap_global/announcement/api",
        "params": {"game": "nap", "game_biz": "nap_global", "bundle_id": "nap_global", "platform": "pc",
                   "region": "prod_gf_jp", "level": "60", "uid": "1000000000", "channel_id": "1"},
        # "3.2 버전 기간 한정 채널(상반기)", "3.2 버전 「...」 업데이트 공지"
        "keywords": ["한정채널", "업데이트공지", "업데이트점검"],
        "exclude": ["음동기", "W-엔진"],
        "link": "https://zenless.hoyoverse.com/ko-kr/news",
    },
}
# 게임 이용과 상관없는 공지는 건너뛴다 (게임별 exclude 와 함께 적용)
HOYO_EXCLUDE = ["수정및최적화", "최적화및", "발견한문제", "보상", "제재", "이용약관", "개인정보", "설문", "쿠폰", "리딤",
                "PlayStation", "모바일기기", "상점", "신규스테이지", "공략", "웹페이지"]


def _hoyo_time(s: str | None, tz_hours: int) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=tz_hours)))
    except ValueError:
        return None


def parse_hoyo(game_id: str, ann_list: dict, ann_content: dict, now: datetime) -> list[NewsItem]:
    """getAnnList + getAnnContent 응답 → 공지 목록"""
    cfg = HOYO[game_id]
    data = ann_list.get("data") or {}
    tz_hours = int(data.get("timezone") if isinstance(data.get("timezone"), int) else 8)
    contents = {c["ann_id"]: c for c in _walk(ann_content.get("data") or {}, ("ann_id", "content"))}

    items, seen = [], set()
    for a in _walk(data, ("ann_id", "title", "start_time")):
        aid = a["ann_id"]
        if aid in seen:
            continue
        seen.add(aid)
        title = html_to_text(a.get("title") or a.get("subtitle") or "")
        if not _wanted(title, cfg["keywords"], HOYO_EXCLUDE + cfg.get("exclude", [])):
            continue
        start = _hoyo_time(a.get("start_time"), tz_hours)
        if not _recent(start, now):
            continue
        c = contents.get(aid) or {}
        text = html_to_text(c.get("content") or "")
        if not text:
            continue
        body = (f"[공지 게시 기간(서버 시간 UTC+{tz_hours})] {a.get('start_time')} ~ {a.get('end_time')}\n"
                f"[시간대 안내] 이 공지의 시각은 따로 적혀 있지 않으면 서버 시간(UTC+{tz_hours})이다. "
                f"한국 시간(UTC+9)으로 바꿔서 적는다 (UTC+8이면 1시간 더함). "
                f"'버전 업데이트 후'처럼 시작 시각이 없으면 시각은 null로 둔다.\n\n{text}")[:MAX_BODY_CHARS]
        url = _versioned(f"{cfg['link']}?ann={aid}", body)
        items.append(NewsItem(title, url, text[:200], start or now, source="official", body=body))
    return items


def fetch_hoyo(game_id: str, now: datetime) -> list[NewsItem]:
    cfg = HOYO[game_id]
    params = {**cfg["params"], "lang": "ko-kr"}
    ann_list = _get(f"{cfg['base']}/getAnnList", params=params).json()
    if ann_list.get("retcode") != 0:
        raise RuntimeError(f"getAnnList retcode={ann_list.get('retcode')} {ann_list.get('message')}")
    ann_content = _get(f"{cfg['base']}/getAnnContent", params=params).json()
    return parse_hoyo(game_id, ann_list, ann_content, now)


# ---------------- 명조 (쿠로 게임즈 공식 사이트 JSON) ----------------

WUWA_BASE = "https://hw-media-cdn-mingchao.kurogame.com/akiwebsite/website2.0/json/G152/kr"
WUWA_LINK = "https://wutheringwaves.kurogames.com/kr/main/news/detail/{}"
WUWA_KEYWORDS = ["튜닝", "버전", "업데이트"]
WUWA_EXCLUDE = ["튜닝상세정보", "FAQ", "PlayStation", "XBOX", "무기이벤트튜닝", "무기콜라보튜닝", "무기튜닝"]


def _kst_time(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
    except ValueError:
        return None


def pick_wuwa(menu: list, now: datetime, limit: int) -> list[dict]:
    rows = [m for m in menu if isinstance(m, dict) and m.get("articleId") and _wanted(m.get("articleTitle", ""), WUWA_KEYWORDS, WUWA_EXCLUDE)]
    rows = [m for m in rows if _recent(_kst_time(m.get("startTime")), now)]
    rows.sort(key=lambda m: m.get("startTime") or "", reverse=True)
    return rows[:limit]


def parse_wuwa_article(meta: dict, article: dict, now: datetime) -> NewsItem | None:
    text = html_to_text(article.get("articleContent") or "")
    if not text:
        return None
    body = ("[시간대 안내] 시각 옆에 시간대가 적혀 있으면 그대로 따른다. '서버 시간'이면 아시아 서버(UTC+8) 기준이니 "
            "한국 시간으로 1시간 더한다.\n\n" + text)[:MAX_BODY_CHARS]
    title = article.get("articleTitle") or meta.get("articleTitle") or ""
    url = _versioned(WUWA_LINK.format(meta["articleId"]), body)
    return NewsItem(title, url, text[:200], _kst_time(meta.get("startTime")) or now, source="official", body=body)


def fetch_wuwa(now: datetime, limit: int) -> list[NewsItem]:
    t = int(time.time() * 1000)
    menu = _get(f"{WUWA_BASE}/ArticleMenu.json", params={"t": t}).json()
    items = []
    for meta in pick_wuwa(menu if isinstance(menu, list) else [], now, limit):
        try:
            art = _get(f"{WUWA_BASE}/article/{meta['articleId']}.json", params={"t": t}).json()
        except requests.RequestException as e:
            log.warning("[wuwa] 공지 본문 실패 %s: %s", meta.get("articleId"), e)
            continue
        item = parse_wuwa_article(meta, art, now)
        if item:
            items.append(item)
    return items


# ---------------- 블루 아카이브 (넥슨 커뮤니티 공지) ----------------

BA_ALIAS = "bluearchive"
BA_BOARD = 1076  # 공지사항
BA_LIST = "https://forum.nexon.com/api/v1/board/{board}/threads"
BA_THREAD = "https://forum.nexon.com/api/v1/thread/{thread}"
BA_LINK = "https://forum.nexon.com/bluearchive/board_view?board={board}&thread={thread}"
# 픽업 모집은 "업데이트 상세 안내"에 함께 나온다
BA_KEYWORDS = ["업데이트상세안내", "모집", "픽업"]
BA_EXCLUDE = ["정기점검예정", "무중단패치"]


def pick_blue_archive(listing, now: datetime, limit: int) -> list[dict]:
    rows = []
    for th in _walk(listing, ("threadId", "title")):
        created = th.get("createDate")
        dt = datetime.fromtimestamp(created, KST) if isinstance(created, (int, float)) else None
        if _wanted(th.get("title", ""), BA_KEYWORDS, BA_EXCLUDE) and _recent(dt, now):
            rows.append({**th, "_dt": dt})
    rows.sort(key=lambda r: r.get("createDate") or 0, reverse=True)
    return rows[:limit]


def parse_blue_archive_thread(meta: dict, thread: dict, now: datetime) -> NewsItem | None:
    t = next(_walk(thread, ("threadId", "content")), None) or thread
    text = html_to_text(t.get("content") or "")
    if not text:
        return None
    body = ("[시간대 안내] 한국 서버 공지라 시각은 한국 시간이다. '점검 후'처럼 시각이 없으면 시각은 null로 둔다.\n\n"
            + text)[:MAX_BODY_CHARS]
    url = _versioned(BA_LINK.format(board=BA_BOARD, thread=meta["threadId"]), body)
    return NewsItem(meta.get("title", ""), url, text[:200], meta.get("_dt") or now, source="official", body=body)


def fetch_blue_archive(now: datetime, limit: int) -> list[NewsItem]:
    listing = _get(BA_LIST.format(board=BA_BOARD), params={
        "alias": BA_ALIAS, "pageNo": 1, "paginationType": "PAGING", "pageSize": 15, "blockSize": 5, "hideType": "WEB",
    }).json()
    items = []
    for meta in pick_blue_archive(listing, now, limit):
        try:
            thread = _get(BA_THREAD.format(thread=meta["threadId"]), params={"alias": BA_ALIAS}).json()
        except (requests.RequestException, ValueError) as e:
            log.warning("[bluearchive] 공지 본문 실패 %s: %s", meta.get("threadId"), e)
            continue
        item = parse_blue_archive_thread(meta, thread, now)
        if item:
            items.append(item)
    return items


# ---------------- HTML 목록 페이지 (엔드필드 / 이환) ----------------

HTML_SITES = {
    "nte": {
        "lists": ["https://nte.perfectworld.com/kr/article/news/index.html",
                  "https://nte.perfectworld.com/kr/article/news/index1.html"],
        "link_re": re.compile(r"/kr/article/news/(?:gamenews|gamebroad|gameevent)/(\d{8})/\d+\.html$"),
        "keywords": ["픽업", "버전", "업데이트", "한정", "모집"],
        "exclude": ["제재", "임시점검"],
        "tz_note": "시각은 적혀 있는 시간대(KST 등)를 따른다.",
    },
}
_DATE_IN_TEXT = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def parse_list_page(game_id: str, html: str, base_url: str) -> list[dict]:
    """목록 페이지 HTML → [{url, title, date}] (공지 링크만).
    <a> 태그가 아니라 스크립트 안에 주소만 있는 경우도 찾는다 (제목은 비워 두고 본문 페이지에서 채움)"""
    cfg = HTML_SITES[game_id]
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    candidates = [(a["href"], a.get_text(" ", strip=True) or a.get("title", "")) for a in soup.find_all("a", href=True)]
    candidates += [(m.group(0), "") for m in re.finditer(r"(?:https?:)?//?[\w./-]*?/kr/article/news/\w+/\d{8}/\d+\.html", html or "")]
    for href, title in candidates:
        url = urljoin(base_url, href).split("#")[0].split("?")[0]
        m = cfg["link_re"].search(url)
        if not m or url in seen:
            continue
        if not title and any(r["url"] == url for r in out):
            continue
        seen.add(url)
        date = None
        if m.groups():  # 이환: 주소에 YYYYMMDD 가 들어 있다
            try:
                date = datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=KST)
            except ValueError:
                pass
        if date is None:
            d = _DATE_IN_TEXT.search(title)
            if d:
                date = datetime(int(d.group(1)), int(d.group(2)), int(d.group(3)), tzinfo=KST)
                title = _DATE_IN_TEXT.sub("", title).strip()
        out.append({"url": url, "title": title, "date": date})
    return out


def fetch_html_site(game_id: str, now: datetime, limit: int) -> list[NewsItem]:
    cfg = HTML_SITES[game_id]
    rows, seen = [], set()
    for list_url in cfg["lists"]:
        try:
            html = _get(list_url).text
        except requests.RequestException as e:
            log.warning("[%s] 공지 목록 실패 %s: %s", game_id, list_url, e)
            continue
        for r in parse_list_page(game_id, html, list_url):
            if r["url"] not in seen:
                seen.add(r["url"])
                rows.append(r)
    if not rows:
        raise RuntimeError("공지 목록에서 글을 하나도 못 찾았어요 (사이트 구조가 바뀌었을 수 있어요)")
    # 제목을 못 얻은 링크는 본문 페이지의 <title> 로 채운다 (최근 글만)
    for r in rows:
        if not r["title"] and _recent(r["date"], now):
            try:
                t = BeautifulSoup(_get(r["url"]).text, "html.parser").title
                r["title"] = re.split(r"\s*-\s*NTE", t.get_text(strip=True))[0] if t else ""
            except requests.RequestException:
                pass
    rows = [r for r in rows if _wanted(r["title"], cfg["keywords"], cfg["exclude"]) and _recent(r["date"], now)]
    rows.sort(key=lambda r: r["date"] or now, reverse=True)

    items = []
    for r in rows[:limit]:
        text = fetch_article_text(r["url"])
        if not text:
            continue
        body = f"[시간대 안내] {cfg['tz_note']}\n\n{text}"[:MAX_BODY_CHARS]
        items.append(NewsItem(r["title"], _versioned(r["url"], body), text[:200], r["date"] or now, source="official", body=body))
    return items


# ---------------- 엔드필드 (게임 안 공지 API) ----------------
# 게임 클라이언트가 띄우는 공지와 같은 데이터. 공식 사이트 소식 목록은 자바스크립트로 그려져서 읽을 수 없다.
EF_BULLETIN = "https://game-hub.gryphline.com/bulletin/v2/aggregate"
EF_PARAMS = {"lang": "ko-kr", "platform": "Windows", "channel": "6", "type": "0",
             "code": "endfield_U35PW8", "hideDetail": "0", "server": "3"}  # server 3 = 아시아
EF_LINK = "https://endfield.gryphline.com/ko-kr/news"
EF_KEYWORDS = ["헤드헌팅", "버전업데이트", "업데이트설명", "업데이트예고"]
EF_EXCLUDE = ["확률상세", "사전테스트", "게임도구", "Discord", "Steam", "판매"]


def parse_endfield(resp: dict, now: datetime, limit: int) -> list[NewsItem]:
    if resp.get("code") not in (0, None):
        raise RuntimeError(f"bulletin code={resp.get('code')} {resp.get('msg')}")
    rows = []
    for b in _walk(resp.get("data") or {}, ("cid", "title", "startAt")):
        title = html_to_text(b.get("title") or b.get("header") or "")
        if not _wanted(title, EF_KEYWORDS, EF_EXCLUDE):
            continue
        html = (b.get("data") or {}).get("html") if isinstance(b.get("data"), dict) else None
        text = html_to_text(html or "")
        if not text:
            continue
        start = datetime.fromtimestamp(b["startAt"], KST) if isinstance(b.get("startAt"), (int, float)) else None
        rows.append((start, title, b["cid"], text))
    rows.sort(key=lambda r: r[0] or now, reverse=True)
    items = []
    for start, title, cid, text in rows[:limit]:
        # 공지 게시 시각(startAt)은 처음 올린 날이라 오래돼 보여도, 내용(기간)은 최신일 수 있다 → 날짜로 거르지 않는다
        body = ("[시간대 안내] '서버 시간'은 아시아 서버(UTC+8) 기준이니 한국 시간으로 1시간 더한다. "
                "'버전 업데이트 점검 전'처럼 끝 시각이 정확히 없으면 endTime 은 null.\n\n" + text)[:MAX_BODY_CHARS]
        items.append(NewsItem(title, _versioned(f"{EF_LINK}?cid={cid}", body), text[:200], start or now,
                              source="official", body=body))
    return items


def fetch_endfield(now: datetime, limit: int) -> list[NewsItem]:
    return parse_endfield(_get(EF_BULLETIN, params=EF_PARAMS).json(), now, limit)


# ---------------- 네이버 게임 라운지 (명조 튜닝, 니케) ----------------
# 게임사가 직접 올리는 공지 게시판. 라운지 화면은 자바스크립트로 그려지고, 데이터는 아래 API 에서 온다.
# 응답 모양이 바뀌어도 버티도록 키 이름으로 찾아 들어간다 (_walk).
LOUNGE_API = "https://comm-api.game.naver.com/nng_main/v1/community/lounge/{lounge}"
LOUNGE_LINK = "https://game.naver.com/lounge/{lounge}/board/detail/{feed}"
LOUNGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://game.naver.com/",
    "Origin": "https://game.naver.com",
}
LOUNGES = {
    "wuwa": {
        "lounge": "WutheringWaves", "board": 28,  # 인게임 공지 게시판
        "keywords": ["캐릭터이벤트튜닝", "캐릭터튜닝", "버전업데이트", "업데이트점검"],
        "exclude": ["무기", "확률", "보상", "오류"],
        "tz_note": "시각 옆 시간대(UTC+8 / 서버 시간 등)를 따른다. '서버 시간'은 아시아 서버 UTC+8 이니 한국 시간으로 1시간 더한다. "
                   "적혀 있지 않으면 한국 시간으로 본다. 튜닝 이름 하나가 픽업 하나다.",
    },
    "nikke": {
        "lounge": "nikke", "board": 11,  # 공지사항 (공식 사이트가 안내하는 게시판)
        "keywords": ["모집", "업데이트", "픽업"],
        "exclude": ["점검완료", "보상", "오류", "당첨", "이벤트당첨"],
        "tz_note": "한국 서버 공지라 시각은 한국 시간이다. '점검 후'처럼 시각이 없으면 시각은 null.",
    },
}
LOUNGE_WARNINGS: dict[str, str] = {}  # 게임 id → 라운지만 실패했을 때 이유 (collect.py 가 Summary 에 표시)

_DATE_KEYS = ("createdDate", "createDate", "createdAt", "regDate", "createTime", "updatedDate")


def _lounge_time(v) -> datetime | None:
    """라운지 날짜: 밀리초/초 숫자, 'YYYYMMDDHHmmss', ISO 문자열 등 무엇이 와도 KST datetime"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, KST)
    s = str(v).strip()
    if s.isdigit() and len(s) >= 12:
        try:
            return datetime.strptime(s[:14].ljust(14, "0"), "%Y%m%d%H%M%S").replace(tzinfo=KST)
        except ValueError:
            return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=KST) if dt.tzinfo is None else dt.astimezone(KST)
    except ValueError:
        return None


def _feed_date(f: dict) -> datetime | None:
    for k in _DATE_KEYS:
        if f.get(k):
            return _lounge_time(f[k])
    return None


def _feed_html(obj) -> str:
    """상세 응답에서 본문 HTML 찾기 (contents / content / body 중 가장 긴 문자열)"""
    best = ""
    for d in _walk(obj, ("feedId",)):
        for k in ("contents", "content", "body", "html"):
            v = d.get(k)
            if isinstance(v, str) and len(v) > len(best):
                best = v
    return best


def parse_lounge_list(game_id: str, resp, now: datetime, limit: int) -> list[dict]:
    cfg = LOUNGES[game_id]
    rows, seen = [], set()
    for f in _walk(resp, ("feedId", "title")):
        fid = f["feedId"]
        if fid in seen:
            continue
        seen.add(fid)
        title = html_to_text(f.get("title") or "")
        dt = _feed_date(f)
        if _wanted(title, cfg["keywords"], cfg["exclude"]) and _recent(dt, now):
            rows.append({"feedId": fid, "title": title, "date": dt, "html": _feed_html({"feedId": fid, **f})})
    rows.sort(key=lambda r: r["date"] or now, reverse=True)
    return rows[:limit]


def lounge_item(game_id: str, row: dict, html: str, now: datetime) -> NewsItem | None:
    cfg = LOUNGES[game_id]
    text = html_to_text(html)
    if not text:
        return None
    body = f"[시간대 안내] {cfg['tz_note']}\n\n{text}"[:MAX_BODY_CHARS]
    url = _versioned(LOUNGE_LINK.format(lounge=cfg["lounge"], feed=row["feedId"]), body)
    return NewsItem(row["title"], url, text[:200], row["date"] or now, source="official", body=body)


def _lounge_get(url: str, **kw):
    res = requests.get(url, headers=LOUNGE_HEADERS, timeout=TIMEOUT, **kw)
    if res.status_code != 200:
        raise RuntimeError(f"라운지 HTTP {res.status_code}: {res.text[:150]}")
    try:
        return res.json()
    except ValueError as e:
        raise RuntimeError(f"라운지 응답이 JSON 이 아님: {res.text[:150]}") from e


def fetch_lounge(game_id: str, now: datetime, limit: int) -> list[NewsItem]:
    cfg = LOUNGES[game_id]
    base = LOUNGE_API.format(lounge=cfg["lounge"])
    resp = _lounge_get(f"{base}/feed", params={"boardId": cfg["board"], "buffFilteringYN": "N",
                                               "limit": 25, "offset": 0, "order": "NEW"})
    rows = parse_lounge_list(game_id, resp, now, limit)
    if not rows and not any(True for _ in _walk(resp, ("feedId", "title"))):
        raise RuntimeError(f"라운지 목록에서 글을 못 찾음: {str(resp)[:150]}")
    items = []
    for r in rows:
        html = r["html"]
        if len(html_to_text(html)) < 100:  # 목록에 본문이 없거나 짧으면 상세를 읽는다
            try:
                html = _feed_html(_lounge_get(f"{base}/feed/{r['feedId']}")) or html
            except RuntimeError as e:
                log.warning("[%s] 라운지 글 %s 본문 실패: %s", game_id, r["feedId"], e)
                continue
        item = lounge_item(game_id, r, html, now)
        if item:
            items.append(item)
    return items


# ---------------- 진입점 ----------------

OFFICIAL_GAMES = set(HOYO) | {"wuwa", "bluearchive", "endfield"} | set(HTML_SITES) | set(LOUNGES)


def has_official(game_id: str) -> bool:
    return game_id in OFFICIAL_GAMES


def fetch_official(game_id: str, limit: int = 8, now: datetime | None = None) -> list[NewsItem]:
    """해당 게임의 최근 공식 공지 (본문 포함). 출처가 없는 게임은 []"""
    now = now or datetime.now(KST)
    if game_id in HOYO:
        items = fetch_hoyo(game_id, now)
        items.sort(key=lambda i: i.published_at, reverse=True)
        return items[:limit]
    if game_id == "wuwa":
        # 버전 공지(공식 사이트) + 튜닝 기간 공지(라운지). 한쪽이 실패해도 다른 쪽은 쓴다
        items, errors = [], []
        for name, fn in (("공식 사이트", lambda: fetch_wuwa(now, limit)), ("라운지", lambda: fetch_lounge("wuwa", now, limit))):
            try:
                items += fn()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
        if errors and not items:
            raise RuntimeError(" / ".join(errors))
        if errors:
            LOUNGE_WARNINGS["wuwa"] = " / ".join(errors)
        return items
    if game_id in LOUNGES:
        return fetch_lounge(game_id, now, limit)
    if game_id == "bluearchive":
        return fetch_blue_archive(now, limit)
    if game_id == "endfield":
        return fetch_endfield(now, limit)
    if game_id in HTML_SITES:
        return fetch_html_site(game_id, now, limit)
    return []
