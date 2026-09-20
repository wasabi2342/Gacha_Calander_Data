"""추출 단계: 기사 본문 → 일정 JSON (Gemini 또는 Anthropic)"""
import json
import logging
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
WEEKDAYS = "월화수목금토일"

SYSTEM_PROMPT = """너는 서브컬처 게임 뉴스에서 '버전 업데이트'와 '캐릭터 픽업(배너)' 일정만 뽑아 JSON으로 정리하는 추출기야.

규칙
1. 기사에 적힌 일정만 추출한다. 날짜를 추측해서 만들지 않는다.
2. "오는 23일", "다음 주 수요일" 같은 상대 날짜는 기사 발행 시각을 기준으로 절대 날짜로 바꾼다.
3. 요청한 게임의 일정만 추출한다. 같은 기사에 나온 다른 게임 일정은 무시한다.
4. type: 새 버전 업데이트 자체는 "VERSION_UPDATE", 캐릭터 픽업(모집, 가챠, 헤드헌팅, 워프, 기원 등) 기간은 "BANNER".
5. version: 기사에 나온 버전 번호(예: "7.1"). 니케, 블루 아카이브, 명일방주처럼 버전 번호를 쓰지 않는 게임이거나 기사에 버전 번호가 없으면, 픽업이 시작하는 날짜를 "YYYY-MM-DD"로 넣는다. 이런 경우에는 VERSION_UPDATE는 만들지 말고 픽업(BANNER)만 추출한다.
6. phase: 버전 번호가 있을 때만 전반부 1, 후반부 2. 알 수 없거나 version이 날짜면 null. VERSION_UPDATE는 항상 null.
7. 기사에 그 픽업의 시작일이 적혀 있지 않으면 startDate는 null로 둔다. 기사 발행일이나 버전 업데이트 날짜를 후반부 픽업 시작일로 넣지 않는다.
   픽업 시작일은 업데이트 점검이 끝나는 날(업데이트 당일)이다. "점검 이후", "업데이트 후부터"라고 하면 점검 날짜를 시작일로 쓴다. 기사 발행일이나 "추가됐다"고 보도한 날을 시작일로 쓰지 않는다.
8. 같은 날 시작하는 픽업 캐릭터는 하나의 BANNER에 모두 넣는다. 시작일이 다른 픽업은 BANNER를 나눈다 (예: 17일 A 픽업, 24일 B 픽업 → BANNER 2개).
9. 여러 기존 캐릭터 중 하나를 고르는 "선택 모집", "복각 선택", "셀렉트" 류는 추출하지 않는다.
10. characters: 픽업 캐릭터만. 신규면 isNew true, 복각이면 false. 등급을 모르면 rarity null. 무기·광추·코스튬(스킨)만 있는 픽업은 넣지 않는다.
11. status: 공식 발표나 공식 공지를 인용한 내용은 "OFFICIAL", '예정', '전망', '~경' 같은 추정은 "ESTIMATED", 유출·리크·데이터마이닝은 "LEAK".
12. 날짜는 "YYYY-MM-DD", 시각은 한국 시간 "HH:mm". 모르면 null.
13. title: "7.1 전반 픽업", "3.7 「부제」"처럼 짧게.
14. evidence: 근거가 된 기사 내용을 30자 이내로 요약한다.
15. 일정이 없으면 []. JSON 배열만 출력하고 다른 텍스트는 쓰지 않는다.

출력 예시
[{"type":"BANNER","version":"7.1","phase":1,"title":"7.1 전반 픽업","characters":[{"name":"베스나","rarity":5,"isNew":true}],"startDate":"2026-09-23","startTime":null,"endDate":"2026-10-13","endTime":"18:59","status":"OFFICIAL","evidence":"7.1 전반부 베스나 픽업"}]

버전 번호가 없는 게임의 예시
[{"type":"BANNER","version":"2026-09-17","phase":null,"title":"바니걸 신규 니케 모집","characters":[{"name":"캐릭터A","rarity":null,"isNew":true},{"name":"캐릭터B","rarity":null,"isNew":true}],"startDate":"2026-09-17","startTime":null,"endDate":"2026-10-01","endTime":null,"status":"OFFICIAL","evidence":"17일 신규 니케 2종 모집 시작"}]"""


class ExtractError(Exception):
    """API 호출 실패. 호출 쪽에서 기사를 '미처리'로 남겨 다음 실행에 재시도한다."""


class RateLimited(ExtractError):
    """호출 한도 초과. 이번 실행은 여기서 멈추고 다음 실행에 이어서 한다."""


# 기본 모델. 서비스 쪽 모델 이름이 바뀌면 저장소 Variables의 MODEL 로 덮어쓰면 된다
DEFAULT_MODELS = {
    "gemini": "gemini-flash-lite-latest",
    "anthropic": "claude-haiku-4-5-20251001",
}


def _fmt_pub(dt: datetime) -> str:
    k = dt.astimezone(KST)
    return f"{k:%Y-%m-%d} ({WEEKDAYS[k.weekday()]}) {k:%H:%M}"


def _check(res: requests.Response) -> None:
    if res.status_code == 429:
        raise RateLimited(f"429 호출 한도 초과: {res.text[:200]}")
    if res.status_code >= 400:
        raise ExtractError(f"{res.status_code}: {res.text[:300]}")


def _call_gemini(api_key: str, model: str, user: str) -> str:
    """Google Gemini API (AI Studio 키)"""
    res = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 2000,
                                 "responseMimeType": "application/json"},
        },
        timeout=60,
    )
    _check(res)
    candidates = res.json().get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "".join(p.get("text", "") for p in parts)


def _call_anthropic(api_key: str, model: str, user: str) -> str:
    """Anthropic Claude API"""
    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 2000, "temperature": 0, "system": SYSTEM_PROMPT,
              "messages": [{"role": "user", "content": user}]},
        timeout=60,
    )
    _check(res)
    return "".join(b.get("text", "") for b in res.json().get("content", []) if b.get("type") == "text")


PROVIDERS = {"gemini": _call_gemini, "anthropic": _call_anthropic}


def extract(provider: str, api_key: str, model: str, game_full_name: str, title: str, body: str,
            published_at: datetime, source: str = "news") -> list[dict]:
    kind = "개인 블로그 글 (팬이 정리한 글이라 틀릴 수 있음)" if source == "blog" else "뉴스 기사"
    user = (f"게임: {game_full_name}\n"
            f"글 종류: {kind}\n"
            f"작성 시각(KST): {_fmt_pub(published_at)}\n"
            f"기사 제목: {title}\n\n"
            f"기사 본문:\n{body}")
    try:
        text = PROVIDERS[provider](api_key, model, user)
    except requests.RequestException as e:
        raise ExtractError(str(e)) from e
    return parse(text or "")


def parse(raw: str) -> list[dict]:
    s, e = raw.find("["), raw.rfind("]")
    if s < 0 or e <= s:
        return []
    try:
        data = json.loads(raw[s:e + 1])
    except json.JSONDecodeError as ex:
        log.warning("추출 결과 JSON 파싱 실패: %s", ex)
        return []
    return [x for x in data if isinstance(x, dict)]
