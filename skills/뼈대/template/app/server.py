"""웹 서버 — 표준 라이브러리만. python3 -m app.server

역할 두 개: operator(운영자) · member(두 번째 역할, spec.MEMBER 표의 아이디로 로그인).
흐름: 데이터셋 검사 → 적용 → 조건 저장 → 생성(초안) → 결재 → 공개 → 두 번째 역할이 공개본을 본다.
"""
import json
import os
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True

from . import clock, dataset, planner, spec, store  # noqa: E402

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DATASETS_DIR = os.environ.get("DATASETS_DIR", "data/datasets")
INITIAL_DATASET = os.environ.get("INITIAL_DATASET", "data/provided")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "out")
SESSION_HOURS = float(os.environ.get("SESSION_HOURS", "12"))
STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def need_env(*names):
    miss = [n for n in names if not os.environ.get(n)]
    if miss:
        sys.exit(f"환경변수 {', '.join(miss)} 가 필요합니다 (.env.example 참고)")


# ---------- 데이터셋 ----------
def dataset_dirs():
    out = {"provided": INITIAL_DATASET}
    if os.path.isdir(DATASETS_DIR):
        for n in sorted(os.listdir(DATASETS_DIR)):
            if os.path.isdir(os.path.join(DATASETS_DIR, n)):
                out[n] = os.path.join(DATASETS_DIR, n)
    return out


def check(name):
    path = dataset_dirs().get(name)
    if not path:
        return None, None, [f"데이터셋 없음: {name}"]
    texts = dataset.read_dir(path)
    data, errs = dataset.parse(texts)
    return texts, data, errs


def add_members(con, data):
    pw = os.environ["MEMBER_INITIAL_PASSWORD"]
    m = spec.MEMBER
    for r in data[m["table"]]:
        store.put_user(con, r[m["key"]], "member", r[m["name"]], pw)


def seed(con):
    store.put_user(con, os.environ.get("OPERATOR_USER", "operator"), "operator", "운영자", os.environ["OPERATOR_PASSWORD"])
    if store.active(con):
        return
    texts, data, errs = check("provided")
    if errs:
        sys.exit("초기 데이터셋 오류: " + "; ".join(errs[:5]))
    store.apply_dataset(con, "provided", texts, dataset.default_params(data), "시작")
    add_members(con, data)


def apply(name, who):
    with store.tx() as con:  # 검사와 적용을 한 트랜잭션에서. 실패하면 아무것도 바꾸지 않는다
        texts, data, errs = check(name)
        if errs:
            return {"ok": False, "errors": errs}
        vid = store.apply_dataset(con, name, texts, dataset.default_params(data), who)
        add_members(con, data)
        return {"ok": True, "dataset_id": vid}


def generate(who):
    with store.read() as con:
        a = store.active(con)  # id·원문·조건을 한 번에
    data, errs = dataset.parse(a["texts"])
    if errs:
        raise store.Conflict("저장된 데이터셋을 다시 읽지 못했습니다: " + errs[0])
    result = planner.generate(data, a["params"])
    with store.tx() as con:
        return store.save_plan(con, a["id"], a["params"], result, who)


def export(plan_id):
    with store.read() as con:
        p = store.plan(con, plan_id)
    if not p:
        return None
    with store.read() as con:
        ds = con.execute("SELECT name, digest FROM datasets WHERE id=?", (p["dataset_id"],)).fetchone()
    meta = {"plan_id": plan_id, "dataset": ds["name"], "digest": ds["digest"], "created_at": p["created_at"]}
    ex = planner.finish_export(p["result"]["export"], meta)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, f"plan-{plan_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ex, f, ensure_ascii=False, indent=1)
    return {"path": path, "stale": p["stale"], "status": p["status_ko"], "data": ex}


def my_view(user, day):
    with store.read() as con:
        pub = store.published(con)
    if not pub:
        return {"published": None, "items": [], "message": "공개된 계획이 없습니다."}
    items = pub["result"]["members"].get(user["id"], [])
    at = clock.now()
    day = day or clock.work_date(items, at)
    mine = [i for i in items if i["date"] == day]
    now_item = next((i for i in mine if clock.item_span(i)[0] <= at < clock.item_span(i)[1]), None)
    upcoming = next((i for i in mine if clock.item_span(i)[0] > at), None)
    return {"published": {"id": pub["id"], "created_at": pub["created_at"]}, "date": day, "now": at.strftime("%Y-%m-%d %H:%M"),
            "items": mine, "now_item": now_item, "next_item": upcoming, "graph": pub["result"]["graph"],
            "dates": sorted({i["date"] for i in items})}


# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    server_version = "app"

    def log_message(self, fmt, *a):
        sys.stderr.write(f"{store.stamp()} {self.address_string()} {fmt % a}\n")

    def send(self, code, body, ctype="application/json; charset=utf-8", headers=()):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            raise store.Conflict("요청이 너무 큽니다.")
        return json.loads(self.rfile.read(n) or b"{}")

    def token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid":
                return v
        return None

    def user(self, role=None):
        u = store.session_user(self.token())
        if not u:
            raise PermissionError(401)
        if role and u["role"] != role:
            raise PermissionError(403)
        return u

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def route(self, method):
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        parts = [p for p in url.path.split("/") if p]
        try:
            if method == "GET" and (not parts or parts[0] == "static"):
                return self.static(parts[1:] if parts else ["index.html"])
            if parts == ["health"]:
                return self.send(200, {"ok": True, "dataset": store.health()})
            if parts[:1] != ["api"]:
                return self.send(404, {"error": "없는 경로"})
            return self.api(method, parts[1:], q)
        except PermissionError as e:
            self.send(e.args[0], {"error": "로그인이 필요합니다." if e.args[0] == 401 else "이 역할은 할 수 없습니다."})
        except store.Conflict as e:
            self.send(409, {"error": str(e)})
        except (ValueError, KeyError) as e:
            self.send(400, {"error": f"요청 형식 오류: {e}"})
        except Exception:
            traceback.print_exc()
            self.send(500, {"error": "서버 오류 (서버 로그 확인)"})

    def static(self, rest):
        path = os.path.normpath(os.path.join(STATIC, *rest))
        if not path.startswith(STATIC) or not os.path.isfile(path):
            return self.send(404, {"error": "없는 파일"})
        ctype = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(os.path.splitext(path)[1], "text/plain")
        self.send(200, open(path, "rb").read(), ctype + "; charset=utf-8")

    def api(self, method, p, q):
        if method == "POST" and p == ["login"]:
            b = self.body()
            tok = store.login(b.get("id", ""), b.get("pw", ""), SESSION_HOURS)
            if not tok:
                return self.send(401, {"error": "아이디 또는 비밀번호가 맞지 않습니다."})
            return self.send(200, {"ok": True, "user": store.session_user(tok)},
                             headers=[("Set-Cookie", f"sid={tok}; HttpOnly; SameSite=Lax; Path=/")])
        if method == "POST" and p == ["logout"]:
            store.logout(self.token())
            return self.send(200, {"ok": True}, headers=[("Set-Cookie", "sid=; Max-Age=0; Path=/")])
        if p == ["me"]:
            return self.send(200, {"user": self.user(), "now": clock.now().strftime("%Y-%m-%d %H:%M")})
        if p == ["my"]:
            return self.send(200, my_view(self.user("member"), q.get("date")))

        who = self.user("operator")["id"]
        if method == "GET" and p == ["datasets"]:
            with store.read() as con:
                a = store.active(con)
                ev = store.events(con)
            return self.send(200, {"names": list(dataset_dirs()), "events": ev,
                                   "active": {k: a[k] for k in ("id", "name", "applied_at", "digest")} if a else None})
        if method == "POST" and p == ["datasets", "check"]:
            _, data, errs = check(self.body()["name"])
            counts = {t: len(rows) for t, rows in data.items()} if data else {}
            return self.send(200, {"ok": not errs, "errors": errs, "counts": counts})
        if method == "POST" and p == ["datasets", "apply"]:
            r = apply(self.body()["name"], who)
            return self.send(200 if r["ok"] else 422, r)
        if method == "GET" and p == ["params"]:
            with store.read() as con:
                a = store.active(con)
            fields = [{k: v for k, v in f.items() if k != "default"} for f in spec.PARAMS]
            return self.send(200, {"dataset_id": a["id"], "params": a["params"], "fields": fields})
        if method == "POST" and p == ["params"]:
            b = self.body()
            with store.read() as con:
                data, _ = dataset.parse(store.active(con)["texts"])
            params, errs = dataset.check_params(b.get("params", {}), data)
            if errs:
                return self.send(422, {"ok": False, "errors": errs})
            with store.tx() as con:
                store.set_params(con, int(b["dataset_id"]), params, who)
            return self.send(200, {"ok": True, "params": params})
        if method == "POST" and p == ["plans"]:
            return self.send(200, {"plan_id": generate(who)})
        if method == "GET" and p == ["plans"]:
            with store.read() as con:
                return self.send(200, {"plans": store.plans(con)})
        if len(p) >= 2 and p[0] == "plans" and p[1].isdigit():
            pid = int(p[1])
            if method == "GET" and len(p) == 2:
                with store.read() as con:
                    pl = store.plan(con, pid)
                return self.send(200, pl) if pl else self.send(404, {"error": "없는 계획"})
            if method == "GET" and p[2:] == ["export"]:
                r = export(pid)
                return self.send(200, r) if r else self.send(404, {"error": "없는 계획"})
            if method == "POST" and len(p) == 3:
                b = self.body()
                with store.tx() as con:  # 검사(상태·데이터셋·확인 필요·NEEDS)와 저장·기록을 한 트랜잭션에서
                    st = store.transition(con, pid, p[2], who, bool(b.get("ack")), b.get("fields") or {})
                return self.send(200, {"ok": True, "status": st})
        return self.send(404, {"error": "없는 API"})


def main():
    need_env("OPERATOR_PASSWORD", "MEMBER_INITIAL_PASSWORD")
    store.init(seed)
    srv = ThreadingHTTPServer((HOST, PORT), H)
    print(f"http://{HOST}:{PORT}  (DB {store.DB_PATH})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
