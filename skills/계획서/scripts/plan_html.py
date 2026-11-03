#!/usr/bin/env python3
"""PLAN.md · AGENTS.md · NOTES.md 를 읽어 PLAN.html 한 장으로 그린다.

목적: 사람이 '에이전트가 내 말을 제대로 알아들었나'를 한눈에 대조하는 것.
- 다시 정의한 문제: 처음 들은 말 → 대화 뒤 내 말
- 흐름: 입력 → 단계(맡은 규칙 번호) → 결과물
- 규칙마다 출처와 맡은 단계 (어느 단계에도 없는 규칙은 눈에 띄게)
- 요청자에게 확인받지 않은 결정과 아직 모르는 것
사용: 작업 폴더에서 `python3 <이 파일>` → view/plan.html. 표준 라이브러리만, Python 3.9 이상.
"""
import datetime
import html
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."


def read(name):
    p = os.path.join(ROOT, name)
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        return f.read()


def sections(md):
    """'## 제목' 단위로 나눈다. 코드 블록 안의 '#' 은 제목이 아니다."""
    out, cur, fence = {}, None, False
    for line in md.splitlines():
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
            continue
        if cur is not None:
            out[cur].append(line)
    return out


def pick(secs, *keys):
    for title, lines in secs.items():
        if any(k in title for k in keys):
            return [l for l in lines if l.strip()]
    return []


def e(s):
    return html.escape(s, quote=True)


def inline(s):
    """`코드` 와 **굵게** 만 살린다."""
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return s


def bullet(line):
    return re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()


def rule_nums(text):
    """'규칙 3', '규칙 1, 9', '규칙 5·8', '규칙 16~20' 의 번호들."""
    nums = set()
    for m in re.finditer(r"규칙\s?(\d+(?:\s*[~–-]\s*\d+|[\s,·와및]+\d+)*)(?![\d가-힣])", text):
        g = m.group(1)
        for a, b in re.findall(r"(\d+)\s*[~–-]\s*(\d+)", g):
            nums.update(range(int(a), int(b) + 1))
        g = re.sub(r"\d+\s*[~–-]\s*\d+", "", g)
        nums.update(int(x) for x in re.findall(r"\d+", g))
    return nums


def table(lines):
    rows = [l for l in lines if l.strip().startswith("|") and not re.match(r"^\s*\|[\s:|-]+\|\s*$", l)]
    if not rows:
        return ""
    def split(r):
        # `코드` 안의 | 는 칸 구분이 아니다
        out, cur, tick = [], "", False
        for ch in r.strip().strip("|"):
            if ch == "`":
                tick = not tick
            if ch == "|" and not tick:
                out.append(cur.strip()); cur = ""
            else:
                cur += ch
        out.append(cur.strip())
        return out
    cells = [split(r) for r in rows]
    head, body = cells[0], cells[1:]
    h = "".join("<th>%s</th>" % inline(c) for c in head)
    b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r) for r in body)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, b)


plan, agents, notes, readme = read("PLAN.md"), read("AGENTS.md"), read("NOTES.md"), read("README.md")
if not plan:
    sys.exit("PLAN.md 가 없습니다. 먼저 $계획서 로 PLAN.md 를 쓰세요.")
P, A = sections(plan), sections(agents)

title = next((l.lstrip("# ").strip() for l in readme.splitlines() if l.startswith("# ")), "계획")
title = re.sub(r"^과제:\s*", "", title)

# 다시 정의한 문제: '처음 … → … 내 말' 또는 '처음 요청:' / '대화 뒤 내 말:' 두 줄
prob = " ".join(l.strip() for l in pick(P, "다시 정의"))
before, after = "", prob
m = re.search(r"처음[^:：]*[:：]\s*(.+?)\s*(?:대화 뒤[^:：]*[:：]|→)\s*(.+)", prob)
if m:
    before, after = m.group(1).strip(), m.group(2).strip()
elif "→" in prob:
    before, after = [x.strip() for x in prob.split("→", 1)]

# 단계
steps = []
for l in pick(P, "단계"):
    m = re.match(r"^\s*(\d+)\.\s*(.+)$", l)
    if not m:
        if steps and l.startswith(" "):
            steps[-1]["text"] += " " + l.strip()
        continue
    steps.append({"n": int(m.group(1)), "text": m.group(2).strip()})
link_text = " ".join(pick(P, "규칙 ↔ 단계", "규칙↔단계"))
for s in steps:
    body, _, check = s["text"].partition("확인:")
    s["what"] = re.sub(r"\s*[—-]\s*$", "", body.strip())
    s["check"] = check.strip()
    s["rules"] = set(rule_nums(s["text"]))
# '규칙 ↔ 단계' 줄의 '규칙 1·2 → 단계 1' 도 반영
for m in re.finditer(r"규칙\s?([\d\s,·~–-]+?)\s*(?:\([^)]*\)\s*)?→\s*단계\s?(\d+)", link_text):
    nums = rule_nums("규칙 " + m.group(1))
    for s in steps:
        if s["n"] == int(m.group(2)):
            s["rules"] |= nums

# 규칙
rules = []
for l in pick(A, "확정된 규칙"):
    m = re.match(r"^\s*(\d+)\)\s*(.+)$", l)
    if not m:
        continue
    text = m.group(2)
    src = re.search(r"출처:\s*([^)]+?)\s*$", text)
    rules.append({
        "n": int(m.group(1)),
        "text": re.sub(r"\s*[—-]\s*출처:.*$", "", text).strip(),
        "src": src.group(1).strip() if src else "",
        "nocode": "(코드 아님)" in text,
        "changed": re.search(r"\(→ (?:예외: )?규칙 \d+[^)]*\)", text) is not None,
    })
for r in rules:
    r["steps"] = [s["n"] for s in steps if r["n"] in s["rules"]]

# 확인 안 된 것: 정한 것(요청자 미확인) / 아직 모름
decided, unknown = [], []
for l in pick(A, "확인 안 된 것"):
    t = bullet(l)
    if not t or t.startswith("정하지 말고"):
        continue
    if re.search(r"사용자 결정|요청자가 맡김|해석:|코드는 .* 로 처리", t):
        decided.append(t)
    else:
        unknown.append(t)
for l in pick(sections(notes), "결정"):
    t = bullet(l)
    if "요청자 미확인" in t and t not in decided:
        decided.append(t)

prio = pick(P, "우선순위")
example = pick(P, "예시")
done = pick(P, "완료 조건")
rejected = [bullet(l) for l in pick(A, "기각한 대안") if not l.strip().startswith("다시 제안")]

inputs = []
for d in ("data", "docs", "input", "자료"):
    p = os.path.join(ROOT, d)
    if os.path.isdir(p):
        for base, _, files in os.walk(p):
            for f in sorted(files):
                inputs.append(os.path.relpath(os.path.join(base, f), ROOT))
outputs = sorted(set(re.findall(r"`((?:out|output)/[^`\s]+)`", plan)))

now = datetime.datetime.now().strftime("%H:%M")
orphan = [r for r in rules if not r["steps"] and not r["nocode"] and not r["changed"]]


def li(items, cls=""):
    return "".join('<li%s>%s</li>' % (' class="%s"' % cls if cls else "", inline(i)) for i in items)


def mark_line(t):
    star = "★" in t
    t = t.replace("★", "").strip()
    cnt = re.search(r"\(지금 ([\d?]+)건[^)]*\)", t)
    t2 = re.sub(r"\s*\(지금 [\d?]+건[^)]*\)", "", t)
    tail = '<span class="cnt">%s건</span>' % cnt.group(1) if cnt else ""
    return '<li>%s%s%s</li>' % ('<span class="star" title="먼저 물을 것">먼저</span>' if star else "", inline(t2), tail)


flow = []
flow.append('<div class="node in"><h3>입력</h3><ul>%s</ul></div>' % (li(inputs[:12]) + ("<li>… 외 %d개</li>" % (len(inputs) - 12) if len(inputs) > 12 else "")))
for s in steps:
    tags = " ".join('<a href="#r%d" class="rn">%d</a>' % (n, n) for n in sorted(s["rules"]))
    flow.append('<div class="node step"><span class="sn">%d</span><p class="what">%s</p>%s%s</div>' % (
        s["n"], inline(s["what"]),
        '<p class="rules">규칙 %s</p>' % tags if tags else '<p class="rules none">맡은 규칙 없음</p>',
        '<p class="chk"><span>확인</span> %s</p>' % inline(s["check"]) if s["check"] else '<p class="chk none">확인 명령 없음</p>'))
flow.append('<div class="node out"><h3>결과물</h3><ul>%s</ul></div>' % (li(outputs) or "<li>PLAN 에 out/ 경로가 없음</li>"))

rule_rows = "".join(
    '<tr id="r%d" class="%s"><td class="num">%d</td><td>%s%s</td><td class="src">%s</td><td class="where">%s</td></tr>' % (
        r["n"], "orphan" if r in orphan else ("muted" if r["changed"] else ""), r["n"], inline(r["text"]),
        ' <span class="note">코드 아님</span>' if r["nocode"] else "",
        e(r["src"]),
        ("단계 " + ", ".join(str(x) for x in r["steps"])) if r["steps"] else ("작업 순서로 지킴" if r["nocode"] else ("바뀐 규칙" if r["changed"] else "어느 단계에도 없음")))
    for r in rules)

prio_cols = []
for key, label in (("먼저", "먼저"), ("남으면", "시간이 남으면"), ("안 함", "이번엔 안 함")):
    items = [bullet(l).split(":", 1)[-1].strip() for l in prio if key in l]
    prio_cols.append('<div><h3>%s</h3><ul>%s</ul></div>' % (label, li(items) or "<li class='empty'>없음</li>"))

doc = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>계획 대조 · %(title)s</title>
<style>
:root{--paper:#f2f4ef;--sheet:#fbfcf8;--ink:#1d2421;--soft:#58625c;--line:#d5dbd2;--brand:#24543f;--brandSoft:#e3ece5;--warn:#7a4e06;--warnSoft:#f6ecd6;--miss:#8b2a1c;--missSoft:#f5e2dd}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:1180px;margin:0 auto;padding:36px 28px 64px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:24px;margin-bottom:28px}
header h1{margin:0;font-size:26px;letter-spacing:-.01em;font-weight:700}
header p{margin:0;color:var(--soft);font-size:13px}
h2{font-size:17px;margin:40px 0 14px;font-weight:700}
h3{font-size:13px;margin:0 0 8px;color:var(--soft);font-weight:600}
code{font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--brandSoft);color:var(--brand);padding:1px 5px;border-radius:4px;word-break:break-all}
ul{margin:0;padding-left:18px}li{margin:3px 0}
.sync{display:grid;grid-template-columns:1fr auto 1.4fr;gap:0;background:var(--sheet);border-radius:14px;overflow:hidden}
.sync>div{padding:22px 26px}
.sync .was{color:var(--soft)}
.sync .now{background:var(--brandSoft)}
.sync .arrow{display:flex;align-items:center;padding:0 4px;color:var(--brand);font-size:22px}
.sync p{margin:0;font-size:16px}
.sync .now p{font-size:17px;font-weight:500}
.flow{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;align-items:stretch}
.node{background:var(--sheet);border-radius:12px;padding:16px 16px 14px;min-width:0}
.node.in,.node.out{background:transparent;border:1.5px dashed var(--line)}
.node.in li,.node.out li{font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--soft);list-style:none;margin-left:-18px;word-break:break-all}
.sn{display:block;font-size:30px;line-height:1;font-weight:700;color:var(--brand);margin-bottom:8px}
.what{margin:0 0 10px;font-weight:500}
.rules{margin:0 0 8px;font-size:13px;color:var(--soft)}
.rules.none{color:var(--miss)}
.rn{display:inline-block;min-width:22px;text-align:center;color:var(--brand);font-weight:700;text-decoration:none;border-bottom:1.5px solid var(--brand);margin-right:2px}
.chk{margin:0;font-size:12.5px;color:var(--soft)}.chk span{font-weight:600;color:var(--ink);margin-right:4px}
.chk.none{color:var(--miss)}
table{width:100%%;border-collapse:collapse;background:var(--sheet);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 14px;vertical-align:top}
th{font-size:12.5px;color:var(--soft);font-weight:600;background:var(--paper)}
tbody tr+tr td{border-top:1px solid var(--line)}
td.num{font-weight:700;color:var(--brand);width:44px}
td.src{color:var(--soft);white-space:nowrap;font-size:13px;width:150px}
td.where{white-space:nowrap;font-size:13px;width:150px}
tr.orphan td{background:var(--missSoft)}tr.orphan td.where{color:var(--miss);font-weight:700}
tr.muted td{color:var(--soft)}
.note{font-size:12px;color:var(--soft);margin-left:6px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.box{background:var(--sheet);border-radius:12px;padding:18px 20px}
.box.warn{background:var(--warnSoft)}.box.warn h3{color:var(--warn)}
.box li{margin:6px 0}
.star{font-size:11.5px;font-weight:700;color:var(--warn);margin-right:6px}
.cnt{font-size:12px;color:var(--soft);margin-left:8px;white-space:nowrap}
.prio{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.prio>div{background:var(--sheet);border-radius:12px;padding:16px 20px}
.prio>div:first-child{background:var(--brandSoft)}
.empty{color:var(--soft);list-style:none;margin-left:-18px}
.ask{margin:10px 0 0;color:var(--soft);font-size:13px}
footer{margin-top:44px;color:var(--soft);font-size:12.5px}
@media (max-width:760px){.sync{grid-template-columns:1fr}.sync .arrow{padding:6px 26px;transform:rotate(90deg);justify-content:flex-start}.split,.prio{grid-template-columns:1fr}}
</style></head><body><main>
<header><h1>%(title)s</h1><p>PLAN.md · AGENTS.md · NOTES.md 에서 %(now)s 에 만듦</p></header>

<section class="sync">
  <div class="was"><h3>처음 들은 말</h3><p>%(before)s</p></div>
  <div class="arrow" aria-hidden="true">→</div>
  <div class="now"><h3>대화 뒤 내 말 · 에이전트가 이해한 문제</h3><p>%(after)s</p></div>
</section>
<p class="ask">오른쪽이 내 생각과 다르면 지금 고친다. 이 아래는 모두 이 문장을 풀어 놓은 것이다.</p>

<h2>흐름</h2>
<div class="flow">%(flow)s</div>

<h2>규칙 %(nrules)d개 · 어디서 지키나</h2>
%(orphan_note)s
<table><thead><tr><th>#</th><th>규칙</th><th>출처</th><th>맡은 곳</th></tr></thead><tbody>%(rule_rows)s</tbody></table>

<h2>확인받지 않은 것</h2>
<div class="split">
  <div class="box warn"><h3>에이전트·내가 정한 것 · 요청자 미확인 %(nd)d</h3><ul>%(decided)s</ul></div>
  <div class="box"><h3>아직 모르는 것 %(nu)d</h3><ul>%(unknown)s</ul></div>
</div>

<h2>우선순위</h2>
<div class="prio">%(prio)s</div>

%(example)s
%(done)s
%(rejected)s
<footer>고칠 것이 보이면 에이전트에게 말로 고치게 하고, 이 스크립트를 다시 돌린다.</footer>
</main></body></html>
""" % {
    "title": e(title), "now": now, "before": inline(before) or "<span class='empty'>PLAN 에 처음 들은 말이 없음</span>", "after": inline(after),
    "flow": "".join(flow), "nrules": len(rules), "rule_rows": rule_rows or "<tr><td colspan=4>확정된 규칙 없음</td></tr>",
    "orphan_note": ('<p class="ask" style="color:var(--miss)">어느 단계에도 연결되지 않은 규칙 %d개: %s</p>' % (len(orphan), ", ".join(str(r["n"]) for r in orphan))) if orphan else "",
    "nd": len(decided), "decided": "".join(mark_line(t) for t in decided) or "<li class='empty'>없음</li>",
    "nu": len(unknown), "unknown": "".join(mark_line(t) for t in unknown) or "<li class='empty'>없음</li>",
    "prio": "".join(prio_cols),
    "example": ('<h2>예시 한 건</h2><div class="box"><ul>%s</ul></div>' % li([bullet(l) for l in example if not l.startswith("|")]) + table(example)) if example else "",
    "done": ('<h2>완료 조건</h2>' + (table(done) or '<div class="box"><ul>%s</ul></div>' % li([bullet(l) for l in done]))) if done else "",
    "rejected": ('<h2>기각한 대안</h2><div class="box"><ul>%s</ul></div>' % li(rejected)) if rejected else "",
}

os.makedirs(os.path.join(ROOT, "view"), exist_ok=True)
out = os.path.join(ROOT, "view", "plan.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(doc)
print("→ %s  (단계 %d · 규칙 %d · 단계 없는 규칙 %d · 미확인 결정 %d · 모르는 것 %d)" % (out, len(steps), len(rules), len(orphan), len(decided), len(unknown)))
