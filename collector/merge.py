"""병합 단계: 추출된 일정을 기존 events 와 합친다.

- 키 (gameId, type, version, phase) 가 같으면 같은 일정으로 본다.
- 버전 번호가 없는 게임(니케, 블루 아카이브 등)은 시작 날짜가 version 자리에 들어간다.
  기사마다 시작일이 하루씩 다르게 적히는 일이 많아서, 시작일이 MATCH_WINDOW_DAYS 이내이고
  신규 캐릭터가 겹치면 같은 픽업으로 본다. 이때 시작일은 더 이른 날(점검 종료일)을 남긴다.
- 신뢰도가 낮은 정보(LEAK)는 높은 정보(OFFICIAL)를 덮어쓰지 못한다.
- 시각까지 확인된 값은 날짜만 있는 값으로 덮어쓰지 않는다.
- 캐릭터 이름은 띄어쓰기·콜론·괄호 표기를 통일해서 비교한다.
"""
import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
RANK = {"LEAK": 1, "ESTIMATED": 2, "OFFICIAL": 3}
TYPES = {"VERSION_UPDATE", "BANNER"}
DATE_VERSION = re.compile(r"\d{4}-\d{2}-\d{2}")
MATCH_WINDOW_DAYS = 3

_NAME_KEY_STRIP = re.compile(r"[\s:：·・()（）\[\]「」『』'\"\-]")


# ---------- 이름 ----------

def clean_name(name: str) -> str:
    """표시용 이름: '길티 : 마이티 바니' / '길티:마이티 바니' → '길티: 마이티 바니'"""
    n = (name or "").strip().replace("：", ":").replace("（", "(").replace("）", ")")
    n = re.sub(r"\s*:\s*", ": ", n)
    n = re.sub(r"\(\s*", "(", n)
    n = re.sub(r"\s*\)", ")", n)
    n = re.sub(r"\s*\(", "(", n)
    return re.sub(r"\s+", " ", n).strip()


def name_key(name: str) -> str:
    """비교용 이름: 공백과 기호를 모두 뺀다"""
    return _NAME_KEY_STRIP.sub("", name or "").lower()


# ---------- 키 ----------

def event_key(game_id: str, type_: str, version: str, phase) -> str:
    return f"{game_id}|{type_}|{version}|{phase if phase is not None else '-'}"


def event_id(game_id: str, type_: str, version: str, phase) -> str:
    kind = "update" if type_ == "VERSION_UPDATE" else f"p{phase if phase is not None else 0}"
    return f"{game_id}-{version}-{kind}"


def key_of(e: dict) -> str:
    return event_key(e["gameId"], e["type"], e["version"], e.get("phase"))


def is_date_version(version: str) -> bool:
    """버전 번호가 없는 게임(니케, 블루 아카이브 등)은 시작 날짜를 버전 자리에 쓴다"""
    return bool(DATE_VERSION.fullmatch(version or ""))


def to_iso(date: str | None, time: str | None, fallback: str) -> str | None:
    if not date:
        return None
    try:
        d = datetime.strptime(date.strip(), "%Y-%m-%d")
        t = datetime.strptime((time or fallback).strip(), "%H:%M")
    except ValueError:
        return None
    return d.replace(hour=t.hour, minute=t.minute, tzinfo=KST).isoformat()


def _days_between(a: str, b: str) -> float:
    return abs((datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds()) / 86400


# ---------- 캐릭터 ----------

def _characters(raw) -> list[dict]:
    """모델 출력 → 정리된 캐릭터 목록 (이름 통일, 같은 캐릭터 중복 제거)"""
    out, seen = [], set()
    for c in raw or []:
        if not isinstance(c, dict):
            continue
        name = clean_name(c.get("name") or "")
        k = name_key(name)
        if not k or k in seen:
            continue
        seen.add(k)
        rarity = c.get("rarity") if isinstance(c.get("rarity"), int) else None
        out.append({"name": name, "rarity": rarity, "isNew": bool(c.get("isNew"))})
    return out


def _new_keys(chars: list[dict]) -> set[str]:
    """같은 픽업인지 판단할 때 쓰는 캐릭터. 신규가 있으면 신규만, 없으면 전부"""
    new = {name_key(c["name"]) for c in chars if c.get("isNew")}
    return new or {name_key(c["name"]) for c in chars}


def _merge_characters(old: list[dict], new: list[dict], union: bool = False) -> list[dict]:
    """같은 캐릭터 목록이면 기존 정보(등급 등)를 지키고, 새 기사에만 있는 정보는 보탠다.
    목록 구성이 달라졌으면(캐릭터 추가·변경) 새 목록을 쓰되, 아는 등급은 이어받는다.
    union=True(날짜로 묶인 픽업)면 기사마다 일부 캐릭터만 언급하므로 합친다."""
    if not new:
        return old
    known = {name_key(c["name"]): c for c in old}
    if union:
        # 기존 캐릭터를 앞에 두고, 새 기사에서 처음 나온 캐릭터를 뒤에 붙인다
        new_by_key = {name_key(n["name"]): n for n in new}
        new = ([new_by_key.get(name_key(c["name"]), c) for c in old]
               + [n for n in new if name_key(n["name"]) not in known])
    result = []
    for c in new:
        k = name_key(c["name"])
        prev = known.get(k, {})
        result.append({
            "name": prev.get("name", c["name"]),   # 먼저 저장된 표기를 유지
            "rarity": c.get("rarity") if c.get("rarity") is not None else prev.get("rarity"),
            "isNew": prev.get("isNew", c["isNew"]) if k in known else c["isNew"],
        })
    if {name_key(c["name"]) for c in result} == set(known) and len(result) == len(old):
        # 이름 구성이 같으면 기존 순서를 유지해서 불필요한 변경을 막는다
        by_key = {name_key(c["name"]): c for c in result}
        result = [by_key[name_key(c["name"])] for c in old]
    return result


# ---------- 같은 픽업 찾기 (버전 없는 게임) ----------

def _find_same_banner(events: dict[str, dict], game_id: str, start: str, chars: list[dict]) -> str | None:
    keys = _new_keys(chars)
    if not keys:
        return None
    for k, e in events.items():
        if (e["gameId"] == game_id and e["type"] == "BANNER" and is_date_version(e["version"])
                and _days_between(start, e["startAt"]) <= MATCH_WINDOW_DAYS
                and keys & _new_keys(e.get("characters") or [])):
            return k
    return None


def _rekey(events: dict[str, dict], old_key: str, e: dict) -> None:
    """버전 없는 픽업의 시작일이 바뀌면 키와 id도 새 날짜로 옮긴다"""
    e["version"] = e["startAt"][:10]
    e["id"] = event_id(e["gameId"], e["type"], e["version"], None)
    new_key = key_of(e)
    del events[old_key]
    if new_key in events and events[new_key] is not e:
        _absorb(events[new_key], e)
    else:
        events[new_key] = e


def _absorb(keep: dict, drop: dict) -> None:
    """drop 의 정보를 keep 에 합친다 (keep 이 더 이른 픽업)"""
    keep["characters"] = _merge_characters(keep.get("characters") or [], drop.get("characters") or [], union=True)
    if RANK.get(drop.get("status"), 0) > RANK.get(keep.get("status"), 0):
        keep["status"] = drop["status"]
    if drop.get("endAt") and (not keep.get("endAt") or (drop.get("endConfirmed") and not keep.get("endConfirmed"))):
        keep["endAt"], keep["endConfirmed"] = drop["endAt"], drop.get("endConfirmed", False)
    if not keep.get("title") and drop.get("title"):
        keep["title"] = drop["title"]


# ---------- 병합 ----------

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
    if date_keyed:
        version = start[:10]  # 모델이 version 과 startDate 를 다르게 줘도 시작일 기준으로 통일

    phase = None if (type_ == "VERSION_UPDATE" or date_keyed) else (x.get("phase") if x.get("phase") in (1, 2) else None)
    status = x.get("status") if x.get("status") in RANK else "ESTIMATED"
    time_known = bool(x.get("startTime")) and to_iso(x.get("startDate"), x.get("startTime"), "00:00") is not None
    end = to_iso(x.get("endDate"), x.get("endTime"), "23:59")
    end_confirmed = end is not None and status == "OFFICIAL"
    chars = _characters(x.get("characters"))
    if date_keyed and not chars:
        return "skip:버전 없는 픽업인데 캐릭터가 없음"
    title = (x.get("title") or "").strip()
    now = datetime.now(KST).isoformat(timespec="seconds")

    key = event_key(game_id, type_, version, phase)
    e = events.get(key)
    if e is None and date_keyed:
        found = _find_same_banner(events, game_id, start, chars)
        if found:
            key, e = found, events[found]
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

    rekey = False
    if date_keyed and start[:10] != e["startAt"][:10]:
        # 같은 픽업인데 날짜가 다르면 더 이른 날(점검 종료일)을 남긴다
        if start < e["startAt"]:
            e["startAt"], e["timeKnown"] = start, time_known
            changed = rekey = True
    elif (time_known or not e.get("timeKnown")) and start != e.get("startAt"):
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
        if rekey:
            _rekey(events, key, e)
        return "updated"
    return None


# ---------- 정리 ----------

def cleanup(events: dict[str, dict]) -> int:
    """이미 저장된 데이터 정리. 매 실행마다 돌아서 예전 규칙으로 쌓인 중복도 고친다.
    1) 캐릭터 이름 표기 통일 + 같은 캐릭터 중복 제거
    2) 버전 없는 게임에서 같은 픽업이 여러 날짜로 나뉜 것 합치기 (이른 날짜로)
    반환: 바뀐 일정 수"""
    changed = 0
    for e in events.values():
        chars = _characters(e.get("characters"))
        if chars != (e.get("characters") or []):
            e["characters"] = chars
            changed += 1

    for game_id in {e["gameId"] for e in events.values()}:
        while True:
            banners = sorted(
                ((k, e) for k, e in events.items()
                 if e["gameId"] == game_id and e["type"] == "BANNER" and is_date_version(e["version"])),
                key=lambda ke: ke[1]["startAt"])
            pair = next(((a, b) for i, a in enumerate(banners) for b in banners[i + 1:]
                         if _days_between(a[1]["startAt"], b[1]["startAt"]) <= MATCH_WINDOW_DAYS
                         and _new_keys(a[1]["characters"]) & _new_keys(b[1]["characters"])), None)
            if pair is None:
                break
            (_, keep), (drop_key, drop) = pair
            _absorb(keep, drop)
            del events[drop_key]
            changed += 1
    return changed


def prune_old(events: dict[str, dict], keep_days: int = 60) -> int:
    """끝난 지 keep_days 넘은 일정 삭제. 삭제 수 반환."""
    cutoff = datetime.now(KST) - timedelta(days=keep_days)
    old = [k for k, e in events.items()
           if datetime.fromisoformat(e.get("endAt") or e["startAt"]) < cutoff]
    for k in old:
        del events[k]
    return len(old)
