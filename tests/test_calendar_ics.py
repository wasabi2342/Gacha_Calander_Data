"""캘린더 구독 파일(.ics) 테스트"""
import json
from datetime import date
from pathlib import Path

import icalendar

import calendar_ics as C

ROOT = Path(__file__).resolve().parent.parent

DOC = {
    "updatedAt": "2026-10-12T03:00:00+09:00",
    "games": [{"id": "genshin", "name": "원신", "color": "#D4A017"}, {"id": "hsr", "name": "스타레일", "color": "#6B5BD6"}],
    "events": [
        {"id": "genshin-7.1-p1", "gameId": "genshin", "type": "BANNER", "version": "7.1", "phase": 1, "title": "7.1 전반 픽업",
         "characters": [{"name": "보댜니차", "rarity": 5, "isNew": False}, {"name": "베스나", "rarity": 5, "isNew": True}],
         "startAt": "2026-09-23T00:00:00+09:00", "timeKnown": False,
         "endAt": "2026-10-13T18:59:00+09:00", "endConfirmed": True, "status": "OFFICIAL", "verified": True,
         "sourceUrl": "https://genshin.hoyoverse.com/ko/news?ann=1#v=abcd1234", "updatedAt": "2026-09-28T05:00:00+09:00"},
        {"id": "genshin-7.1-update", "gameId": "genshin", "type": "VERSION_UPDATE", "version": "7.1", "phase": None,
         "title": "7.1", "characters": [], "startAt": "2026-09-23T07:00:00+09:00", "timeKnown": True,
         "endAt": None, "endConfirmed": False, "status": "OFFICIAL", "updatedAt": "2026-09-28T05:00:00+09:00"},
        {"id": "hsr-4.7-p1", "gameId": "hsr", "type": "BANNER", "version": "4.7", "phase": 1, "title": "4.7 전반 워프",
         "characters": [{"name": "누군가", "isNew": True}], "startAt": "2026-11-05T00:00:00+09:00", "timeKnown": False,
         "endAt": None, "endConfirmed": False, "status": "ESTIMATED", "updatedAt": "2026-10-01T05:00:00+09:00"},
        {"id": "hsr-4.6-p2", "gameId": "hsr", "type": "BANNER", "version": "4.6", "phase": 2, "title": "4.6 후반 워프",
         "characters": [], "startAt": "2026-10-15T12:00:00+09:00", "timeKnown": True,
         "endAt": "2026-11-05T03:59:00+09:00", "endConfirmed": True, "status": "OFFICIAL", "updatedAt": "2026-10-01T05:00:00+09:00"},
    ],
}


def events_of(text: str):
    return {str(v["UID"]): v for v in icalendar.Calendar.from_ical(text.encode()).walk("VEVENT")}


def test_banner_is_all_day_through_last_day():
    ev = events_of(C.build_calendar(DOC))["genshin-7.1-p1@gacha-calander-data"]
    assert ev["DTSTART"].dt == date(2026, 9, 23)
    assert ev["DTEND"].dt == date(2026, 10, 14)  # 하루 종일 일정은 끝 다음 날까지
    assert str(ev["SUMMARY"]) == "[원신] 7.1 전반 픽업 - 베스나, 보댜니차(복각)"
    assert "공식 공지 확인" in str(ev["DESCRIPTION"]) and "18:59" in str(ev["DESCRIPTION"])
    assert str(ev["URL"]) == "https://genshin.hoyoverse.com/ko/news?ann=1"  # #v= 해시는 뺀다


def test_update_and_estimated_and_early_end():
    evs = events_of(C.build_calendar(DOC))
    up = evs["genshin-7.1-update@gacha-calander-data"]
    assert str(up["SUMMARY"]) == "[원신] 7.1 업데이트"
    assert up["DTEND"].dt == date(2026, 9, 24)
    est = evs["hsr-4.7-p1@gacha-calander-data"]
    assert str(est["SUMMARY"]).startswith("(추정) [스타레일]") and "(종료일 미정)" in str(est["SUMMARY"])
    assert str(est["STATUS"]) == "TENTATIVE"
    early = evs["hsr-4.6-p2@gacha-calander-data"]
    assert early["DTEND"].dt == date(2026, 11, 5)  # 11/5 03:59 종료 → 11/4 까지 표시


def test_per_game_file_and_lines():
    text = C.build_calendar(DOC, "hsr")
    assert set(events_of(text)) == {"hsr-4.7-p1@gacha-calander-data", "hsr-4.6-p2@gacha-calander-data"}
    assert "X-WR-CALNAME:스타레일 일정" in text
    raw = text.encode()
    assert max(len(line) for line in raw.split(b"\r\n")) <= 75
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0


def test_write_only_when_changed(tmp_path):
    first = C.write_calendars(DOC, tmp_path)
    assert first == ["calendar.ics", "ics/genshin.ics", "ics/hsr.ics"]
    assert C.write_calendars(DOC, tmp_path) == []


def test_real_data_builds():
    doc = json.loads((ROOT / "data" / "events.json").read_text(encoding="utf-8"))
    evs = events_of(C.build_calendar(doc))
    assert len(evs) == len(doc["events"])
