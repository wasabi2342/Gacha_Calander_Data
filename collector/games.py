"""수집 대상 게임 목록.

- name: 앱에 표시할 짧은 이름
- full_name: 모델에게 알려줄 정식 이름
- search_terms: 네이버 뉴스 검색어 (뒤에 "업데이트", "픽업"이 붙음)
- match_words: 기사 제목에 이 중 하나가 있어야 분석 (공백 무시)
"""

GAMES = [
    {"id": "genshin", "name": "원신", "full_name": "원신", "color": "#D4A017",
     "search_terms": ["원신"], "match_words": ["원신"]},
    {"id": "hsr", "name": "스타레일", "full_name": "붕괴: 스타레일", "color": "#6B5BD6",
     "search_terms": ["스타레일"], "match_words": ["스타레일"]},
    {"id": "wuwa", "name": "명조", "full_name": "명조: 워더링 웨이브", "color": "#1F9E89",
     "search_terms": ["명조"], "match_words": ["명조", "워더링"]},
    {"id": "nte", "name": "이환", "full_name": "이환 (Neverness to Everness)", "color": "#E0457B",
     "search_terms": ["이환 NTE", "이환 픽업"], "match_words": ["이환", "NTE"]},
    {"id": "zzz", "name": "젠존제", "full_name": "젠레스 존 제로", "color": "#E8772E",
     "search_terms": ["젠레스 존 제로"], "match_words": ["젠레스", "젠존제"]},
    {"id": "bluearchive", "name": "블루 아카이브", "full_name": "블루 아카이브", "color": "#2D8CF0",
     "search_terms": ["블루 아카이브"], "match_words": ["블루아카이브", "블루아카"]},
    {"id": "arknights", "name": "명일방주", "full_name": "명일방주 (엔드필드 아님)", "color": "#5C6670",
     "search_terms": ["명일방주"], "match_words": ["명일방주"]},
    {"id": "endfield", "name": "엔드필드", "full_name": "명일방주: 엔드필드", "color": "#9AAE2F",
     "search_terms": ["엔드필드"], "match_words": ["엔드필드"]},
    {"id": "nikke", "name": "니케", "full_name": "승리의 여신: 니케", "color": "#C23B3B",
     "search_terms": ["니케"], "match_words": ["니케"]},
]

GAMES_BY_ID = {g["id"]: g for g in GAMES}


def is_relevant(game: dict, title: str) -> bool:
    t = (title or "").replace(" ", "")
    return any(w.replace(" ", "") in t for w in game["match_words"])
