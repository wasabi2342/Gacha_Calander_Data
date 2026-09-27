"""collect.run_game 전체 흐름 (네트워크·모델 없이)"""
from datetime import datetime, timedelta, timezone

import collect
from sources import NewsItem

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 28, 3, 0, tzinfo=KST)


def fake_extract(provider, api_key, model, game, title, body, published_at, source="news"):
    if source == "official":
        return [{"type": "BANNER", "version": "7.1", "phase": 1, "title": "7.1 전반 픽업",
                 "characters": [{"name": "베스나", "rarity": 5, "isNew": True}],
                 "startDate": "2026-09-23", "startTime": None, "endDate": "2026-10-13", "endTime": "18:59",
                 "status": "OFFICIAL", "evidence": body[:20]}]
    # 뉴스: 공식 공지와 종료일이 다르고, 다음 버전 소식도 있음
    return [{"type": "BANNER", "version": "7.1", "phase": 1, "title": "7.1 전반 픽업",
             "characters": [{"name": "베스나", "rarity": 5, "isNew": True}],
             "startDate": "2026-09-23", "startTime": None, "endDate": "2026-10-10", "endTime": None,
             "status": "OFFICIAL", "evidence": "뉴스"},
            {"type": "VERSION_UPDATE", "version": "7.2", "phase": None, "title": "7.2",
             "startDate": "2026-11-04", "startTime": None, "status": "OFFICIAL", "evidence": "뉴스"}]


def setup(monkeypatch, official_items):
    calls = {"body": []}
    monkeypatch.setattr(collect, "fetch_official", lambda gid, limit: official_items)
    monkeypatch.setattr(collect, "search_news", lambda *a, **k: [
        NewsItem("원신 7.2 업데이트 예고", "https://news/1", "요약", NOW)])
    monkeypatch.setattr(collect, "search_blog", lambda *a, **k: [])
    monkeypatch.setattr(collect, "fetch_article_text", lambda url: "뉴스 본문")

    def spy(*a, **k):
        calls["body"].append((k.get("source"), a[5]))
        return fake_extract(*a, **k)
    monkeypatch.setattr(collect, "extract", spy)
    monkeypatch.setattr(collect, "CALL_INTERVAL_SEC", 0)
    for k in collect.STATS:
        collect.STATS[k] = 0
    return calls


ENV = {"naver_id": "x", "naver_secret": "y", "provider": "gemini", "api_key": "k", "model": "m",
       "use_blog": False, "use_official": True, "news_cap": True}


def test_official_first_then_news_capped(monkeypatch):
    official_item = NewsItem("「봄바람의 춤」 기원", "https://genshin.hoyoverse.com/ko/news?ann=1#v=abc", "요약", NOW,
                             source="official", body="공식 공지 본문 전체")
    calls = setup(monkeypatch, [official_item])
    events, seen, report = {}, {}, []
    collect.run_game(collect.GAMES_BY_ID["genshin"], events, seen, ENV, False, report)

    # 공식 공지를 먼저, 미리 채워 둔 본문 그대로 모델에 보냄
    assert calls["body"][0] == ("official", "공식 공지 본문 전체")
    banner = events["genshin|BANNER|7.1|1"]
    assert banner["verified"] is True and banner["endAt"].startswith("2026-10-13T18:59")  # 뉴스(10/10)가 못 덮어씀
    # 공식 공지가 있는 게임이라 뉴스의 "공식" 소식은 추정으로 저장
    assert events["genshin|VERSION_UPDATE|7.2|-"]["status"] == "ESTIMATED"
    assert official_item.url in seen and seen[official_item.url]["source"] == "official"
    assert collect.STATS["official_ok"] == 1 and collect.STATS["official_read"] == 1
    assert any(label.startswith("[공식]") for *_, label in report)

    # 다음 실행: 같은 공지는 다시 분석하지 않음
    calls["body"].clear()
    collect.run_game(collect.GAMES_BY_ID["genshin"], events, seen, ENV, False, [])
    assert all(src != "official" for src, _ in calls["body"])


def test_official_failure_falls_back_to_news(monkeypatch):
    setup(monkeypatch, [])

    def boom(gid, limit):
        raise RuntimeError("403")
    monkeypatch.setattr(collect, "fetch_official", boom)
    events = {}
    collect.run_game(collect.GAMES_BY_ID["genshin"], events, {}, ENV, False, [])
    assert collect.STATS["official_fail"] == 1
    assert "genshin|BANNER|7.1|1" in events  # 뉴스로는 계속 채워짐


def test_games_without_official_keep_news_status(monkeypatch):
    setup(monkeypatch, [])
    monkeypatch.setattr(collect, "search_news", lambda *a, **k: [
        NewsItem("명일방주 신규 업데이트", "https://news/2", "요약", NOW)])
    events = {}
    collect.run_game(collect.GAMES_BY_ID["arknights"], events, {}, ENV, False, [])
    # 명일방주는 공식 공지 출처가 없어서 예전처럼 뉴스의 OFFICIAL 을 그대로 둔다
    assert events["arknights|VERSION_UPDATE|7.2|-"]["status"] == "OFFICIAL"
