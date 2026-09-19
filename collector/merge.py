"""병합 단계: 추출된 일정을 기존 events 와 합친다.

- 키 (gameId, type, version, phase) 가 같으면 같은 일정으로 본다.
- 신뢰도가 낮은 정보(LEAK)는 높은 정보(OFFICIAL)를 덮어쓰지 못한다.
- 시각까지 확인된 값은 날짜만 있는 값으로 덮어쓰지 않는다.
"""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
RANK = {"LEAK": 1, "ESTIMATED": 2, "OFFICIAL": 3}
TYPES = {"VERSION_UPDATE", "BANNER"}


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


def merge(events: dict[str, dict], game_id: str, x: dict, source_url: str) -> str | None:
    """events(키 → 일정)를 제자리에서 갱신. 바뀌었으면 'added'/'updated', 아니면 None."""
    type_ = x.get("type")
    version = str(x.get("version") or "").strip()
    if type_ not in TYPES or not version:
        return None
    start = to_iso(x.get("startDate"), x.get("startTime"), "00:00")
    if not start:
        return None

    phase = None if type_ == "VERSION_UPDATE" else (x.get("phase") if x.get("phase") in (1, 2) else None)
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
    if chars and chars != e.get("characters"):
        e["characters"] = chars
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
        if title:
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
