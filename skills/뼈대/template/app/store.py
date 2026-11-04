"""저장 — 고치지 않는 곳. SQLite 한 파일(DB_PATH).

지키는 것 (서술형 ②④ 답의 근거 — 줄 번호는 sed -n 으로 다시 찍는다):
  A. 요청마다 새 연결. 연결을 스레드끼리 나눠 쓰지 않는다                         → tx()
  B. 쓰기는 BEGIN IMMEDIATE 한 트랜잭션: 여러 프로세스·워커여도 한 번에 하나       → tx()
  C. 상태를 바꾸기 전 검사(지금 상태·활성 데이터셋·확인 필요)는 저장과 같은 트랜잭션  → transition()
  D. 활성 데이터셋은 id 와 내용을 한 행에서 한 번에 읽는다                          → active()
  E. 조건(params)은 데이터셋 버전마다 따로. 새로 적용하면 그 데이터의 기본값에서 시작  → apply_dataset()
  F. 계획은 만든 때의 데이터셋 id·조건·결과를 통째로 저장(스냅숏). 공개 화면은 스냅숏만 읽는다
  G. 다른 데이터셋으로 만든 계획은 결재·공개하지 못한다(409). 화면엔 '이전 데이터셋' 으로
  H. 생성 중에 데이터셋이 바뀌면 저장하지 않는다(409, 다시 생성)                     → save_plan()
  I. 모든 상태 변화는 events 에 남긴다(누가·언제·무엇)
"""
import contextlib
import hashlib
import json
import os
import secrets
import sqlite3

from . import clock

DB_PATH = os.environ.get("DB_PATH", "var/app.db")

# 계획 상태: 동작 → (바꾸기 전 상태, 바꾼 뒤 상태). 결재가 없는 요청이면 {"publish": ("draft", "published")} 로.
TRANSITIONS = {"approve": ("draft", "approved"), "publish": ("approved", "published")}
STATUS_KO = {"draft": "초안", "approved": "결재됨", "published": "공개", "replaced": "교체됨"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, role TEXT NOT NULL, name TEXT, salt TEXT, pw TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS datasets(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, applied_at TEXT, applied_by TEXT,
  texts TEXT, digest TEXT, params TEXT, active INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS one_active ON datasets(active) WHERE active=1;
CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id INTEGER NOT NULL, params TEXT,
  created_at TEXT, created_by TEXT, status TEXT NOT NULL, result TEXT, issues_n INTEGER, ack_by TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, who TEXT, what TEXT, plan_id INTEGER, detail TEXT);
"""


class Conflict(Exception):
    """409 로 돌려줄 거절. 문장은 화면에 그대로 보인다."""


def _connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextlib.contextmanager
def read():
    con = _connect()
    try:
        yield con
    finally:
        con.close()


@contextlib.contextmanager
def tx():
    con = _connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def stamp():
    return clock.now().strftime("%Y-%m-%dT%H:%M:%S")


def log(con, who, what, plan_id=None, detail=""):
    con.execute("INSERT INTO events(at, who, what, plan_id, detail) VALUES(?,?,?,?,?)",
                (stamp(), who, what, plan_id, detail))


# ---------- 계정 ----------
def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()


def put_user(con, uid, role, name, pw):
    if con.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        return
    salt = secrets.token_hex(8)
    con.execute("INSERT INTO users VALUES(?,?,?,?,?)", (uid, role, name, salt, _hash(pw, salt)))


def login(uid, pw, hours):
    with tx() as con:
        u = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not u or not secrets.compare_digest(u["pw"], _hash(pw, u["salt"])):
            return None
        token = secrets.token_urlsafe(24)
        exp = clock.now().timestamp() + hours * 3600
        con.execute("INSERT INTO sessions VALUES(?,?,?)", (token, uid, str(exp)))
        return token


def session_user(token):
    if not token:
        return None
    with read() as con:
        r = con.execute("SELECT u.id, u.role, u.name, s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
                        (token,)).fetchone()
    if not r or float(r["expires"]) < clock.now().timestamp():
        return None
    return {"id": r["id"], "role": r["role"], "name": r["name"]}


def logout(token):
    with tx() as con:
        con.execute("DELETE FROM sessions WHERE token=?", (token,))


# ---------- 데이터셋 ----------
def digest(texts):
    return hashlib.sha256(json.dumps(texts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def active(con):
    """(id, 이름, 원문, 조건) 을 한 행에서 — D. 없으면 None."""
    r = con.execute("SELECT id, name, applied_at, digest, texts, params FROM datasets WHERE active=1").fetchone()
    if not r:
        return None
    return {"id": r["id"], "name": r["name"], "applied_at": r["applied_at"], "digest": r["digest"],
            "texts": json.loads(r["texts"]), "params": json.loads(r["params"])}


def apply_dataset(con, name, texts, params, who):
    """검증은 부른 쪽이 이 트랜잭션 안에서 이미 끝냈다. E: 조건은 새 데이터의 기본값으로 시작."""
    con.execute("UPDATE datasets SET active=0 WHERE active=1")
    cur = con.execute("INSERT INTO datasets(name, applied_at, applied_by, texts, digest, params, active) VALUES(?,?,?,?,?,?,1)",
                      (name, stamp(), who, json.dumps(texts, ensure_ascii=False), digest(texts),
                       json.dumps(params, ensure_ascii=False)))
    log(con, who, "데이터셋 적용", detail=f"{name} → 버전 {cur.lastrowid}")
    return cur.lastrowid


def set_params(con, dataset_id, params, who):
    a = active(con)
    if not a or a["id"] != dataset_id:
        raise Conflict("화면을 연 뒤 데이터셋이 바뀌었습니다. 새로 고친 뒤 다시 저장하세요.")
    con.execute("UPDATE datasets SET params=? WHERE id=?", (json.dumps(params, ensure_ascii=False), dataset_id))
    log(con, who, "조건 저장", detail=json.dumps(params, ensure_ascii=False))


# ---------- 계획 ----------
def save_plan(con, dataset_id, params, result, who):
    """H: 계산을 시작할 때 본 데이터셋이 지금도 활성일 때만 저장."""
    a = active(con)
    if not a or a["id"] != dataset_id:
        raise Conflict("계산하는 동안 데이터셋이 바뀌었습니다. 다시 생성하세요.")
    cur = con.execute("INSERT INTO plans(dataset_id, params, created_at, created_by, status, result, issues_n) VALUES(?,?,?,?,?,?,?)",
                      (dataset_id, json.dumps(params, ensure_ascii=False), stamp(), who, "draft",
                       json.dumps(result, ensure_ascii=False), len(result.get("issues", []))))
    log(con, who, "계획 생성", cur.lastrowid, f"확인 필요 {len(result.get('issues', []))}건")
    return cur.lastrowid


def transition(con, plan_id, action, who, ack=False):
    """C: 읽기·검사·쓰기를 한 트랜잭션에서. 두 사람이 동시에 눌러도 한 번만 바뀐다."""
    if action not in TRANSITIONS:
        raise Conflict(f"없는 동작: {action}")
    before, after = TRANSITIONS[action]
    p = con.execute("SELECT id, dataset_id, status, issues_n FROM plans WHERE id=?", (plan_id,)).fetchone()
    if not p:
        raise Conflict("없는 계획입니다.")
    if p["status"] != before:
        raise Conflict(f"지금 상태가 '{STATUS_KO.get(p['status'], p['status'])}' 라서 할 수 없습니다.")
    a = active(con)
    if not a or p["dataset_id"] != a["id"]:  # G
        raise Conflict("이전 데이터셋으로 만든 계획입니다. 지금 데이터셋으로 다시 생성하세요.")
    if p["issues_n"] and not ack:
        raise Conflict(f"확인 필요 {p['issues_n']}건이 있습니다. 내용을 보고 '확인함' 을 체크한 뒤 진행하세요.")
    if after == "published":
        con.execute("UPDATE plans SET status='replaced' WHERE status='published'")
    con.execute("UPDATE plans SET status=?, ack_by=COALESCE(ack_by, ?) WHERE id=?",
                (after, who if p["issues_n"] else None, plan_id))
    log(con, who, STATUS_KO[after], plan_id, "확인 필요 확인함" if p["issues_n"] else "")
    return after


def plans(con):
    a = active(con)
    out = []
    for r in con.execute("SELECT id, dataset_id, created_at, created_by, status, issues_n FROM plans ORDER BY id DESC LIMIT 50"):
        d = dict(r)
        d["stale"] = not a or r["dataset_id"] != a["id"]
        d["status_ko"] = STATUS_KO.get(r["status"], r["status"])
        out.append(d)
    return out


def plan(con, plan_id):
    r = con.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    if not r:
        return None
    a = active(con)
    d = dict(r)
    d["params"], d["result"] = json.loads(d["params"]), json.loads(d["result"])
    d["stale"] = not a or r["dataset_id"] != a["id"]
    d["status_ko"] = STATUS_KO.get(r["status"], r["status"])
    return d


def published(con):
    """F: 공개된 계획의 스냅숏. 지금 데이터셋으로 다시 계산하지 않는다."""
    r = con.execute("SELECT id, dataset_id, created_at, result FROM plans WHERE status='published' ORDER BY id DESC LIMIT 1").fetchone()
    return None if not r else {"id": r["id"], "dataset_id": r["dataset_id"], "created_at": r["created_at"],
                               "result": json.loads(r["result"])}


def events(con, n=30):
    return [dict(r) for r in con.execute("SELECT at, who, what, plan_id, detail FROM events ORDER BY id DESC LIMIT ?", (n,))]


def init(seed):
    """빈 DB 에서 스키마와 초기 데이터. seed(con) 는 운영자 계정·초기 데이터셋을 넣는다."""
    con = _connect()
    try:
        con.executescript(SCHEMA)
    finally:
        con.close()
    with tx() as con:
        seed(con)


def health():
    with read() as con:
        con.execute("SELECT 1").fetchone()
        return active(con) is not None
