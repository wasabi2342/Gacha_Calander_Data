"""추출 단계: 기사 본문 → 일정 JSON (GitHub Models)"""
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
    """GitHub Models 호출 한도 초과. 이번 실행은 여기서 멈추고 다음 실행에 이어서 한다."""


# GitHub Models (OpenAI 호환 chat completions). Actions의 GITHUB_TOKEN 으로 인증
MODELS_URL = "https://models.github.ai/inference/chat/completions"


def _fmt_pub(dt: datetime) -> str:
    k = dt.astimezone(KST)
    return f"{k:%Y-%m-%d} ({WEEKDAYS[k.weekday()]}) {k:%H:%M}"


def extract(token: str, model: str, game_full_name: str, title: str, body: str,
            published_at: datetime) -> list[dict]:
    user = (f"게임: {game_full_name}\n"
            f"기사 발행 시각(KST): {_fmt_pub(published_at)}\n"
            f"기사 제목: {title}\n\n"
            f"기사 본문:\n{body}")
    try:
        res = requests.post(
            MODELS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0,
                "max_tokens": 2000,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
    except requests.RequestException as e:
        raise ExtractError(str(e)) from e

    if res.status_code == 429:
        raise RateLimited(f"429 호출 한도 초과: {res.text[:200]}")
    if res.status_code >= 400:
        raise ExtractError(f"{res.status_code}: {res.text[:300]}")

    choices = res.json().get("choices") or []
    text = (choices[0].get("message") or {}).get("content", "") if choices else ""
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
