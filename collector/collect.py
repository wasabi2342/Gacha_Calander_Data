"""6시간마다 GitHub Actions에서 실행되는 수집기.

    python collector/collect.py                 # 전체 게임
    python collector/collect.py --game genshin  # 한 게임만
    python collector/collect.py --game genshin --dry-run   # 파일 저장 없이 추출 결과만 출력

환경 변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, LLM_API_KEY
         (선택) LLM_PROVIDER = gemini(기본) | anthropic, (선택) MODEL
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from extractor import DEFAULT_MODELS, PROVIDERS, ExtractError, RateLimited, extract
from games import GAMES, GAMES_BY_ID, is_relevant
from merge import key_of, merge, prune_old
from sources import fetch_article_text, search_news

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "data" / "events.json"
SEEN_PATH = ROOT / "data" / "seen_articles.json"

QUERY_SUFFIXES = ["업데이트", "픽업"]
ARTICLES_PER_QUERY = 10
MAX_NEW_ARTICLES_PER_GAME = 6   # 1회 실행당 게임별 모델 호출 상한 (무료 한도 보호)
CALL_INTERVAL_SEC = 6           # 분당 호출 한도에 걸리지 않게 호출 사이 대기
MAX_CONSECUTIVE_FAILS = 3       # 추출이 연달아 이만큼 실패하면 설정 문제로 보고 이번 실행을 멈춤
SEEN_KEEP_DAYS = 120

log = logging.getLogger("collect")

# 실행 진단용 집계. 실패해도 경고만 남기면 Actions가 "성공"으로 보여서 원인을 놓치기 쉽다
STATS = {"search_ok": 0, "search_fail": 0, "extract_ok": 0, "extract_fail": 0, "relevant": 0}
FIRST_ERROR: dict[str, str] = {}
CONSECUTIVE_FAILS = [0]


def _record_error(kind: str, msg: str) -> None:
    STATS[kind] += 1
    FIRST_ERROR.setdefault(kind, msg[:300])


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_game(game, events, seen, env, dry_run, report) -> None:
    analyzed = 0
    visited: set[str] = set()
    for term in game["search_terms"]:
        for suffix in QUERY_SUFFIXES:
            try:
                items = search_news(env["naver_id"], env["naver_secret"], f"{term} {suffix}", ARTICLES_PER_QUERY)
            except Exception as e:  # noqa: BLE001 - 한 검색어 실패로 전체를 멈추지 않음
                detail = getattr(getattr(e, "response", None), "text", "") or ""
                log.warning("[%s] 뉴스 검색 실패: %s %s", game["id"], e, detail[:200])
                _record_error("search_fail", f"{e} {detail[:200]}")
                continue
            STATS["search_ok"] += 1

            for item in items:
                if analyzed >= MAX_NEW_ARTICLES_PER_GAME:
                    return
                if item.url in visited or item.url in seen or not is_relevant(game, item.title):
                    continue
                visited.add(item.url)
                STATS["relevant"] += 1

                body = fetch_article_text(item.url) or item.description
                if STATS["extract_ok"] + STATS["extract_fail"] > 0:
                    time.sleep(CALL_INTERVAL_SEC)
                try:
                    extracted = extract(env["provider"], env["api_key"], env["model"], game["full_name"],
                                        item.title, body, item.published_at)
                except RateLimited:
                    raise  # main 에서 이번 실행을 멈춘다
                except ExtractError as e:
                    log.warning("[%s] 추출 실패, 다음에 재시도: %s (%s)", game["id"], item.url, e)
                    _record_error("extract_fail", str(e))
                    CONSECUTIVE_FAILS[0] += 1
                    if CONSECUTIVE_FAILS[0] >= MAX_CONSECUTIVE_FAILS:
                        raise RateLimited(f"추출이 {MAX_CONSECUTIVE_FAILS}번 연속 실패했어요") from e
                    continue
                CONSECUTIVE_FAILS[0] = 0
                analyzed += 1
                STATS["extract_ok"] += 1

                if dry_run:
                    print(f"\n# {item.title}\n{item.url}")
                    print(json.dumps(extracted, ensure_ascii=False, indent=2))
                    continue

                changes = 0
                for x in extracted:
                    result = merge(events, game["id"], x, item.url)
                    if result:
                        changes += 1
                        report.append((game["name"], result, x.get("title") or x.get("version"), item.title))
                seen[item.url] = {
                    "game": game["id"], "title": item.title,
                    "seenAt": datetime.now(KST).isoformat(timespec="seconds"), "changes": changes,
                }
                log.info("[%s] %s → %d건 반영", game["id"], item.title, changes)


def write_summary(report, removed: int, stopped: str | None) -> None:
    """Actions 실행 결과 페이지에 변경 내역 표시"""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = ["## 일정 수집 결과", ""]
    if report:
        lines += ["| 게임 | 결과 | 일정 | 출처 기사 |", "|---|---|---|---|"]
        lines += [f"| {g} | {'추가' if r == 'added' else '갱신'} | {t} | {a} |" for g, r, t, a in report]
    else:
        lines.append("바뀐 일정이 없어요.")
    if removed:
        lines += ["", f"오래된 일정 {removed}건 정리"]
    if stopped:
        lines += ["", f"⚠️ {stopped} 남은 기사는 다음 실행에서 이어서 분석해요."]
    lines += [
        "", "### 진단", "",
        f"- 뉴스 검색: 성공 {STATS['search_ok']} / 실패 {STATS['search_fail']}",
        f"- 새로 찾은 관련 기사: {STATS['relevant']}",
        f"- 모델 추출: 성공 {STATS['extract_ok']} / 실패 {STATS['extract_fail']}",
    ]
    for kind, label in (("search_fail", "검색 첫 오류"), ("extract_fail", "추출 첫 오류")):
        if kind in FIRST_ERROR:
            lines.append(f"- {label}: `{FIRST_ERROR[kind]}`")
    text = "\n".join(lines) + "\n"
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    print(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", help="게임 id (생략하면 전체)")
    parser.add_argument("--dry-run", action="store_true", help="파일 저장 없이 추출 결과만 출력")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    env = {
        "naver_id": os.environ.get("NAVER_CLIENT_ID", ""),
        "naver_secret": os.environ.get("NAVER_CLIENT_SECRET", ""),
        "provider": (os.environ.get("LLM_PROVIDER") or "gemini").strip().lower(),
        "api_key": os.environ.get("LLM_API_KEY", ""),
    }
    if env["provider"] not in PROVIDERS:
        log.error("LLM_PROVIDER 는 %s 중 하나여야 해요 (지금: %s)", " / ".join(PROVIDERS), env["provider"])
        return 1
    env["model"] = os.environ.get("MODEL") or DEFAULT_MODELS[env["provider"]]
    missing = [k for k in ("naver_id", "naver_secret", "api_key") if not env[k]]
    if missing:
        log.error("환경 변수가 비어 있어요: NAVER_CLIENT_ID / NAVER_CLIENT_SECRET / LLM_API_KEY 를 확인하세요.")
        return 1
    log.info("추출 모델: %s / %s", env["provider"], env["model"])

    if args.game and args.game not in GAMES_BY_ID:
        log.error("알 수 없는 게임 id: %s (가능: %s)", args.game, ", ".join(GAMES_BY_ID))
        return 1
    targets = [GAMES_BY_ID[args.game]] if args.game else GAMES

    doc = load_json(EVENTS_PATH, {"events": []})
    events = {key_of(e): e for e in doc.get("events", [])}
    seen = load_json(SEEN_PATH, {})

    report: list = []
    stopped = None
    for game in targets:
        try:
            run_game(game, events, seen, env, args.dry_run, report)
        except RateLimited as e:
            stopped = f"{game['name']}에서 멈췄어요 ({e})."
            log.warning("%s (%s)", stopped, e)
            break

    if args.dry_run:
        return 0

    removed = prune_old(events)
    cutoff = datetime.now(KST) - timedelta(days=SEEN_KEEP_DAYS)
    seen = {u: v for u, v in seen.items() if datetime.fromisoformat(v["seenAt"]) >= cutoff}

    ordered = sorted(events.values(), key=lambda e: (e["startAt"], e["gameId"], e.get("phase") or 0))
    new_doc = {
        "updatedAt": datetime.now(KST).isoformat(timespec="seconds"),
        "games": [{"id": g["id"], "name": g["name"], "color": g["color"]} for g in GAMES],
        "events": ordered,
    }
    # 일정이 안 바뀌었으면 updatedAt 만 바뀌는 커밋을 만들지 않는다
    if report or removed or doc.get("games") != new_doc["games"] or "updatedAt" not in doc:
        save_json(EVENTS_PATH, new_doc)
    save_json(SEEN_PATH, seen)
    write_summary(report, removed, stopped)

    # 전부 실패했으면 실행을 실패(빨간 X)로 표시해서 바로 알아챌 수 있게 한다
    if STATS["search_ok"] == 0 and STATS["search_fail"] > 0:
        log.error("뉴스 검색이 전부 실패했어요. NAVER API HUB 키와 'NAVER 검색' API 선택 여부를 확인하세요.")
        return 1
    if STATS["extract_ok"] == 0 and STATS["extract_fail"] > 0:
        log.error("모델 추출이 전부 실패했어요. LLM_API_KEY, LLM_PROVIDER, MODEL 값을 확인하세요.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
