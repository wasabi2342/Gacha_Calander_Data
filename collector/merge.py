"""병합 단계: 추출된 일정을 기존 events 와 합친다.

- 키 (gameId, type, version, phase) 가 같으면 같은 일정으로 본다.
- 신뢰도가 낮은 정보(LEAK)는 높은 정보(OFFICIAL)를 덮어쓰지 못한다.
- 시각까지 확인된 값은 날짜만 있는 값으로 덮어쓰지 않는다.
"""
import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
RANK = {"LEAK": 1, "ESTIMATED": 2, "OFFICIAL": 3}
TYPES = {"VERSION_UPDATE", "BANNER"}
DATE_VERSION = re.compile(r"\d{4}-\d{2}-\d{2}")


def event_key(game_id: str, type_: str, version: str, phase) -> str:
    return f"{game_id}|{type_}|{version}|{phase if phase is not None else '-'}"


def event_id(game_id: str, type_: str, version: str, phase) -> str:
    kind = "update" if type_ == "VERSION_UPDATE" else f"p{phase if phase is not None else 0}"
    return f"{game_id}-{version}-{kind}"


def key_of(e: dict) -> str:
    return event_key(e["gameId"], e["type"], e["version"], e.get("phase"))


def to_iso(date: str | None, time: str | None, fallback: str) -> str | None:
    if not date:
        return None
    try:
        d = datetime.strptime(date.strip(), "%Y-%m-%d")
        t = datetime.strptime((time or fallback).strip(), "%H:%M")
    except ValueError:
        return None
    return d.replace(hour=t.hour, minute=t.minute, tzinfo=KST).isoformat()


def _characters(raw) -> list[dict]:
    out = []
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        name = (c.get("name") or "").strip()
        if not name:
            continue
        rarity = c.get("rarity") if isinstance(c.get("rarity"), int) else None
        out.append({"name": name, "rarity": rarity, "isNew": bool(c.get("isNew"))})
    return out


def _merge_characters(old: list[dict], new: list[dict], union: bool = False) -> list[dict]:
    """같은 캐릭터 목록이면 기존 정보(등급 등)를 지키고, 새 기사에만 있는 정보는 보탠다.
    목록 구성이 달라졌으면(캐릭터 추가·변경) 새 목록을 쓰되, 아는 등급은 이어받는다.
    union=True(날짜로 묶인 픽업)면 기사마다 일부 캐릭터만 언급하므로 합친다."""
    if not new:
        return old
    known = {c["name"]: c for c in old}
    if union:
        # 기존 캐릭터를 앞에 두고, 새 기사에서 처음 나온 캐릭터를 뒤에 붙인다
        new_by_name = {n["name"]: n for n in new}
        new = [new_by_name.get(c["name"], c) for c in old] + [n for n in new if n["name"] not in known]
    result = []
    for c in new:
        prev = known.get(c["name"], {})
        result.append({
            "name": c["name"],
            "rarity": c.get("rarity") if c.get("rarity") is not None else prev.get("rarity"),
            "isNew": c["isNew"] if c["name"] not in known else prev.get("isNew", c["isNew"]),
        })
    if {c["name"] for c in result} == set(known) and len(result) == len(old):
        # 이름 구성이 같으면 기존 순서를 유지해서 불필요한 변경을 막는다
        by_name = {c["name"]: c for c in result}
        result = [by_name[c["name"]] for c in old]
    return result


def is_date_version(version: str) -> bool:
    """버전 번호가 없는 게임(니케, 블루 아카이브 등)은 시작 날짜를 버전 자리에 쓴다"""
    return bool(DATE_VERSION.fullmatch(version or ""))


def merge(events: dict[str, dict], game_id: str, x: dict, source_url: str) -> str | None:
    """events(키 → 일정)를 제자리에서 갱신.
    반환: 'added' / 'updated' / None(이미 같은 정보) / 'skip:사유'(형식 문제로 버림) / 'ignore:사유'(일부러 제외)"""
    type_ = x.get("type")
    if type_ not in TYPES:
        return f"skip:알 수 없는 type({type_})"
    start = to_iso(x.get("startDate"), x.get("startTime"), "00:00")
    if not start:
        return f"skip:시작 날짜 없음/형식 오류({x.get('startDate')})"
    version = str(x.get("version") or "").strip()
    if not version:
        # 모델이 버전을 비워 보내도 버리지 않고 시작 날짜로 대신한다
        version = start[:10]
    date_keyed = is_date_version(version)
    if date_keyed and type_ == "VERSION_UPDATE":
        # 버전 번호가 없는 게임은 픽업 일정만 표시한다
        return "ignore:버전 번호 없는 업데이트"

    phase = None if (type_ == "VERSION_UPDATE" or date_keyed) else (x.get("phase") if x.get("phase") in (1, 2) else None)
    status = x.get("status") if x.get("status") in RANK else "ESTIMATED"
    time_known = bool(x.get("startTime")) and to_iso(x.get("startDate"), x.get("startTime"), "00:00") is not None
    end = to_iso(x.get("endDate"), x.get("endTime"), "23:59")
    end_confirmed = end is not None and status == "OFFICIAL"
    chars = _characters(x.get("characters"))
    title = (x.get("title") or "").strip()
    now = datetime.now(KST).isoformat(timespec="seconds")

    key = event_key(game_id, type_, version, phase)
    e = events.get(key)
    if e is None:
        events[key] = {
            "id": event_id(game_id, type_, version, phase),
            "gameId": game_id, "type": type_, "version": version, "phase": phase,
            "title": title or f"{version} {'업데이트' if type_ == 'VERSION_UPDATE' else '픽업'}",
            "characters": chars,
            "startAt": start, "timeKnown": time_known,
            "endAt": end, "endConfirmed": end_confirmed,
            "status": status, "note": None,
            "sourceUrl": source_url, "evidence": x.get("evidence"), "updatedAt": now,
        }
        return "added"

    if RANK[status] < RANK.get(e.get("status"), 0):
        return None

    changed = False
    merged_chars = _merge_characters(e.get("characters") or [], chars, union=date_keyed)
    if merged_chars != (e.get("characters") or []):
        e["characters"] = merged_chars
        changed = True
    if (time_known or not e.get("timeKnown")) and start != e.get("startAt"):
        e["startAt"], e["timeKnown"] = start, time_known
        changed = True
    if end and (end_confirmed or not e.get("endConfirmed")) and end != e.get("endAt"):
        e["endAt"], e["endConfirmed"] = end, end_confirmed
        changed = True
    if RANK[status] > RANK.get(e.get("status"), 0):
        e["status"] = status
        changed = True
    if changed:
        # 제목은 기사마다 표현만 다르다("상반기"/"전반")라서 비어 있을 때만 채운다
        if title and not e.get("title"):
            e["title"] = title
        e["sourceUrl"], e["evidence"], e["updatedAt"] = source_url, x.get("evidence"), now
        return "updated"
    return None


def prune_old(events: dict[str, dict], keep_days: int = 60) -> int:
    """끝난 지 keep_days 넘은 일정 삭제. 삭제 수 반환."""
    cutoff = datetime.now(KST) - timedelta(days=keep_days)
    old = [k for k, e in events.items()
           if datetime.fromisoformat(e.get("endAt") or e["startAt"]) < cutoff]
    for k in old:
        del events[k]
    return len(old)
