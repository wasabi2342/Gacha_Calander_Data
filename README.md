# gacha-calendar-data

픽업 달력 앱이 읽는 게임 일정 데이터 저장소. GitHub Actions가 6시간마다 뉴스를 검색해서 `data/events.json`을 갱신한다.

```
[Actions, 6시간마다] 네이버 뉴스 검색 → 기사 본문 → GitHub Models로 일정 추출 → 병합 → data/ 커밋
[앱] https://raw.githubusercontent.com/<계정>/gacha-calendar-data/main/data/events.json 읽기
```

## 파일

| 경로 | 내용 |
|---|---|
| `data/events.json` | 앱이 읽는 파일. 게임 목록 + 일정 |
| `data/seen_articles.json` | 이미 분석한 기사 URL (같은 기사를 다시 모델에 보내지 않기 위함, 120일 보관) |
| `collector/collect.py` | 실행 진입점 |
| `collector/games.py` | 게임 목록, 검색어, 색상 |
| `collector/sources.py` | 네이버 뉴스 검색, 본문 추출 |
| `collector/extractor.py` | 추출 프롬프트와 GitHub Models 호출 |
| `collector/merge.py` | 병합 규칙 (공식 > 추정 > 유출) |

## 처음 설정

1. **이 폴더를 개인 계정의 공개(Public) 저장소로 올린다.** 앱이 로그인 없이 파일을 읽으려면 공개여야 하고, GitHub Models 무료 호출은 조직(Organization) 저장소에서 막히는 경우가 있어서 개인 계정에 두는 게 안전해요.
2. 저장소 **Settings → Secrets and variables → Actions → Secrets** 에 추가
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (네이버 클라우드 플랫폼 콘솔 → NAVER API HUB → Application → 인증 정보)
   - AI 모델 키는 필요 없어요. 워크플로가 Actions 기본 토큰(`GITHUB_TOKEN`)으로 GitHub Models를 호출해요.
3. (선택) 같은 화면 **Variables** 에 `MODEL` 을 넣으면 모델을 바꿀 수 있어요 (예: `openai/gpt-4.1`). 비워두면 `openai/gpt-4.1-mini`.
4. **Actions 탭 → 일정 수집 → Run workflow** 로 한 번 수동 실행. `game`에 `genshin` 을 넣어 한 게임만 먼저 테스트하는 걸 추천해요.
5. 실행 결과 페이지 아래 Summary에 추가·갱신된 일정 표가 나와요. 바뀐 게 있으면 `data:` 로 시작하는 커밋이 생깁니다.

## 로컬에서 테스트 (Windows PowerShell)

```powershell
pip install -r collector/requirements.txt
# GITHUB_TOKEN: github.com/settings/personal-access-tokens 에서 Fine-grained 토큰 생성 → Permissions에서 Models: Read-only
$env:NAVER_CLIENT_ID="..."; $env:NAVER_CLIENT_SECRET="..."; $env:GITHUB_TOKEN="github_pat_..."
python collector/collect.py --game genshin --dry-run   # 저장 없이 추출 결과만 출력
```

## 비용과 한도

- 1회 실행에 게임당 새 기사 최대 6개만 모델로 보내요 (`MAX_NEW_ARTICLES_PER_GAME`). 이미 본 기사는 건너뛰어서 보통은 이보다 훨씬 적어요.
- GitHub Models는 무료 대신 하루·분당 호출 한도가 있어요. 호출 사이에 4초씩 쉬고, 한도(429)에 걸리면 그 실행은 멈추고 남은 기사는 다음 실행에서 이어서 분석해요. 실행 결과 Summary에 ⚠️ 표시가 나와요.
- 공개 저장소의 Actions 실행 시간은 무료예요.
- 공개 저장소는 60일 동안 활동이 없으면 예약 실행이 자동으로 꺼질 수 있어요. 꺼지면 Actions 탭에서 다시 켜면 됩니다.

## 추출이 틀렸을 때

`data/events.json` 을 직접 고쳐서 커밋하면 돼요. 고친 일정의 `status` 를 `"OFFICIAL"` 로 두면 이후 추정·유출 기사로는 덮어써지지 않아요. 각 일정의 `evidence`, `sourceUrl` 로 어떤 기사에서 왔는지 확인할 수 있어요.
