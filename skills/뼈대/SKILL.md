---
name: 뼈대
description: 웹 서비스(데이터셋 적용 → 계산 → 결재·공개 → 역할별 조회)를 만들 때 쓴다. `$파악` 직후 다른 터미널에서 '환경 모드'로 깔아 두거나(요건 질문과 동시에), `$계획서` 커밋 직후 한 번. 서버·DB·로그인·화면·검사 틀을 깔고, 받은 자료에 맞게 채울 곳만 채운다.
---

# 뼈대

> 매번 처음부터 짜던 서버·저장·로그인·화면을 미리 맞게 짜 둔 틀이다. 시간은 계산과 규칙(planner·verify)에 쓴다.

## 깔기
`bash .agents/skills/뼈대/scripts/scaffold.sh .` (없으면 `~/.agents/skills/뼈대/scripts/scaffold.sh .`). 있는 파일은 덮지 않는다.
요청 문서가 정한 파일 이름·실행 방법·포트가 틀과 다르면 요청 문서를 따른다.

## 환경 모드 (`$파악` 직후, 요건 질문과 동시에 — 다른 터미널)
요청자 답을 기다리는 동안 요건과 상관없는 바닥만 깐다. AGENTS '목표'·PLAN 이 비어 있어도 진행한다(그 예외가 이 모드다). 그냥 `$뼈대` 로 불렸는데 PLAN 이 없으면 멈추지 말고 '환경 모드로 할까요?' 한 줄로 묻는다. README 의 배포·실행·제출 요구(파일 이름·포트·Dockerfile·HOW_TO_RUN)와 `$파악` 결과만 본다.
- 한다: 깔기 → 아래 1(`app/spec.py` 의 CSV 열·형식·key·refs. PARAMS 는 README·자료에 적힌 값만) → 2(9x 오류 데이터셋) → `PORT=… python3 -m app.server` 를 0.0.0.0 으로 띄워 `/health`·운영자 로그인·데이터셋 검사·적용 → `docker build` 가 되면 한 번(안 되면 이유 한 줄)
- 안 한다(요청자 답에 달림): `TRANSITIONS`·`NEEDS`(결재 여부·받을 입력), PARAMS 기본값을 짐작으로, `app/planner.py`·`checks/verify.py`. 짐작이 필요하면 멈추고 사용자에게 한 줄로
- 끝 조건: check 행 수 = `wc -l` − 1, 9x 적용 거절, `/health` ok, 로그인. smoke 전체는 아직(계산이 예시라 실패해도 된다 — 어느 줄이 실패하는지만 적는다)
- 고치는 파일은 틀이 만든 것과 `data/datasets/` 뿐. `NOTES.md`·`PLAN.md`·`AGENTS.md`·`view/` 는 다른 터미널 몫이라 읽기만. 커밋은 `git add` 로 자기 파일만, 머리 `[환경]` (`index.lock` 오류면 잠시 뒤 다시)
- 끝나면 터미널에: 한 것 · 확인 명령과 출력 · 띄운 서버 PID·포트 · 요청자 답이 필요한 빈칸 목록. `$계획서` 커밋 뒤 아래 3번부터 이어 간다

## 채울 곳 (이 순서로, 하나 끝날 때마다 확인 명령)
1. `app/spec.py` — `$파악` 결과로 CSV 전부의 열·형식·key·refs, 운영자가 바꿀 조건(PARAMS), 두 번째 역할 표(MEMBER), 표 사이 검사(extra_checks).
   확인: `python3 -m app.cli check data/provided` 의 행 수 = `wc -l` − 1 (표마다)
2. `python3 checks/break_data.py` → `data/datasets/9x-오류-*`. 내용이 바뀐 정상 데이터셋은 손으로 하나 이상(`01-…`, 상태 열은 두 방향 다).
   확인: 화면 또는 smoke 에서 9x 모두 적용 거절
3. `app/planner.py` — 예시 계산을 지우고 `generate(data, params)` 를 쓴다. 돌려줄 모양(머리 주석)은 바꾸지 않는다. 규칙마다 `# 규칙 N`, 빠지는 대상은 `issues`. 묶는 날짜와 시작 날짜가 다른 항목(자정 뒤 새벽)은 `day` 를 넣는다. EXPORT_SCHEMA 머리 칸(계획 번호·데이터셋·시각)은 `finish_export` 에서.
   확인: `python3 -m app.cli export data/provided --out out/export.json` 의 요약 숫자
4. `checks/verify.py` — 예시 규칙을 지우고 요청 문서·확정된 규칙을 하나씩. `app/` 를 import 하지 않는다.
   확인: `python3 checks/verify.py out/export.json data/provided` 가 위반 0 이고, 결과를 일부러 한 건 망가뜨린 사본에서 1 이상
5. `checks/smoke.py` 머리의 `MEMBER_ID`·`PARAM_CHANGE`·`NIGHT`, `app/store.py` 의 `TRANSITIONS`(결재 없으면 publish 하나)와 `NEEDS`(결재 사유·바깥 확인처럼 요청자가 정한 입력. 예시 줄은 지운다), 화면 문구(`static/index.html` 제목, 두 번째 역할 이름).
   확인: `python3 checks/smoke.py` → 합계 통과 N / N
6. `HOW_TO_RUN.md` 의 `(채움)` 을 전부. 확인: `grep -c '(채움)' HOW_TO_RUN.md` → 0

1~2를 한 커밋(`뼈대: 자료 모양 — 확인: …`), 3은 PLAN 의 계산 단계(`$구현`), 4~6은 각자 단계에서.

## 고치지 않는 곳 (고쳐야 하면 먼저 사용자에게 말한다)
`app/store.py`·`dataset.py`·`clock.py`·`server.py` 의 흐름. store.py 머리의 A~I 가 지키는 것:
요청마다 새 연결 · 쓰기는 `BEGIN IMMEDIATE` 한 번에 하나 · 상태 바꾸기 전 검사와 저장이 한 트랜잭션 · 활성 데이터셋은 id 와 내용을 한 번에 · 조건은 데이터셋 버전마다 · 계획은 스냅숏(공개 화면은 스냅숏만) · 이전 데이터셋 계획은 결재·공개 409 · 계산 중 데이터셋이 바뀌면 저장 안 함 · 모든 상태 변화는 events.
시각은 `clock.now()` 만(현지 `APP_UTC_OFFSET`, 자정 넘는 항목은 시작한 날). 새 API 를 더할 때도 쓰기는 `store.tx()` 안에서 검사 → 저장하고, `app/apidoc.py` 의 ROUTES 에 한 줄 더한다(`/docs` Swagger UI · `/openapi.json`, smoke 가 어긋남을 잡는다).

## 서술형·보고에 쓸 때
- 모듈·상태 순서: dataset.parse → store.apply_dataset → planner.generate → store.save_plan → store.transition → store.published. 줄 번호는 `grep -n 'def ' app/store.py` 로 새로 찍는다
- 동시성·오류·취소의 근거는 smoke 의 해당 줄 출력(동시 결재 8번 → 성공 1, 이전 데이터셋 409, 재시작 뒤 유지)
- 틀이 해 준 것과 내가 정한 것을 나눠 쓴다. 틀의 보장도 이번 자료로 smoke 를 돌려 본 것만 '확인함'
