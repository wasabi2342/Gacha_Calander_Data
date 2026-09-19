# gacha-calendar-data

픽업 달력 앱이 읽는 게임 일정 데이터 저장소. GitHub Actions가 6시간마다 뉴스를 검색해서 `data/events.json`을 갱신한다.

```
[Actions, 6시간마다] 네이버 뉴스 검색 → 기사 본문 → Claude로 일정 추출 → 병합 → data/ 커밋
[앱] https://raw.githubusercontent.com/<계정>/gacha-calendar-data/main/data/events.json 읽기
```

## 파일

| 경로 | 내용 |
|---|---|
| `data/events.json` | 앱이 읽는 파일. 게임 목록 + 일정 |
| `data/seen_articles.json` | 이미 분석한 기사 URL (같은 기사를 다시 Claude에 보내지 않기 위함, 120일 보관) |
| `collector/collect.py` | 실행 진입점 |
| `collector/games.py` | 게임 목록, 검색어, 색상 |
| `collector/sources.py` | 네이버 뉴스 검색, 본문 추출 |
| `collector/extractor.py` | Claude 프롬프트와 호출 |
| `collector/merge.py` | 병합 규칙 (공식 > 추정 > 유출) |

## 처음 설정

1. **이 폴더를 공개(Public) 저장소로 올린다.** 앱이 로그인 없이 파일을 읽으려면 공개여야 해요. 앱 코드 저장소는 비공개여도 됩니다.
2. 저장소 **Settings → Secrets and variables → Actions → Secrets** 에 추가
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (developers.naver.com, 검색 API)
   - `ANTHROPIC_API_KEY` (console.anthropic.com)
3. (선택) 같은 화면 **Variables** 에 `ANTHROPIC_MODEL` 을 넣으면 모델을 바꿀 수 있어요. 비워두면 Haiku.
4. **Actions 탭 → 일정 수집 → Run workflow** 로 한 번 수동 실행. `game`에 `genshin` 을 넣어 한 게임만 먼저 테스트하는 걸 추천해요.
5. 실행 결과 페이지 아래 Summary에 추가·갱신된 일정 표가 나와요. 바뀐 게 있으면 `data:` 로 시작하는 커밋이 생깁니다.

## 로컬에서 테스트 (Windows PowerShell)

```powershell
pip install -r collector/requirements.txt
$env:NAVER_CLIENT_ID="..."; $env:NAVER_CLIENT_SECRET="..."; $env:ANTHROPIC_API_KEY="..."
python collector/collect.py --game genshin --dry-run   # 저장 없이 추출 결과만 출력
```

## 비용과 한도

- 1회 실행에 게임당 새 기사 최대 6개만 Claude로 보내요 (`MAX_NEW_ARTICLES_PER_GAME`). 이미 본 기사는 건너뛰어서 보통은 이보다 훨씬 적어요.
- 공개 저장소의 Actions 실행 시간은 무료예요.
- 공개 저장소는 60일 동안 활동이 없으면 예약 실행이 자동으로 꺼질 수 있어요. 꺼지면 Actions 탭에서 다시 켜면 됩니다.

## 추출이 틀렸을 때

`data/events.json` 을 직접 고쳐서 커밋하면 돼요. 고친 일정의 `status` 를 `"OFFICIAL"` 로 두면 이후 추정·유출 기사로는 덮어써지지 않아요. 각 일정의 `evidence`, `sourceUrl` 로 어떤 기사에서 왔는지 확인할 수 있어요.
