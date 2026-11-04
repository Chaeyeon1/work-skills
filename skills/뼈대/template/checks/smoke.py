"""처음부터 끝까지 한 번 — 빈 DB 로 서버를 띄워 API 로 흐름을 밟고, 끝나면 PID 로 끈다.

python3 checks/smoke.py            (진짜 DB·out/ 은 건드리지 않는다. 임시 폴더를 쓴다)
줄마다 '통과/실패 — 무엇'. 실패가 하나라도 있으면 종료 코드 1.
받은 자료에 맞게 고칠 곳: MEMBER_ID(공개 계획에 일정이 있는 두 번째 역할 아이디), PARAM_CHANGE, NIGHT(자정을 넘는 항목 한 건).
store.NEEDS 의 입력은 자동으로 채워 보낸다(빈 채로 보내 409 인지도 본다).
"""
import http.cookiejar
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMBER_ID = "U01"
PARAM_CHANGE = {"max_per_place": 1}  # 저장했다가 새 데이터셋에서 기본값으로 돌아가는지 볼 조건 하나 (기본값과 다른 값)
NIGHT = {"date": "2026-01-05", "start": "22:00", "end": "06:00", "at": "2026-01-06T03:00", "expect": "2026-01-05"}
results = []


def ok(cond, what):
    results.append(bool(cond))
    print(("통과" if cond else "실패") + " — " + what, flush=True)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Client:
    def __init__(self, base):
        self.base = base
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
        try:
            with self.op.open(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


def start(env):
    p = subprocess.Popen([sys.executable, "-m", "app.server"], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{env['PORT']}/health", timeout=1) as r:
                if r.status == 200:
                    return p
        except OSError:
            time.sleep(0.1)
    p.kill()
    print(p.stdout.read())
    sys.exit("서버가 뜨지 않음")


def stop(p):
    os.kill(p.pid, signal.SIGTERM)  # 띄운 것만 PID 로
    p.wait(timeout=10)


def main():
    tmp = tempfile.mkdtemp(prefix="smoke-")
    ds = os.path.join(tmp, "datasets")
    shutil.copytree(os.path.join(ROOT, "data/provided"), os.path.join(ds, "01-같은자료-다시"))
    subprocess.run([sys.executable, "checks/break_data.py", "data/provided", ds], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    port = free_port()
    env = dict(os.environ, PORT=str(port), HOST="127.0.0.1", DB_PATH=os.path.join(tmp, "app.db"), DATASETS_DIR=ds,
               EXPORT_DIR=os.path.join(tmp, "out"), OPERATOR_PASSWORD="smoke-op", MEMBER_INITIAL_PASSWORD="smoke-m",
               PYTHONDONTWRITEBYTECODE="1")
    srv = start(env)
    base = f"http://127.0.0.1:{port}"
    try:
        op, mem = Client(base), Client(base)
        ok(op.call("/health")[1].get("dataset") is True, "빈 DB 에서 시작해 초기 데이터셋이 적용됨 (/health)")
        ok(op.call("/api/login", {"id": "operator", "pw": "틀림"})[0] == 401, "틀린 비밀번호 → 401")
        ok(op.call("/api/plans")[0] == 401, "로그인 전 운영 API → 401")
        ok(op.call("/api/login", {"id": "operator", "pw": "smoke-op"})[0] == 200, "운영자 로그인")
        ok(mem.call("/api/login", {"id": MEMBER_ID, "pw": "smoke-m"})[0] == 200, f"두 번째 역할 로그인 ({MEMBER_ID})")
        ok(mem.call("/api/plans")[0] == 403, "두 번째 역할이 운영 API → 403")

        v1 = op.call("/api/datasets")[1]["active"]["id"]
        for name in sorted(n for n in os.listdir(ds) if n.startswith("9")):
            c = op.call("/api/datasets/check", {"name": name})[1]
            a = op.call("/api/datasets/apply", {"name": name})
            ok(not c["ok"] and c["errors"] and a[0] == 422, f"{name}: 검사 오류 {len(c['errors'])}건 · 적용 거절 — {c['errors'][:1]}")
        ok(op.call("/api/datasets")[1]["active"]["id"] == v1, "오류 데이터셋 적용 시도 뒤에도 활성 데이터셋 그대로")

        st, pr = op.call("/api/params")
        bad = op.call("/api/params", {"dataset_id": pr["dataset_id"], "params": {**pr["params"], "date_from": "2026-13-40"}})
        ok(bad[0] == 422, f"형식 틀린 조건 → 422 {bad[1].get('errors', [''])[:1]}")
        p1 = op.call("/api/plans", {})[1]["plan_id"]
        pl = op.call(f"/api/plans/{p1}")[1]
        n_issue = len(pl["result"]["issues"])
        needs = pl.get("needs", {})
        F = lambda action: {"ack": True, "fields": {f["name"]: True if f["kind"] == "check" else "smoke" for f in needs.get(action, [])}}
        for action in needs:
            if action == "approve" and needs[action]:
                r = op.call(f"/api/plans/{p1}/approve", {"ack": True})
                ok(r[0] == 409, f"결재 입력 {[f['label'] for f in needs[action]]} 없이 결재 → 409")
        if n_issue:
            ok(op.call(f"/api/plans/{p1}/approve", {})[0] == 409, f"확인 필요 {n_issue}건인데 확인 체크 없이 결재 → 409")
        ok(op.call(f"/api/plans/{p1}/publish", {"ack": True})[0] == 409, "초안을 결재 없이 공개 → 409")

        codes = []
        th = [threading.Thread(target=lambda: codes.append(op.call(f"/api/plans/{p1}/approve", F("approve"))[0])) for _ in range(8)]
        [t.start() for t in th]
        [t.join() for t in th]
        ok(sorted(codes).count(200) == 1 and codes.count(409) == 7, f"같은 계획 결재를 동시에 8번 → 성공 1·거절 7 ({sorted(codes)})")
        if needs.get("publish"):
            ok(op.call(f"/api/plans/{p1}/publish", {"ack": True})[0] == 409, "공개 입력 없이 공개 → 409")
        ok(op.call(f"/api/plans/{p1}/publish", F("publish"))[0] == 200, "결재된 계획 공개")
        ev = op.call("/api/datasets")[1]["events"]
        ok(all(any(f["label"] in (e["detail"] or "") for e in ev) for a in needs for f in needs[a]), "결재·공개 입력이 기록(events)에 남음")

        my = mem.call("/api/my")[1]
        ok(my["published"] and my["published"]["id"] == p1, f"두 번째 역할이 공개본을 봄 (계획 {p1}, 날짜 {my.get('date')}, 항목 {len(my['items'])})")
        dates = my["dates"]
        my2 = mem.call(f"/api/my?date={dates[0]}")[1] if dates else {"items": []}
        ok(len(my2["items"]) > 0, f"날짜 {dates[:1]} 을 고르면 내 일정 {len(my2['items'])}건")

        ex = op.call(f"/api/plans/{p1}/export")[1]
        ok(json.load(open(ex["path"], encoding="utf-8")) == ex["data"], f"내보낸 파일 = 화면에 보인 JSON ({ex['path']})")
        chk = subprocess.run([sys.executable, "checks/verify.py", ex["path"], "data/provided"], cwd=ROOT, capture_output=True, text=True)
        ok(chk.returncode == 0, "내보낸 JSON 을 독립 검사기로: " + chk.stdout.strip().splitlines()[-1])

        p2 = op.call("/api/plans", {})[1]["plan_id"]
        op.call("/api/params", {"dataset_id": pr["dataset_id"], "params": {**pr["params"], **PARAM_CHANGE}})
        saved = op.call("/api/params")[1]["params"]
        ok(all(saved.get(k) == v for k, v in PARAM_CHANGE.items()), f"조건 저장 {PARAM_CHANGE}")
        a = op.call("/api/datasets/apply", {"name": "01-같은자료-다시"})
        ok(a[0] == 200, "정상 데이터셋 적용")
        pr2 = op.call("/api/params")[1]
        ok(pr2["dataset_id"] != pr["dataset_id"] and all(pr2["params"].get(k) == pr["params"].get(k) for k in PARAM_CHANGE),
           "새 데이터셋은 이전 조건을 물려받지 않고 기본값에서 시작")
        r = op.call(f"/api/plans/{p2}/approve", F("approve"))
        ok(r[0] == 409 and "이전 데이터셋" in r[1]["error"], "적용 전에 만든 계획 결재 → 409 이전 데이터셋")
        ok(op.call(f"/api/plans/{p2}")[1]["stale"] is True, "그 계획은 화면에 '이전 데이터셋' 으로 표시(stale)")
        ok(mem.call("/api/my")[1]["published"]["id"] == p1, "새 데이터셋 적용 뒤에도 공개 화면은 공개 당시 스냅숏")
        old = op.call(f"/api/plans/{p1}/export")[1]
        ok(old["stale"] is True, "옛 계획을 내보내면 stale 표시")

        n_plans = len(op.call("/api/plans")[1]["plans"])
        stop(srv)
        srv = start(env)
        op2 = Client(base)
        op2.call("/api/login", {"id": "operator", "pw": "smoke-op"})
        ok(len(op2.call("/api/plans")[1]["plans"]) == n_plans, f"재시작 뒤 계획 {n_plans}건 그대로")
        ok(op2.call("/api/datasets")[1]["active"]["name"] == "01-같은자료-다시", "재시작 뒤 활성 데이터셋 그대로")
    finally:
        stop(srv)

    night = subprocess.run([sys.executable, "-c", "import json,sys; from app import clock; "
                            f"print(clock.work_date([{json.dumps(NIGHT)}]))"],
                           cwd=ROOT, env=dict(os.environ, APP_NOW=NIGHT["at"], PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
    ok(night.stdout.strip() == NIGHT["expect"], f"자정 넘는 항목: {NIGHT['at']} 에 보면 날짜 {night.stdout.strip()} (기대 {NIGHT['expect']})")
    utc = subprocess.run([sys.executable, "-c", "from app import clock; print(clock.now().utcoffset())"], cwd=ROOT,
                         env=dict(os.environ, TZ="UTC", PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
    ok(utc.stdout.strip() == "9:00:00", f"서버 TZ=UTC 여도 '지금'은 APP_UTC_OFFSET 기준 ({utc.stdout.strip()})")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"합계 통과 {sum(results)} / {len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
