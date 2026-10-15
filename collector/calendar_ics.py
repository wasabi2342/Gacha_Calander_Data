"""events.json → 캘린더 구독 파일(.ics)

구글 캘린더 / 삼성 캘린더 / 아이폰 캘린더에서 'URL로 구독'하면 6시간마다 알아서 갱신된다.

- data/calendar.ics       : 모든 게임
- data/ics/<게임 id>.ics  : 게임 하나만 (원하는 게임만 골라 구독)

규칙
- 모든 일정은 '하루 종일' 일정으로 넣는다 (기기 시간대가 달라도 날짜가 어긋나지 않게). 정확한 시각은 설명에 적는다.
- 픽업: 시작일 ~ 종료일. 새벽 6시 전에 끝나는 픽업은 앱과 같이 전날까지로 표시한다.
  종료일이 아직 없으면 시작일 하루만 넣고 제목에 '(종료일 미정)'.
- 업데이트: 업데이트 날 하루.
- 내용이 같으면 파일도 글자 하나 안 바뀌게 만든다 (DTSTAMP 를 일정의 updatedAt 으로) → 불필요한 커밋이 안 생긴다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PRODID = "-//Gacha Calendar//subculture schedule//KO"
UID_DOMAIN = "gacha-calander-data"
STATUS_PREFIX = {"ESTIMATED": "(추정) ", "LEAK": "(유출) "}


# ---------------- 형식 도우미 ----------------

def escape(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\n").replace("\n", "\\n")


def fold(line: str) -> str:
    """한 줄이 75바이트를 넘으면 접는다 (RFC 5545). 한글이 중간에 잘리지 않게 글자 단위로."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > (75 if not out else 74):
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
    out.append(cur)
    return "\r\n ".join(out)


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _utc_stamp(iso: str | None) -> str:
    try:
        dt = datetime.fromisoformat(iso) if iso else None
    except ValueError:
        dt = None
    dt = dt or datetime(2026, 1, 1, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _clean_url(url: str | None) -> str | None:
    return url.split("#v=")[0] if url else None


def _hm(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------- 일정 하나 ----------------

def day_range(e: dict) -> tuple[date, date, bool]:
    """(첫날, 마지막 날, 종료일 아는지). 앱의 dayRange 와 같은 규칙"""
    start = datetime.fromisoformat(e["startAt"])
    first = start.date()
    if e["type"] != "BANNER" or not e.get("endAt"):
        return first, first, e["type"] != "BANNER"
    end = datetime.fromisoformat(e["endAt"])
    last = end.date()
    if end.hour < 6 and last > first:
        last -= timedelta(days=1)
    return first, max(first, last), True


def character_line(e: dict) -> str:
    chars = e.get("characters") or []
    new = [c["name"] for c in chars if c.get("isNew")]
    old = [f"{c['name']}(복각)" for c in chars if not c.get("isNew")]
    return ", ".join(new + old)


def vevent(e: dict, game_name: str) -> list[str]:
    first, last, end_known = day_range(e)
    banner = e["type"] == "BANNER"
    title = e.get("title") or ("픽업" if banner else "업데이트")
    if not banner and "업데이트" not in title:
        title += " 업데이트"
    chars = character_line(e)
    summary = f"{STATUS_PREFIX.get(e.get('status'), '')}[{game_name}] {title}"
    if chars:
        summary += f" - {chars}"
    if banner and not end_known:
        summary += " (종료일 미정)"

    start = datetime.fromisoformat(e["startAt"])
    desc = [f"게임: {game_name}", f"종류: {'픽업' if banner else '버전 업데이트'}"]
    desc.append(f"시작: {_hm(start) if e.get('timeKnown') else start.strftime('%Y-%m-%d') + ' (시각 미정)'}")
    if banner:
        if e.get("endAt"):
            end = datetime.fromisoformat(e["endAt"])
            desc.append(f"종료: {_hm(end)}{'' if e.get('endConfirmed') else ' (추정)'}")
        else:
            desc.append("종료: 아직 발표 전")
    if chars:
        desc.append(f"캐릭터: {chars}")
    status = "공식 공지 확인" if e.get("verified") else {"OFFICIAL": "공식", "ESTIMATED": "추정", "LEAK": "유출"}.get(e.get("status"), "")
    desc.append(f"상태: {status}")
    if e.get("note"):
        desc.append(f"메모: {e['note']}")
    url = _clean_url(e.get("sourceUrl"))
    if url:
        desc.append(f"출처: {url}")
    desc.append("(한국 시간 기준)")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{e['id']}@{UID_DOMAIN}",
        f"DTSTAMP:{_utc_stamp(e.get('updatedAt'))}",
        f"DTSTART;VALUE=DATE:{_ymd(first)}",
        f"DTEND;VALUE=DATE:{_ymd(last + timedelta(days=1))}",
        f"SUMMARY:{escape(summary)}",
        f"DESCRIPTION:{escape(chr(10).join(desc))}",
        f"CATEGORIES:{escape(game_name)},{'픽업' if banner else '업데이트'}",
        "TRANSP:TRANSPARENT",  # '바쁨'으로 표시하지 않는다
    ]
    if e.get("status") in ("ESTIMATED", "LEAK"):
        lines.append("STATUS:TENTATIVE")
    else:
        lines.append("STATUS:CONFIRMED")
    if url:
        lines.append(f"URL:{url}")
    lines.append("END:VEVENT")
    return lines


# ---------------- 캘린더 ----------------

def build_calendar(doc: dict, game_id: str | None = None) -> str:
    names = {g["id"]: g["name"] for g in doc.get("games", [])}
    cal_name = f"{names.get(game_id, game_id)} 일정" if game_id else "서브컬처 게임 일정"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(cal_name)}",
        f"X-WR-CALDESC:{escape('게임사 공식 공지로 모은 버전 업데이트·픽업 일정 (6시간마다 갱신)')}",
        "X-WR-TIMEZONE:Asia/Seoul",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for e in doc.get("events", []):
        if game_id and e["gameId"] != game_id:
            continue
        try:
            lines += vevent(e, names.get(e["gameId"], e["gameId"]))
        except (KeyError, ValueError, TypeError):
            continue  # 형식이 이상한 일정 하나 때문에 파일 전체가 깨지지 않게
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def _write_if_changed(path: Path, text: str) -> bool:
    data = text.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def write_calendars(doc: dict, data_dir: Path) -> list[str]:
    """data/calendar.ics + data/ics/<게임>.ics 를 쓰고, 바뀐 파일 이름 목록을 돌려준다"""
    changed = []
    if _write_if_changed(data_dir / "calendar.ics", build_calendar(doc)):
        changed.append("calendar.ics")
    for g in doc.get("games", []):
        if _write_if_changed(data_dir / "ics" / f"{g['id']}.ics", build_calendar(doc, g["id"])):
            changed.append(f"ics/{g['id']}.ics")
    return changed
