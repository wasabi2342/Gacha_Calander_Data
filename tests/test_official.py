"""공식 공지 파서 테스트 (네트워크 없이, 실제 응답과 같은 모양의 샘플로)"""
from datetime import datetime, timedelta, timezone

import official

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 28, 3, 0, tzinfo=KST)


def test_hoyo_list_and_content_are_joined_and_filtered():
    ann_list = {"retcode": 0, "data": {
        "timezone": 8,
        "list": [{"type_label": "게임", "list": [
            {"ann_id": 1, "title": "「봄바람의 춤」 기원: 「눈꽃 연회의 검·베스나(바람)」 확률 UP!", "subtitle": "", "start_time": "2026-09-21 12:00:00", "end_time": "2026-10-13 17:59:00"},
            {"ann_id": 2, "title": "게임 업데이트 수정 및 최적화 설명", "start_time": "2026-09-23 07:00:00", "end_time": "2026-11-04 06:00:00"},
            {"ann_id": 3, "title": "오래된 기원: 누군가 확률 UP!", "start_time": "2026-05-01 12:00:00", "end_time": "2026-05-20 17:59:00"},
            {"ann_id": 5, "title": "「신의 주조」 기원: 「한손검·나비의 우화」 확률 UP!", "start_time": "2026-09-21 12:00:00", "end_time": "2026-10-13 17:59:00"},
            {"ann_id": 6, "title": "「검에 서린 설원의 여정」 이벤트: 원하는 「세상 여행」 일반 기원의 ★5", "start_time": "2026-09-21 12:00:00", "end_time": "2026-10-13 17:59:00"},
        ]}],
        # 그림 공지(pic_list)에 들어 있는 경우도 찾아야 한다
        "pic_list": [{"type_list": [{"list": [
            {"ann_id": 4, "title": "「죽음의 진혼곡」 7.1 버전 업데이트 안내", "start_time": "2026-09-23 07:00:00", "end_time": "2026-11-04 06:00:00"},
        ]}]}],
    }}
    ann_content = {"retcode": 0, "data": {
        "list": [{"ann_id": 1, "title": "x", "content": "<p>〈기원 기간〉</p><p>7.1 버전 업데이트 후 ~ 2026/10/13 17:59</p><p>5성 캐릭터 베스나</p>"},
                 {"ann_id": 2, "content": "<p>수정</p>"}],
        "pic_list": [{"ann_id": 4, "content": "<p>업데이트 일정: 2026/09/23 06:00 ~ 11:00</p>"}],
    }}
    items = official.parse_hoyo("genshin", ann_list, ann_content, NOW)
    titles = [i.title for i in items]
    # 무기 기원(신의 주조)·이벤트 공지·수정 공지·오래된 공지는 빠진다
    assert titles == ["「봄바람의 춤」 기원: 「눈꽃 연회의 검·베스나(바람)」 확률 UP!", "「죽음의 진혼곡」 7.1 버전 업데이트 안내"]
    wish = items[0]
    assert wish.source == "official"
    assert "베스나" in wish.body and "UTC+8" in wish.body  # 시간대 안내가 붙는다
    assert wish.url.startswith("https://genshin.hoyoverse.com/ko/news?ann=1#v=")
    assert wish.published_at == datetime(2026, 9, 21, 13, 0, tzinfo=KST)  # 서버 12시 = 한국 13시


def test_hoyo_url_changes_when_notice_is_edited():
    base = {"retcode": 0, "data": {"timezone": 8, "list": [{"list": [
        {"ann_id": 1, "title": "「X」 기원: Y 확률 UP!", "start_time": "2026-09-21 12:00:00", "end_time": "2026-10-13 17:59:00"}]}]}}
    a = official.parse_hoyo("genshin", base, {"data": {"list": [{"ann_id": 1, "content": "A"}]}}, NOW)
    b = official.parse_hoyo("genshin", base, {"data": {"list": [{"ann_id": 1, "content": "B"}]}}, NOW)
    assert a[0].url != b[0].url


def test_wuwa_pick_and_parse():
    menu = [
        {"articleId": 4888, "articleTitle": "[내일에 인화될 기억] 캐릭터 이벤트 튜닝", "startTime": "2026-09-12 11:00:00"},
        {"articleId": 4896, "articleTitle": "[프리즈 프레임] 무기 이벤트 튜닝", "startTime": "2026-09-12 11:05:00"},
        {"articleId": 763, "articleTitle": "튜닝 상세정보", "startTime": "2024-05-23 10:00:00"},
        {"articleId": 5357, "articleTitle": "3.6 버전 업데이트 안내", "startTime": "2026-08-20 10:00:00"},
        {"articleId": 1, "articleTitle": "아주 옛날 버전 업데이트", "startTime": "2025-01-01 10:00:00"},
    ]
    picked = official.pick_wuwa(menu, NOW, 8)
    assert [m["articleId"] for m in picked] == [4888, 5357]  # 무기 튜닝·상세정보·오래된 글 제외, 최신순
    item = official.parse_wuwa_article(picked[0], {"articleContent": "<p>기간: 9월 12일 ~ 10월 2일</p>"}, NOW)
    assert item.url.startswith("https://wutheringwaves.kurogames.com/kr/main/news/detail/4888#v=")
    assert "10월 2일" in item.body


def test_blue_archive_pick_and_parse():
    listing = {"threads": [
        {"threadId": 3542433, "title": "9/29(화) 업데이트 정기점검 예정 안내", "createDate": 1790326800},
        {"threadId": 3536012, "title": "(완료) 9/15(화) 업데이트 상세 안내 (9/15 추가)", "createDate": 1789376400},
        {"threadId": 3528726, "title": "8/20(목) 무중단 패치 안내", "createDate": 1787204400},
    ]}
    picked = official.pick_blue_archive(listing, NOW, 5)
    assert [p["threadId"] for p in picked] == [3536012]
    thread = {"threadId": 3536012, "title": "x", "content": "<p>픽업 모집 기간: 9월 15일(화) 점검 후 ~ 9월 29일(화) 오전 10시 59분</p><p>무츠키(드레스)</p>"}
    item = official.parse_blue_archive_thread(picked[0], thread, NOW)
    assert "무츠키" in item.body and "한국 시간" in item.body
    assert item.url.startswith("https://forum.nexon.com/bluearchive/board_view?board=1076&thread=3536012#v=")


def test_nte_list_page():
    html = """
    <ul>
      <li><a href="/kr/article/news/gamebroad/20260921/264254.html">2026년 9월 21일 위반 계정 제재 공지</a></li>
      <li><a href="https://nte.perfectworld.com/kr/article/news/gamenews/20260914/264138.html">1.4 버전 업데이트 안내</a></li>
      <li><a href="/kr/index.html">홈</a></li>
    </ul>"""
    rows = official.parse_list_page("nte", html, "https://nte.perfectworld.com/kr/article/news/index.html")
    assert [r["title"] for r in rows] == ["2026년 9월 21일 위반 계정 제재 공지", "1.4 버전 업데이트 안내"]
    assert rows[1]["date"] == datetime(2026, 9, 14, tzinfo=KST)
    wanted = [r for r in rows if official._wanted(r["title"], official.HTML_SITES["nte"]["keywords"], official.HTML_SITES["nte"]["exclude"])]
    assert [r["title"] for r in wanted] == ["1.4 버전 업데이트 안내"]


def test_hsr_filter_skips_noise():
    titles = ["4.6 버전 이벤트 워프 (1)", "4.6 버전 「달 뜨기 전, 괴수와 춤을」 버전 업데이트 안내", "4.6 버전 업데이트 점검 예고",
              "4.6 버전 게임 최적화 및 발견한 문제 안내", "4.6 버전 상점 신상 출시", "4.6 버전 신규 스테이지",
              "「은하 워프 프로젝트」 가입 초대", "「은하열차 공략 가이드」 웹 페이지 업데이트"]
    cfg = official.HOYO["hsr"]
    kept = [t for t in titles if official._wanted(t, cfg["keywords"], official.HOYO_EXCLUDE + cfg["exclude"])]
    assert kept == titles[:3]


def test_endfield_bulletin():
    resp = {"code": 0, "msg": "", "data": {"list": [
        {"cid": "a1", "tab": "updates", "title": "「찬란한 색채」 재구축 헤드헌팅#1 및 「점묘 신청」 재구축 신청#1 개방",
         "header": "", "startAt": 1790380800, "displayType": "rich_text",
         "data": {"html": "<p>개방 시간: 2026/09/24 12:00(서버 시간) ~ 버전 업데이트 점검 전</p><p>6성 오퍼레이터 [이본]</p>", "linkType": 0}},
        {"cid": "a2", "tab": "updates", "title": "확률 상세 안내", "startAt": 1774238400,
         "data": {"html": "<p>확률</p>"}},
        {"cid": "a3", "tab": "events", "title": "그림 공지 헤드헌팅", "startAt": 1790380800,
         "data": {"url": "https://x/img.png", "link": "", "linkType": 0}},
    ]}}
    items = official.parse_endfield(resp, NOW, 8)
    assert [i.title for i in items] == ["「찬란한 색채」 재구축 헤드헌팅#1 및 「점묘 신청」 재구축 신청#1 개방"]
    assert "이본" in items[0].body and "UTC+8" in items[0].body
    assert items[0].url.startswith("https://endfield.gryphline.com/ko-kr/news?cid=a1#v=")


def test_endfield_bulletin_error_code():
    import pytest
    with pytest.raises(RuntimeError):
        official.parse_endfield({"code": 10001, "msg": "bad"}, NOW, 8)


def test_nte_link_only_in_script():
    html = """<script>var list=[{"url":"https://nte.perfectworld.com/kr/article/news/gamenews/20260929/264413.html"}]</script>"""
    rows = official.parse_list_page("nte", html, "https://nte.perfectworld.com/kr/article/news/index.html")
    assert rows and rows[0]["url"].endswith("/20260929/264413.html") and rows[0]["title"] == ""
    assert rows[0]["date"] == datetime(2026, 9, 29, tzinfo=KST)


def test_games_without_official_source():
    assert official.has_official("genshin") and official.has_official("bluearchive") and official.has_official("endfield")
    assert not official.has_official("nikke") and not official.has_official("arknights")
    assert official.fetch_official("nikke") == []
