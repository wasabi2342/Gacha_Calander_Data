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
4. type: 새 버전 업데이트 자체는 "VERSION_UPDATE", 캐릭터 픽업 기간은 "BANNER".
5. phase: 전반부 1, 후반부 2, 알 수 없으면 null. VERSION_UPDATE는 항상 null.
6. characters: 픽업 캐릭터만. 신규면 isNew true, 복각이면 false. 등급을 모르면 rarity null. 무기·광추 픽업은 넣지 않는다.
7. status: 공식 발표나 공식 공지를 인용한 내용은 "OFFICIAL", '예정', '전망', '~경' 같은 추정은 "ESTIMATED", 유출·리크·데이터마이닝은 "LEAK".
8. 날짜는 "YYYY-MM-DD", 시각은 한국 시간 "HH:mm". 모르면 null.
9. title: "7.1 전반 픽업", "3.7 「부제」"처럼 짧게.
10. evidence: 근거가 된 기사 내용을 30자 이내로 요약한다.
11. 일정이 없으면 []. JSON 배열만 출력하고 다른 텍스트는 쓰지 않는다.

출력 예시
[{"type":"BANNER","version":"7.1","phase":1,"title":"7.1 전반 픽업","characters":[{"name":"베스나","rarity":5,"isNew":true}],"startDate":"2026-09-23","startTime":null,"endDate":"2026-10-13","endTime":"18:59","status":"OFFICIAL","evidence":"7.1 전반부 베스나 픽업"}]"""


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
            published_at: datetime) -> list[dict]:
    user = (f"게임: {game_full_name}\n"
            f"기사 발행 시각(KST): {_fmt_pub(published_at)}\n"
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
