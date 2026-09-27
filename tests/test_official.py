"""공식 공지 파서 테스트 (네트워크 없이, 실제 응답과 같은 모양의 샘플로)"""
from datetime import datetime, timedelta, timezone

import official

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 28, 3, 0, tzinfo=KST)


def test_hoyo_list_and_content_are_joined_and_filtered():
    ann_list = {"retcode": 0, "data": {
        "timezone": 8,
        "list": [{"type_label": "게임", "list": [
            {"ann_id": 1, "title": "「봄바람의 춤」 기원", "subtitle": "", "start_time": "2026-09-21 12:00:00", "end_time": "2026-10-13 17:59:00"},
            {"ann_id": 2, "title": "게임 업데이트 수정 및 최적화 설명", "start_time": "2026-09-23 07:00:00", "end_time": "2026-11-04 06:00:00"},
            {"ann_id": 3, "title": "오래된 기원", "start_time": "2026-05-01 12:00:00", "end_time": "2026-05-20 17:59:00"},
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
    assert titles == ["「봄바람의 춤」 기원", "「죽음의 진혼곡」 7.1 버전 업데이트 안내"]
    wish = items[0]
    assert wish.source == "official"
    assert "베스나" in wish.body and "UTC+8" in wish.body  # 시간대 안내가 붙는다
    assert wish.url.startswith("https://genshin.hoyoverse.com/ko/news?ann=1#v=")
    assert wish.published_at == datetime(2026, 9, 21, 13, 0, tzinfo=KST)  # 서버 12시 = 한국 13시


def test_hoyo_url_changes_when_notice_is_edited():
    base = {"retcode": 0, "data": {"timezone": 8, "list": [{"list": [
        {"ann_id": 1, "title": "기원", "start_time": "2026-09-21 12:00:00", "end_time": "2026-10-13 17:59:00"}]}]}}
    a = official.parse_hoyo("hsr" if False else "genshin", base, {"data": {"list": [{"ann_id": 1, "content": "A"}]}}, NOW)
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


def test_endfield_list_page_takes_date_from_text():
    html = """<a href="/ko-kr/news/0801"><span>2026.09.23</span> "찬란한 색채" 재구축 헤드헌팅#1 개방</a>
              <a href="/ko-kr/news/0790">2026.09.22 게임 도구 업데이트</a>"""
    rows = official.parse_list_page("endfield", html, "https://endfield.gryphline.com/ko-kr/news")
    assert rows[0]["url"] == "https://endfield.gryphline.com/ko-kr/news/0801"
    assert rows[0]["date"] == datetime(2026, 9, 23, tzinfo=KST)
    assert "헤드헌팅" in rows[0]["title"]


def test_games_without_official_source():
    assert official.has_official("genshin") and official.has_official("bluearchive")
    assert not official.has_official("nikke") and not official.has_official("arknights")
    assert official.fetch_official("nikke") == []
