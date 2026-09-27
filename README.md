# gacha-calendar-data

픽업 달력 앱이 읽는 게임 일정 데이터 저장소. GitHub Actions가 6시간마다 **게임사 공식 공지**와 뉴스를 읽어서 `data/events.json`을 갱신한다.

```
[Actions, 6시간마다] ① 게임사 공식 공지 → ② 네이버 뉴스 → ③ 블로그 → Gemini로 일정 추출 → 병합 → data/ 커밋
[앱] https://raw.githubusercontent.com/<계정>/gacha-calendar-data/main/data/events.json 읽기
```

## 파일

| 경로 | 내용 |
|---|---|
| `data/events.json` | 앱이 읽는 파일. 게임 목록 + 일정 |
| `data/seen_articles.json` | 이미 분석한 기사 URL (같은 기사를 다시 모델에 보내지 않기 위함, 120일 보관) |
| `collector/collect.py` | 실행 진입점 |
| `collector/games.py` | 게임 목록, 검색어, 색상 |
| `collector/official.py` | 게임사 공식 공지 수집 (게임별 출처는 아래 표) |
| `collector/sources.py` | 네이버 뉴스·블로그 검색, 본문 추출 |
| `collector/extractor.py` | 추출 프롬프트와 모델 호출 (Gemini 기본, Anthropic 선택 가능) |
| `collector/merge.py` | 병합 규칙 (공식 > 추정 > 유출) |

## 공식 공지 출처

뉴스 기사는 날짜를 옮겨 적다 틀리거나 루머가 섞이는 일이 많아서, 게임사가 직접 올린 공지를 가장 먼저 읽어요.
공식 공지에서 온 일정은 `"verified": true` 로 저장되고, 뉴스·블로그로는 바뀌지 않아요.

| 게임 | 공식 출처 |
|---|---|
| 원신 / 스타레일 / 젠존제 | 게임 안 공지 (HoYoverse 공지 API, 한국어) |
| 명조 | 공식 사이트 소식 (한국어) |
| 블루 아카이브 | 넥슨 커뮤니티 공지사항 게시판 |
| 엔드필드 | 공식 사이트 소식 (한국어) |
| 이환 | 공식 사이트 소식 (한국어) |
| 니케 / 명일방주 | 아직 없음 → 예전처럼 뉴스·블로그만 사용 |

- 공식 출처가 있는 게임은, 공지로 확인되기 전까지 뉴스에서 온 일정을 `ESTIMATED`(앱에서 "추정")로 저장해요.
  공지가 올라오면 자동으로 `OFFICIAL` + `verified` 로 바뀌어요.
- 공지 내용이 수정되면(본문이 바뀌면) 다시 분석해요.
- 호요버스 게임 공지의 시각은 서버 시간(UTC+8)이라 한국 시간으로 1시간 더해서 저장해요.
- 어떤 출처가 막히면(사이트 구조 변경 등) 그 게임은 뉴스로 계속 수집하고, 실행 결과 Summary의 "공식 공지 첫 오류"에 이유가 나와요.

## 처음 설정

1. **이 폴더를 공개(Public) 저장소로 올린다.** 앱이 로그인 없이 파일을 읽으려면 공개여야 해요.
2. 저장소 **Settings → Secrets and variables → Actions → Secrets** 에 추가
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (네이버 클라우드 플랫폼 콘솔 → NAVER API HUB → Application → 인증 정보). Application에서 **뉴스**와 **블로그** API를 둘 다 선택해야 해요
   - `LLM_API_KEY` (Google AI Studio → Get API key 에서 발급한 Gemini 키)
3. (선택) 같은 화면 **Variables** 탭
   - `MODEL`: 모델 이름을 직접 지정 (비워두면 `gemini-flash-lite-latest`)
   - `USE_BLOG`: `false` 로 두면 블로그 검색을 꺼요 (기본 켜짐)
   - `USE_OFFICIAL`: `false` 로 두면 공식 공지 수집을 꺼요 (기본 켜짐)
   - `NEWS_CAP`: `false` 로 두면 공식 출처가 있는 게임도 뉴스 정보를 `OFFICIAL` 로 저장해요 (기본: `ESTIMATED` 까지만)
   - `LLM_PROVIDER`: `anthropic` 으로 바꾸면 Claude API를 사용. 이때 `LLM_API_KEY` 에는 Anthropic 키를 넣어요 (기본 모델 `claude-haiku-4-5-20251001`)
4. **Actions 탭 → 일정 수집 → Run workflow** 로 한 번 수동 실행. `game`에 `genshin` 을 넣어 한 게임만 먼저 테스트하는 걸 추천해요.
5. 실행 결과 페이지 아래 Summary에 추가·갱신된 일정 표가 나와요. 바뀐 게 있으면 `data:` 로 시작하는 커밋이 생깁니다.

## 수동 실행 옵션 (Actions → 일정 수집 → Run workflow)

| 항목 | 설명 |
|---|---|
| `game` | 게임 id. 비우면 전체. `genshin`, `hsr`, `wuwa`, `nte`, `zzz`, `bluearchive`, `arknights`, `endfield`, `nikke` |
| `reprocess` | 이미 분석한 기사도 다시 분석 (추출 규칙을 고친 뒤에 사용) |
| `reset` | `안 함` / `선택한 게임만` (game 필수) / `전체 게임` (game 비움). 일정을 지우고 최근 기사로 처음부터 다시 수집 |

- 초기화는 최근 기사만 다시 보기 때문에 이미 끝난 오래된 픽업은 다시 안 잡힐 수 있어요.
- 초기화 중 검색이나 추출이 전부 실패하면 저장하지 않아서 기존 일정이 그대로 남아요.

## 병합 규칙 요약

- 블로그는 보조 소스예요. 게임당 최대 3개(초기화 때 6개)만 보고, 블로그에서 나온 정보는 최대 `ESTIMATED` 로만 저장해서 공식 뉴스 정보를 덮어쓰지 못해요.

- 신뢰도는 공식 공지(`OFFICIAL` + `verified`) > `OFFICIAL` > `ESTIMATED` > `LEAK`. 낮은 쪽이 높은 쪽을 덮어쓰지 못해요.
- 공식 공지 날짜는 "버전 업데이트일과 안 맞음" 검사와 자동 보정에서 빠져요 (틀린 쪽은 보통 뉴스에서 온 업데이트일이라서).
- 날짜만 있는 정보끼리는 먼저 저장된 것을 믿고, 시각이 새로 확인되거나 더 믿을 만한 출처일 때만 바꿔요.
- 버전 있는 게임: 전반 픽업은 버전 업데이트일(±2일), 후반 픽업은 업데이트 7일 이후에 시작해야 해요. 어긋나는 날짜는 버리고, 이미 잘못 저장된 날짜는 매 실행마다 자동으로 바로잡아요.
- 버전 없는 게임(니케, 블루 아카이브 등): 픽업만 저장하고, 시작일이 3일 이내이면서 신규 캐릭터가 겹치면 같은 픽업으로 합쳐요. 날짜는 더 이른 날(점검 종료일)을 남겨요.
- 캐릭터 이름은 띄어쓰기·콜론·괄호 표기를 통일해서 비교하고, 기사마다 일부만 언급해도 목록을 합쳐요.

## 테스트

```bash
pip install -r collector/requirements.txt pytest
python -m pytest -q tests      # 네트워크 없이 공식 공지 파서·병합 규칙·수집 흐름 확인
```

## 로컬에서 테스트 (Windows PowerShell)

```powershell
pip install -r collector/requirements.txt
$env:NAVER_CLIENT_ID="..."; $env:NAVER_CLIENT_SECRET="..."; $env:LLM_API_KEY="..."
python collector/collect.py --game genshin --dry-run   # 저장 없이 추출 결과만 출력
python collector/collect.py --game nikke --reset       # 한 게임 초기화 후 다시 수집
python collector/collect.py --reset-all                # 전체 초기화 후 다시 수집
```

## 비용과 한도

- 1회 실행에 게임당 새 기사 최대 6개만 모델로 보내요 (`MAX_NEW_ARTICLES_PER_GAME`). 이미 본 기사는 건너뛰어서 보통은 이보다 훨씬 적어요.
- Gemini 무료 구간은 하루·분당 호출 한도가 있어요. 호출 사이에 6초씩 쉬고, 한도(429)에 걸리거나 추출이 3번 연속 실패하면 그 실행은 멈추고 남은 기사는 다음 실행에서 이어서 분석해요. 실행 결과 Summary에 ⚠️ 표시가 나와요.
- 무료 서비스는 정책이 자주 바뀌어요. 막히면 `LLM_PROVIDER` 와 `LLM_API_KEY` 만 바꿔서 다른 제공자로 옮길 수 있어요.
- 공개 저장소의 Actions 실행 시간은 무료예요.
- 공개 저장소는 60일 동안 활동이 없으면 예약 실행이 자동으로 꺼질 수 있어요. 꺼지면 Actions 탭에서 다시 켜면 됩니다.

## 추출이 틀렸을 때

`data/events.json` 을 직접 고쳐서 커밋하면 돼요. 고친 일정에 `"status": "OFFICIAL"` 과 `"verified": true` 를 넣으면 이후 뉴스·블로그로는 덮어써지지 않아요. 각 일정의 `evidence`, `sourceUrl` 로 어떤 기사에서 왔는지 확인할 수 있어요.
