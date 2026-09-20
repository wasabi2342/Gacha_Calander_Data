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
HALF_VERSION_DAYS = 21  # 버전 하나가 보통 6주, 전반·후반 각 3주

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


def _find_phased_banner(events: dict[str, dict], game_id: str, version: str, chars: list[dict]) -> str | None:
    keys = _new_keys(chars)
    if not keys:
        return None
    for ph in (1, 2):
        k = event_key(game_id, "BANNER", version, ph)
        if k in events and keys & _new_keys(events[k].get("characters") or []):
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


# ---------- 버전 있는 게임의 날짜 검사 ----------

def _version_start(events: dict[str, dict], game_id: str, version: str) -> str | None:
    v = events.get(event_key(game_id, "VERSION_UPDATE", version, None))
    return v["startAt"] if v else None


def _banner_start_problem(events: dict[str, dict], game_id: str, version: str, phase, start: str) -> str | None:
    """말이 안 되는 픽업 시작일이면 이유를 돌려준다.
    - 전반 픽업은 버전 업데이트 날(±2일)에 시작한다
    - 후반 픽업은 버전 업데이트 7일 이후, 전반 픽업 시작 이후에 시작한다
    - 어떤 픽업도 버전 업데이트보다 먼저 시작하지 않는다"""
    vs = _version_start(events, game_id, version)
    st = datetime.fromisoformat(start)
    if vs:
        v = datetime.fromisoformat(vs)
        if phase == 1 and abs((st - v).total_seconds()) > 2 * 86400:
            return f"전반 픽업 시작일({start[:10]})이 {version} 업데이트일({vs[:10]})과 안 맞음"
        if phase == 2 and st <= v + timedelta(days=7):
            return f"후반 픽업 시작일({start[:10]})이 {version} 업데이트일({vs[:10]})과 너무 가까움"
        if st < v - timedelta(days=1):
            return f"픽업 시작일({start[:10]})이 {version} 업데이트일({vs[:10]})보다 이름"
    if phase == 2:
        p1 = events.get(event_key(game_id, "BANNER", version, 1))
        if p1 and st <= datetime.fromisoformat(p1["startAt"]):
            return f"후반 픽업 시작일({start[:10]})이 전반 픽업 시작일({p1['startAt'][:10]}) 이전"
    return None


# ---------- 병합 ----------

def merge(events: dict[str, dict], game_id: str, x: dict, source_url: str) -> str | None:
    """events(키 → 일정)를 제자리에서 갱신.
    반환: 'added' / 'updated' / None(이미 같은 정보) / 'skip:사유'(형식 문제로 버림) / 'ignore:사유'(일부러 제외)"""
    type_ = x.get("type")
    if type_ not in TYPES:
        return f"skip:알 수 없는 type({type_})"
    start = to_iso(x.get("startDate"), x.get("startTime"), "00:00")
    version = str(x.get("version") or "").strip()
    if not version:
        if not start:
            return f"skip:버전도 시작 날짜도 없음({x.get('startDate')})"
        # 모델이 버전을 비워 보내도 버리지 않고 시작 날짜로 대신한다
        version = start[:10]
    date_keyed = is_date_version(version)
    if date_keyed and type_ == "VERSION_UPDATE":
        # 버전 번호가 없는 게임은 픽업 일정만 표시한다
        return "ignore:버전 번호 없는 업데이트"
    if date_keyed:
        if not start:
            return "skip:버전 없는 픽업인데 시작 날짜가 없음"
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

    start_problem = None
    if start and type_ == "BANNER" and not date_keyed:
        start_problem = _banner_start_problem(events, game_id, version, phase, start)
        if start_problem:
            start, time_known = None, False  # 틀린 날짜는 버리고 나머지 정보만 쓴다
    if not start and e is None:
        return f"skip:{start_problem or '시작 날짜 없음/형식 오류'}"

    if e is None and date_keyed:
        found = _find_same_banner(events, game_id, start, chars)
        if found:
            key, e = found, events[found]
    if e is None and type_ == "BANNER" and not date_keyed and phase is None:
        # 전반/후반을 모르는 픽업은, 같은 버전에서 신규 캐릭터가 겹치는 픽업이 있으면 그쪽으로 합친다
        found = _find_phased_banner(events, game_id, version, chars)
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
    # 기사마다 일부 캐릭터만 언급하는 경우가 많아서 기본은 합치기.
    # 더 믿을 만한 출처(예: 유출 → 공식)가 오면 그 목록으로 교체한다
    replace = RANK[status] > RANK.get(e.get("status"), 0)
    merged_chars = _merge_characters(e.get("characters") or [], chars, union=not replace)
    if merged_chars != (e.get("characters") or []):
        e["characters"] = merged_chars
        changed = True

    rekey = False
    old_rank = RANK.get(e.get("status"), 0)
    if not start:
        pass  # 이번 기사에는 믿을 만한 시작일이 없음
    elif date_keyed:
        if start[:10] != e["startAt"][:10] and start < e["startAt"]:
            # 같은 픽업인데 날짜가 다르면 더 이른 날(점검 종료일)을 남긴다
            e["startAt"], e["timeKnown"] = start, time_known
            changed = rekey = True
    elif start != e.get("startAt"):
        # 날짜만 있는 정보끼리는 먼저 저장된 것을 믿는다. 시각이 새로 확인됐거나
        # 더 믿을 만한 출처(유출 → 추정 → 공식)일 때만 바꾼다
        if (time_known and (not e.get("timeKnown") or RANK[status] >= old_rank)) or RANK[status] > old_rank:
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

    # 전반/후반을 모른 채 저장된 픽업이 같은 버전의 전반·후반 픽업과 겹치면 합친다
    for k, e in list(events.items()):
        if e["type"] == "BANNER" and not is_date_version(e["version"]) and e.get("phase") is None:
            found = _find_phased_banner(events, e["gameId"], e["version"], e.get("characters") or [])
            if found and found != k:
                _absorb(events[found], e)
                del events[k]
                changed += 1

    changed += _repair_version_banners(events)

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


def _repair_version_banners(events: dict[str, dict]) -> int:
    """이미 잘못 저장된 픽업 시작일 바로잡기
    - 전반 픽업이 버전 업데이트일과 안 맞으면 → 버전 업데이트일
    - 후반 픽업이 말이 안 되면 → 전반 픽업 종료일"""
    fixed = 0
    for e in list(events.values()):
        if e["type"] != "BANNER" or is_date_version(e["version"]) or e.get("phase") not in (1, 2):
            continue
        if not _banner_start_problem(events, e["gameId"], e["version"], e["phase"], e["startAt"]):
            continue
        new_start, guessed = None, False
        vs = _version_start(events, e["gameId"], e["version"])
        if e["phase"] == 1:
            new_start = vs
        else:
            p1 = events.get(event_key(e["gameId"], "BANNER", e["version"], 1))
            if p1 and p1.get("endAt"):
                new_start = p1["endAt"]
            elif vs:
                # 전반 종료일도 모르면 보통 3주 뒤에 후반이 시작하니 그렇게 추정
                new_start = (datetime.fromisoformat(vs) + timedelta(days=HALF_VERSION_DAYS)).isoformat()
                guessed = True
        if new_start and new_start != e["startAt"]:
            e["startAt"], e["timeKnown"] = new_start, False
            if guessed:
                e["status"] = "ESTIMATED" if e.get("status") == "OFFICIAL" else e.get("status")
                e["note"] = "시작일은 업데이트 3주 뒤로 추정"
            fixed += 1
    return fixed


def prune_old(events: dict[str, dict], keep_days: int = 60) -> int:
    """끝난 지 keep_days 넘은 일정 삭제. 삭제 수 반환."""
    cutoff = datetime.now(KST) - timedelta(days=keep_days)
    old = [k for k, e in events.items()
           if datetime.fromisoformat(e.get("endAt") or e["startAt"]) < cutoff]
    for k in old:
        del events[k]
    return len(old)
