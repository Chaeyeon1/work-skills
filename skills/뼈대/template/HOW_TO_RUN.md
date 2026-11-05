# HOW_TO_RUN

<!-- (채움) 표시를 모두 채우고 이 줄을 지운다. 확인하지 않은 문장은 쓰지 않는다. -->

## 1. 목적과 범위

(채움: 누가 무엇을 하려고 쓰는지 한두 문장 — PLAN '다시 정의한 문제')

- 만든 것: 데이터셋 선택·검증·적용, 조건 변경, 계획 생성, 결재·공개, 두 번째 역할의 조회 화면, JSON 내보내기
- 다루지 않은 범위: (채움: 요청 문서의 '다루지 않는 범위' + 이번에 뺀 것과 이유)

## 2. 기술 스택

- Python 3.12 표준 라이브러리만 (`http.server`, `sqlite3`, `csv`). 외부 패키지 없음
- 화면: HTML·CSS·JavaScript 한 장 (`static/`), 그래프는 SVG 로 직접 그림
- 구조: `app/dataset.py`(읽기·검증) → `app/planner.py`(계산, DB·시각을 읽지 않음) → `app/store.py`(SQLite, 데이터셋 버전·계획 상태) → `app/server.py`(API)

## 3. 준비 사항

- Python 3.11 이상 또는 Docker
- 환경변수: `.env.example` 참고. `OPERATOR_PASSWORD`, `MEMBER_INITIAL_PASSWORD` 가 없으면 서버가 시작하지 않는다
- 데이터: `data/provided/`(제공 원본) · `data/datasets/`(준비한 데이터셋. `python3 checks/break_data.py` 로 오류 데이터셋을 다시 만들 수 있다)

## 4. 실행 방법

```bash
set -a; . ./.env.example; set +a        # 또는 .env
python3 -m app.server                     # http://localhost:8000
```

Docker:

```bash
docker build -t plan-service .
docker run --rm -p 8000:8000 -e OPERATOR_PASSWORD=… -e MEMBER_INITIAL_PASSWORD=… -v plan-data:/data plan-service
```

API 문서: `/docs`(Swagger UI, 오프라인이면 표) · `/openapi.json`. 헬스체크: `GET /health` → `{"ok": true, "dataset": true}`. 빈 DB 로 시작하면 스키마를 만들고 `data/provided` 를 첫 데이터셋으로 적용한다.

## 5. 이용 순서와 대표 결과

- 운영자: `operator` / `OPERATOR_PASSWORD`
- 두 번째 역할: (채움: 아이디가 무엇인지, 예 한 개) / `MEMBER_INITIAL_PASSWORD`

1. 운영자 로그인 → 1. 데이터셋에서 고르고 **검사** → 오류면 파일:줄과 이유가 나오고 **적용**해도 바뀌지 않는다
2. **적용** → 맨 위에 적용된 데이터셋(버전·시각)이 바뀌고, 이전 계획은 '이전 데이터셋'으로 표시된다. 조건은 새 데이터의 기본값으로 돌아간다
3. 2. 조건을 바꾸고 저장 → 3. **생성** → 초안. '확인 필요'가 있으면 내용을 보고 체크해야 결재·공개된다
4. **결재** → **공개** → 두 번째 역할 화면에 보인다 (공개 당시 결과를 그대로 보여 준다)
5. **JSON 내보내기** → 서버의 `out/plan-<번호>.json` 에 저장되고 화면에도 보인다. 명령으로: `python3 -m app.cli export data/provided --out out/export.json`

대표 결과: (채움: 제공 데이터 전체 기간 기준 숫자 — 명령과 함께)

계획 기준과 최적화 방식: (채움: 무엇이 더 나은 계획인지, 어떤 순서로 비교하는지, 어떻게 찾는지)

## 6. 테스트

```bash
python3 checks/smoke.py                                  # 빈 DB 부터 흐름 전체 (임시 폴더, 진짜 DB 안 건드림)
python3 -m app.cli export data/provided --out out/export.json
python3 checks/verify.py out/export.json data/provided    # app/ 를 import 하지 않는 독립 검사
```

smoke 가 확인하는 것: 로그인·권한(401/403), 오류 데이터셋 적용 거절과 기존 유지, 확인 필요가 있는 계획의 결재 거절,
같은 계획을 동시에 8번 결재하면 1번만 성공, 적용 전에 만든 계획의 결재 거절, 공개 화면이 공개 당시 결과를 유지,
새 데이터셋에 조건이 넘어가지 않음, 재시작 뒤 유지, 자정을 넘는 항목의 날짜, 서버 시계가 UTC 일 때의 현지 시각.

## 7. 가정과 제한 사항

- (채움: 요청자에게 확인하지 못하고 정한 것 — NOTES '결정' 에서)
- 한 서버·한 SQLite 파일 기준. 쓰기는 `BEGIN IMMEDIATE` 로 한 번에 하나라서 여러 워커여도 같은 DB 파일이면 안전하지만, 여러 서버가 DB 를 나눠 쓰려면 서버형 DB 로 바꿔야 한다
- 계산이 길어지는 동안 데이터셋이 바뀌면 그 결과는 저장하지 않고 다시 생성하라고 알린다
- 비밀번호는 PBKDF2 로 저장, 세션은 DB 에 저장(만료 `SESSION_HOURS`). 비밀번호 변경 화면은 없다
