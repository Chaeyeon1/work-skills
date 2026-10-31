#!/usr/bin/env python3
"""결과 보고 한 장 (view/report.html). 두 단계로 쓴다. 표준 라이브러리만, Python 3.9 이상.

1) python3 report_html.py draft
   기계로 뽑을 수 있는 것(바뀐 파일, 바뀐 줄의 분기, checks/ 이름, 확정된 규칙, 요청자 미확인 결정,
   남은 한계, 커밋)을 .verify/report.json 에 쓴다. 에이전트가 채울 칸은 비워 둔다.
   이미 있으면 에이전트가 채운 칸은 그대로 두고 기계 목록(_ 로 시작하는 칸)만 새로 쓴다.
2) 에이전트가 .verify/report.json 의 빈 칸을 요청자가 부르는 말로 채운다(코드 이름은 괄호).
3) python3 report_html.py
   그린다. 그릴 때마다 기계 목록을 다시 뽑아 누락 대조를 하고, 빠진 것이 있으면 맨 위에 '누락 N' 을 띄운다.

채울 칸 (report.json):
  summary   요청자에게 보낼 요약 세 줄 (숫자는 실제 출력에서)
  features  [{"what": 무엇을 할 수 있게 됐나, "when": 언제 보이나}]
  flow      {"inputs": [입력 파일·칸], "rules": [{"rule": 판단 규칙, "basis": "파일:줄", "quote": 코드 원문 한 줄}], "outputs": [출력 칸·화면 자리]}
  cases     [{"cond": 입력 조건(경계·빈 값·처음 보는 값·중복·기간 밖…), "result": 결과, "how": 확인 방법(checks 이름 / 명령 / 화면 / 미확인)}]
  diffs     [{"what": 요청과 다르게 간 것, "why": 이유, "who": "요청자 HH:MM" 또는 "사용자 결정 HH:MM (요청자 미확인)", "pending": 대기 중인 질문}]
  files     {"바뀐 파일 경로": "요청자에게 무엇이 달라졌나 한 줄"}
  before_after {"before": {"caption", "table": {"head", "rows"} | "lines": [...] | "img": "img/x.png" (view/img/ 에 두고 커밋)}, "after": {...}, "note": 어떻게 껐고 되돌렸나}
  view      [보는 순서: "새 터미널: python3 -m http.server 8090 --bind 0.0.0.0", "Browser 탭 PORT 8090 · URL /out/x.html", "○○ 누르기"]
  limits    ["🔴/🟠/🟡 무엇이 틀릴 수 있나 → 어떻게 확인하나"]  (비우면 README·NOTES '한계' 절을 쓴다)
"""
import datetime
import html
import json
import os
import re
import subprocess
import sys

ROOT = "."
VERIFY = os.path.join(ROOT, ".verify")
JSON_PATH = os.path.join(VERIFY, "report.json")
SKIP = re.compile(r"(^|/)(\.agents|\.verify|out|output|dist|build|view|node_modules|__pycache__|tmp)/")
DATA_EXT = (".md", ".txt", ".csv", ".tsv", ".json", ".lock", ".png", ".jpg", ".svg", ".pdf", ".xlsx", ".log", ".html")
FILL = ["summary", "features", "flow", "cases", "diffs", "files", "before_after", "view", "limits"]


def sh(*cmd):
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True, timeout=30, cwd=ROOT).stdout
    except Exception:
        return ""


def read(name):
    p = os.path.join(ROOT, name)
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def sections(md, level="## "):
    out, cur, fence = {}, None, False
    for line in md.splitlines():
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith(level):
            cur = line[len(level):].strip()
            out[cur] = []
            continue
        if cur is not None:
            out[cur].append(line)
    return out


def pick(secs, *keys):
    lines = []
    for title, ls in secs.items():
        if any(k in title for k in keys):
            lines += ls
    return lines


def bullet(line):
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()


def rule_nums(text):
    nums = set()
    for m in re.finditer(r"규칙\s?(\d+(?:\s*[~–-]\s*\d+|[\s,·와및]+\d+)*)(?![\d가-힣])", text):
        g = m.group(1)
        for a, b in re.findall(r"(\d+)\s*[~–-]\s*(\d+)", g):
            nums.update(range(int(a), int(b) + 1))
        nums.update(int(x) for x in re.findall(r"\d+", re.sub(r"\d+\s*[~–-]\s*\d+", "", g)))
    return nums


def inventory():
    """기계로 뽑는 목록. 매번 새로 뽑는다."""
    git = ["git", "-c", "core.quotepath=off"]
    first = sh(*git, "rev-list", "--max-parents=0", "HEAD").strip().splitlines()
    base = first[0] if first else ""
    changed = []
    if base:
        for l in sh(*git, "diff", "--name-status", base, "HEAD").splitlines():
            parts = l.split("\t")
            if len(parts) >= 2:
                changed.append(parts[-1])
    for l in sh(*git, "status", "--porcelain").splitlines():
        p = l[3:].strip().strip('"')
        if p and p not in changed:
            changed.append(p)
    changed = [p for p in changed if not SKIP.search(p) and not p.startswith(("data/", "docs/"))]

    # 바뀐 코드 줄의 분기: if · elif · else · continue · return · except · ? : · and/or 조건
    branches = []
    code = [p for p in changed if not p.endswith(DATA_EXT) and not p.startswith("checks/")]
    for p in code:
        diff = sh(*git, "diff", "-U0", base, "--", p) if base else ""
        if not diff and os.path.exists(os.path.join(ROOT, p)):
            with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as f:
                diff = "".join("+" + l for l in f)
            lineno = 0
        ln = 0
        for l in diff.splitlines():
            m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", l)
            if m:
                ln = int(m.group(1)) - 1
                continue
            if l.startswith("+") and not l.startswith("+++"):
                ln += 1
                s = l[1:].strip()
                if re.match(r"^(if |elif |else\b|except\b|continue\b|return\b|break\b)", s) or re.search(r"\bif\b.+\belse\b|\?.+:", s):
                    branches.append("%s:%d  %s" % (p, ln, s[:140]))
    checks = []
    if os.path.isdir(os.path.join(ROOT, "checks")):
        for f in sorted(os.listdir(os.path.join(ROOT, "checks"))):
            if not f.startswith("."):
                checks.append("checks/" + f)
    for p in sh(*git, "ls-files").splitlines() + [x for x in changed]:
        if re.search(r"(^|/)test_[^/]+\.py$|_test\.py$", p) and os.path.exists(os.path.join(ROOT, p)):
            with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as f:
                checks += ["%s::%s" % (p, n) for n in re.findall(r"^\s*def (test_\w+)", f.read(), re.M)]

    agents, notes, readme = read("AGENTS.md"), read("NOTES.md"), read("README.md")
    A, N = sections(agents), sections(notes)
    rules = []
    for l in pick(A, "확정된 규칙"):
        m = re.match(r"^\s*(\d+)\)\s*(.+)$", l)
        if m:
            rules.append({"n": int(m.group(1)), "text": re.sub(r"\s*[—-]\s*출처:.*$", "", m.group(2)).strip(),
                          "skip": bool(re.search(r"\(코드 아님\)|→ (?:예외: )?규칙 \d+", m.group(2)))})
    decided = []
    for l in pick(A, "확인 안 된 것"):
        t = bullet(l)
        if re.search(r"사용자 결정|요청자가 맡김|해석:|요청자가 나중에 정함", t):
            decided.append(t)
    for l in pick(N, "결정"):
        t = bullet(l)
        if "요청자 미확인" in t and t not in decided:
            decided.append(t)
    limits = []
    for src in (readme, notes):
        for lvl in ("## ", "### "):
            for t, ls in sections(src, lvl).items():
                if "한계" in t:
                    limits += [bullet(l) for l in ls if l.strip() and not l.strip().startswith("|")]
    title = next((l.lstrip("# ").strip() for l in readme.splitlines() if l.startswith("# ")), "결과 보고")
    log = sh(*git, "log", "--reverse", "--date=format:%H:%M", "--format=%ad\t%h\t%s").strip().splitlines()
    status = sh(*git, "status", "--porcelain").strip().splitlines()
    chk = ""
    for c in (".agents/skills/검사/scripts/check.sh", os.path.expanduser("~/.agents/skills/검사/scripts/check.sh")):
        if os.path.exists(os.path.join(ROOT, c) if not c.startswith("/") else c):
            lines = sh("bash", c).strip().splitlines()
            chk = lines[-1] if lines else ""
            break
    return {"_title": re.sub(r"^과제:\s*", "", title), "_changed_files": changed, "_branches": branches, "_checks": checks,
            "_rules": rules, "_decided": decided, "_limits": list(dict.fromkeys(x for x in limits if x)),
            "_commits": log, "_status": status, "_check_sh": chk}


def load():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


inv = inventory()
data = load()
if len(sys.argv) > 1 and sys.argv[1] == "draft":
    os.makedirs(VERIFY, exist_ok=True)
    for k in FILL:
        data.setdefault(k, {} if k in ("flow", "files", "before_after") else [])
    if not data["files"]:
        data["files"] = {p: "" for p in inv["_changed_files"]}
    else:
        for p in inv["_changed_files"]:
            data["files"].setdefault(p, "")
    data.update(inv)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("→ %s  초안 (바뀐 파일 %d · 분기 %d · checks %d · 규칙 %d · 미확인 결정 %d)" % (
        JSON_PATH, len(inv["_changed_files"]), len(inv["_branches"]), len(inv["_checks"]), len(inv["_rules"]), len(inv["_decided"])))
    print("다음: _branches 를 보고 flow.rules·cases 를, _decided 를 보고 diffs 를, files 의 빈 설명을 채운 뒤 인자 없이 다시 돌린다.")
    sys.exit(0)

# ── 누락 대조 ──
missing = []
if not data:
    missing.append("report.json 이 없음 — 먼저 `report_html.py draft` 로 초안을 만들고 칸을 채운다")
files = data.get("files", {}) or {}
for p in inv["_changed_files"]:
    if not str(files.get(p, "")).strip():
        missing.append("바뀐 파일 설명 없음: %s" % p)
blob = json.dumps({k: data.get(k) for k in FILL}, ensure_ascii=False)
how = " ".join(str(c.get("how", "")) for c in data.get("cases", []) if isinstance(c, dict))
for c in inv["_checks"]:
    short = c.split("::")[-1]
    if c not in how and short not in how and os.path.basename(c) not in how:
        missing.append("케이스 표 '확인 방법'에 없는 검산: %s" % c)
mentioned = rule_nums(blob)
for r in inv["_rules"]:
    if r["skip"]:
        continue
    if r["n"] not in mentioned and r["text"][:12] not in blob:
        missing.append("동작 원리·케이스에 안 나오는 규칙 %d: %s" % (r["n"], r["text"][:40]))
dtext = json.dumps(data.get("diffs", []), ensure_ascii=False)
for d in inv["_decided"]:
    key = re.split(r"\s*→", d)[0].strip()[:14]
    if key and key not in dtext and not (rule_nums(d) & rule_nums(dtext)):
        missing.append("'다른 점'에 없는 미확인 결정: %s" % d[:50])
for side in ("before", "after"):
    img = ((data.get("before_after") or {}).get(side) or {}).get("img")
    if img and not os.path.exists(os.path.normpath(os.path.join(ROOT, "view", img))):
        missing.append("깨진 이미지: %s" % img)
for k in ("summary", "features", "cases", "view"):
    if not data.get(k):
        missing.append("빈 칸: %s" % k)


def e(s):
    return html.escape(str(s), quote=True)


def inline(s):
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def ul(items, cls=""):
    if not items:
        return '<p class="soft">없음</p>'
    return '<ul%s>%s</ul>' % (' class="%s"' % cls if cls else "", "".join("<li>%s</li>" % inline(i) for i in items))


def tbl(head, rows, cls=""):
    return '<table%s><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
        ' class="%s"' % cls if cls else "", "".join("<th>%s</th>" % e(h) for h in head),
        "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows))


def side(d, tone, label):
    if not d:
        return '<figure class="%s"><figcaption>%s</figcaption><p class="soft">비어 있음</p></figure>' % (tone, label)
    body = ""
    if d.get("img"):
        body = '<img src="%s" alt="%s">' % (e(d["img"]), e(d.get("caption", label)))
    elif d.get("table"):
        t = d["table"]
        body = tbl(t.get("head", []), [[inline(c) for c in r] for r in t.get("rows", [])])
    elif d.get("lines"):
        body = "<pre>%s</pre>" % e("\n".join(d["lines"]))
    return '<figure class="%s"><figcaption>%s · %s</figcaption>%s</figure>' % (tone, label, e(d.get("caption", "")), body)


flow = data.get("flow") or {}
cases = data.get("cases") or []
diffs = data.get("diffs") or []
ba = data.get("before_after") or {}
limits = data.get("limits") or inv["_limits"]
now = datetime.datetime.now().strftime("%H:%M")
clean = not inv["_status"]

parts = []
if missing:
    parts.append('<div class="missing"><b>누락 %d</b><ul>%s</ul></div>' % (len(missing), "".join("<li>%s</li>" % e(m) for m in missing)))
parts.append('<section class="lead"><h2>요약</h2>%s</section>' % ul(data.get("summary") or []))
parts.append('<h2>① 기능 목록</h2>' + (tbl(["무엇을 할 수 있게 됐나", "언제 보이나"], [[inline(f.get("what", "")), inline(f.get("when", ""))] for f in data.get("features", []) if isinstance(f, dict)]) if data.get("features") else '<p class="soft">비어 있음</p>'))
flow_html = '<div class="flow"><div class="node io"><h3>입력</h3>%s</div><div class="node"><h3>판단 규칙</h3>%s</div><div class="node io"><h3>출력</h3>%s</div></div>' % (
    ul(flow.get("inputs", [])),
    tbl(["규칙", "근거"], [[inline(r.get("rule", "")), "<code>%s</code>%s" % (e(r.get("basis", "")), ('<div class="quote">%s</div>' % e(r["quote"])) if r.get("quote") else "")] for r in flow.get("rules", []) if isinstance(r, dict)]) if flow.get("rules") else '<p class="soft">비어 있음</p>',
    ul(flow.get("outputs", [])))
parts.append('<h2>② 동작 원리</h2>' + flow_html)
parts.append('<h2>③ 케이스 표</h2>' + (tbl(["입력 조건", "결과", "확인 방법"], [[inline(c.get("cond", "")), inline(c.get("result", "")),
            ('<span class="miss">미확인</span>' if "미확인" in str(c.get("how", "")) else inline(c.get("how", "")))] for c in cases if isinstance(c, dict)]) if cases else '<p class="soft">비어 있음</p>'))
parts.append('<h2>④ 요청과 다른 점</h2>' + (tbl(["무엇이", "왜", "누가 정했나", "대기 중인 질문"], [[inline(d.get("what", "")), inline(d.get("why", "")),
            ('<span class="wait">%s</span>' % e(d.get("who", ""))) if "미확인" in str(d.get("who", "")) else e(d.get("who", "")), inline(d.get("pending", ""))] for d in diffs if isinstance(d, dict)]) if diffs else '<p class="soft">없음</p>'))
parts.append('<h2>수정 전 / 수정 후</h2><div class="ba">%s%s</div>%s' % (side(ba.get("before"), "before", "수정 전"), side(ba.get("after"), "after", "수정 후"),
            '<p class="soft">%s</p>' % inline(ba["note"]) if ba.get("note") else ""))
parts.append('<h2>보는 곳</h2>' + (('<ol class="view">%s</ol>' % "".join("<li>%s</li>" % inline(v) for v in data.get("view", []))) if data.get("view") else '<p class="soft">비어 있음</p>'))
parts.append('<h2>바뀐 파일 %d</h2>' % len(inv["_changed_files"]) + tbl(["파일", "무엇이 달라졌나"], [["<code>%s</code>" % e(p), inline(files.get(p, "")) or '<span class="miss">설명 없음</span>'] for p in inv["_changed_files"]]))
parts.append('<h2>남은 한계</h2>' + ul(limits))
tail = '<h2>꼬리</h2><div class="tail"><p><b>작업 트리</b> %s · <b>점검 스크립트</b> %s</p>%s</div>' % (
    "깨끗함" if clean else '<span class="miss">커밋 안 된 변경 %d</span>' % len(inv["_status"]),
    e(inv["_check_sh"] or "못 찾음"),
    tbl(["시각", "커밋", "메시지"], [[e(x) for x in (c.split("\t") + ["", ""])[:3]] for c in inv["_commits"]], "log"))
parts.append(tail)

doc = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>결과 보고 · %(title)s</title>
<style>
:root{--paper:#f2f4ef;--sheet:#fbfcf8;--ink:#1d2421;--soft:#58625c;--line:#d5dbd2;--brand:#24543f;--brandSoft:#e3ece5;--warn:#7a4e06;--warnSoft:#f6ecd6;--miss:#8b2a1c;--missSoft:#f5e2dd}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:1080px;margin:0 auto;padding:36px 28px 64px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:24px;margin-bottom:22px}
header h1{margin:0;font-size:26px}header p{margin:0;color:var(--soft);font-size:13px}
h2{font-size:17px;margin:36px 0 12px}h3{font-size:13px;margin:0 0 8px;color:var(--soft);font-weight:600}
code{font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--brandSoft);color:var(--brand);padding:1px 5px;border-radius:4px;word-break:break-all}
pre{margin:0;padding:12px 14px;background:#fff;border-radius:8px;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;word-break:break-all}
ul,ol{margin:0;padding-left:20px}li{margin:3px 0}
.missing{background:var(--missSoft);color:var(--miss);border-radius:12px;padding:14px 20px;margin-bottom:18px}
.missing b{font-size:16px}
.lead{background:var(--brandSoft);border-radius:14px;padding:4px 24px 18px}.lead h2{margin-top:16px}
table{width:100%%;border-collapse:collapse;background:var(--sheet);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:9px 14px;vertical-align:top}
th{font-size:12.5px;color:var(--soft);font-weight:600;background:var(--paper)}
tbody tr+tr td{border-top:1px solid var(--line)}
.flow{display:grid;grid-template-columns:1fr 2fr 1fr;gap:14px}
.node{background:var(--sheet);border-radius:12px;padding:16px}.node.io{background:transparent;border:1.5px dashed var(--line)}
.node table{background:#fff}
.quote{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--soft);margin-top:4px;word-break:break-all}
.ba{display:grid;grid-template-columns:1fr 1fr;gap:14px}
figure{margin:0;background:var(--sheet);border-radius:12px;padding:12px 14px}
figcaption{font-size:13px;font-weight:600;margin-bottom:8px}
figure.before figcaption{color:var(--miss)}figure.after figcaption{color:var(--brand)}
figure img{max-width:100%%;display:block;border-radius:6px}
.view li{margin:6px 0}
.soft{color:var(--soft);font-size:13.5px}.miss{color:var(--miss);font-weight:700}.wait{color:var(--warn);font-weight:600}
.tail p{margin:0 0 10px}
.log td:first-child{width:64px;color:var(--soft)}.log td:nth-child(2){width:84px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
@media (max-width:760px){.flow,.ba{grid-template-columns:1fr}header{display:block}}
</style></head><body><main>
<header><h1>%(title)s</h1><p>실행 결과로 만든 보고 · %(now)s</p></header>
%(parts)s
</main></body></html>
""" % {"title": e(inv["_title"]), "now": now, "parts": "".join(parts)}

os.makedirs(os.path.join(ROOT, "view"), exist_ok=True)
with open(os.path.join(ROOT, "view", "report.html"), "w", encoding="utf-8") as f:
    f.write(doc)
print("→ view/report.html  (누락 %d · 바뀐 파일 %d · 케이스 %d · 다른 점 %d)" % (len(missing), len(inv["_changed_files"]), len(cases), len(diffs)))
for m in missing:
    print("  누락: " + m)
