"""공식 공지(verified) 우선순위 + 기존 동작 유지 확인"""
import copy
import json
from pathlib import Path

import merge as M

ROOT = Path(__file__).resolve().parent.parent


def banner(start, end, status="OFFICIAL", chars=("베스나",), phase=1, version="7.1", start_time=None, end_time="17:59"):
    return {"type": "BANNER", "version": version, "phase": phase, "title": f"{version} 전반 픽업",
            "characters": [{"name": c, "rarity": 5, "isNew": True} for c in chars],
            "startDate": start, "startTime": start_time, "endDate": end, "endTime": end_time,
            "status": status, "evidence": "t"}


def test_official_notice_overrides_news_official():
    ev = {}
    assert M.merge(ev, "genshin", banner("2026-09-23", "2026-10-12"), "news://a") == "added"
    # 공식 공지: 종료일이 하루 다르고 캐릭터가 하나 더 있음
    r = M.merge(ev, "genshin", banner("2026-09-23", "2026-10-13", chars=("베스나", "나히다"), end_time="18:59"),
                "official://1", verified=True)
    assert r == "updated"
    e = next(iter(ev.values()))
    assert e["verified"] is True and e["status"] == "OFFICIAL"
    assert e["endAt"].startswith("2026-10-13T18:59")
    assert [c["name"] for c in e["characters"]] == ["베스나", "나히다"]
    assert e["sourceUrl"] == "official://1"


def test_news_cannot_change_verified():
    ev = {}
    M.merge(ev, "genshin", banner("2026-09-23", "2026-10-13"), "official://1", verified=True)
    before = copy.deepcopy(ev)
    assert M.merge(ev, "genshin", banner("2026-09-24", "2026-10-20", chars=("다른캐",)), "news://b") is None
    assert ev == before


def test_verified_date_is_not_rejected_by_news_version_date():
    ev = {}
    # 뉴스가 버전 업데이트일을 잘못(9/30) 저장해 둔 상황
    M.merge(ev, "genshin", {"type": "VERSION_UPDATE", "version": "7.1", "phase": None, "title": "7.1",
                            "startDate": "2026-09-30", "status": "OFFICIAL"}, "news://v")
    # 뉴스의 전반 픽업(9/23)은 업데이트일과 안 맞아서 버려지지만
    assert M.merge(ev, "genshin", banner("2026-09-23", "2026-10-13"), "news://a").startswith("skip:")
    # 공식 공지는 그대로 들어간다
    assert M.merge(ev, "genshin", banner("2026-09-23", "2026-10-13"), "official://1", verified=True) == "added"
    # 그리고 매 실행의 자동 보정이 공식 날짜를 바꾸지 않는다
    M.cleanup(ev)
    e = ev[M.event_key("genshin", "BANNER", "7.1", 1)]
    assert e["startAt"].startswith("2026-09-23")


def test_verified_date_keyed_banner_can_move_later():
    ev = {}
    x = {"type": "BANNER", "version": None, "phase": None, "title": "모집", "characters": [{"name": "무츠키(드레스)", "isNew": True}],
         "startDate": "2026-09-14", "startTime": None, "endDate": "2026-09-29", "endTime": "10:59", "status": "OFFICIAL"}
    M.merge(ev, "bluearchive", x, "news://a")
    y = dict(x, startDate="2026-09-15")
    assert M.merge(ev, "bluearchive", y, "official://1", verified=True) == "updated"
    e = next(iter(ev.values()))
    assert e["startAt"].startswith("2026-09-15") and e["version"] == "2026-09-15" and e["verified"]


def test_existing_data_unchanged_by_new_rules():
    """지금 저장된 events.json 에 cleanup 을 돌려도 새 규칙 때문에 달라지는 게 없어야 한다 (verified 가 없으니까)"""
    doc = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))
    events = {M.key_of(e): e for e in doc["events"]}
    snapshot = copy.deepcopy(events)
    M.cleanup(events)
    assert events == snapshot
    assert not any("verified" in e for e in events.values())
