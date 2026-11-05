"""내가 만든 것 한 장 — view/explain.json → view/explain.html

python3 explain_html.py [view/explain.json] [view/explain.html]   (작업 폴더 맨 위에서)

json 에 쓴 `파일:줄` 은 이 스크립트가 그 줄을 다시 읽어 원문을 붙인다. 파일이 없거나 줄이 넘치면 빨간 '좌표 없음'.
json 모양 (칸은 짧은 명사구. 없는 칸은 빼도 된다):
{
 "title": "무엇", "problem": "다시 정의한 문제 한 줄",
 "criteria": {"q": "물을 만한 질문", "order": ["① …", "② …"], "method": "방법 한 줄",
              "rejected": [{"what": "기각한 방법", "why": "이유", "lost": "포기한 것"}],
              "compare": [{"case": "조건", "mine": "내 안 값", "other": "비교안 값", "cmd": "명령"}]},
 "flow": {"q": "…", "steps": [{"name": "단계", "what": "하는 일", "state": "저장·상태 변화", "where": "app/x.py:12"}]},
 "checked": {"q": "…", "done": [{"what": "확인한 것", "how": "명령 → 결과", "when": "HH:MM"}],
             "assumed": [{"what": "가정·안 한 확인", "risk": "틀리면", "where": "파일:줄"}]},
 "failures": {"q": "…", "rows": [{"case": "동시 결재", "happens": "남는 행·화면", "where": "파일:줄", "checked": "HH:MM 명령 | 미확인"}]},
 "changes": {"q": "…", "rows": [{"change": "바꾼 조건", "result": "깨지는 곳·늘어난 지표", "where": "파일:줄", "checked": "HH:MM | 미확인"}]},
 "sources": {"q": "…", "rows": [{"value": "값·판정", "from": "파일.csv 열", "code": "파일:줄", "shown": "화면·내보내기 어디"}],
             "invalid": "검증 실패 데이터셋이면 무엇을 쓰나 + 파일:줄", "conflict": "파일끼리 다를 때 믿은 쪽 + 결정 시각"},
 "decisions": [{"what": "결정", "by": "요청자 HH:MM | 나 HH:MM", "note": "한 마디"}],
 "numbers": [{"name": "이름", "value": "값", "cmd": "만든 명령"}]
}
"""
import html
import json
import os
import re
import sys
from datetime import datetime

COORD = re.compile(r"([\w./\-가-힣]+\.(?:py|js|html|css|sh|md|csv|json|sql|txt)):(\d+)")
stats = {"ok": 0, "bad": 0}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def coords(text):
    """문장 속 파일:줄 마다 원문을 붙인다."""
    if not text:
        return ""
    out, last = [], 0
    for m in COORD.finditer(text):
        out.append(esc(text[last:m.start()]))
        path, n = m.group(1), int(m.group(2))
        line = None
        if os.path.isfile(path):
            rows = open(path, encoding="utf-8", errors="replace").read().splitlines()
            if 1 <= n <= len(rows):
                line = rows[n - 1].strip()
        if line is None:
            stats["bad"] += 1
            out.append(f'<span class="co bad" title="파일이 없거나 줄이 넘침"><code>{esc(m.group(0))}</code> 좌표 없음</span>')
        else:
            stats["ok"] += 1
            out.append(f'<span class="co"><code>{esc(m.group(0))}</code><q>{esc(line[:96])}{"…" if len(line) > 96 else ""}</q></span>')
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


def status(text):
    t = str(text or "")
    if not t or "미확인" in t:
        return f'<span class="tag miss">{esc(t or "미확인")}</span>'
    return f'<span class="tag ok">{esc(t)}</span>'


def q(sec):
    return f'<p class="q">물을 만한 질문 — {esc(sec.get("q"))}</p>' if sec.get("q") else ""


def table(head, rows):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def section(no, title, body):
    return f'<section id="s{no}"><h2><span class="no">{no}</span>{esc(title)}</h2>{body}</section>'


def build(d):
    parts = []
    c = d.get("criteria", {})
    if c:
        order = "".join(f"<li>{coords(x)}</li>" for x in c.get("order", []))
        rej = [f"<tr><td>{esc(r.get('what'))}</td><td>{coords(r.get('why'))}</td><td>{coords(r.get('lost'))}</td></tr>" for r in c.get("rejected", [])]
        cmp_ = [f"<tr><td>{esc(r.get('case'))}</td><td class='b'>{esc(r.get('mine'))}</td><td>{esc(r.get('other'))}</td><td><code>{esc(r.get('cmd'))}</code></td></tr>" for r in c.get("compare", [])]
        body = q(c) + f'<div class="two"><div class="card"><h3>더 나은 계획의 기준 (앞이 우선)</h3><ol>{order}</ol></div>' \
            f'<div class="card"><h3>방법</h3><p>{coords(c.get("method"))}</p></div></div>'
        if rej:
            body += "<h3>고르지 않은 방법</h3>" + table(["방법", "이유", "포기한 것"], rej)
        if cmp_:
            body += "<h3>비교한 숫자</h3>" + table(["조건", "내 안", "비교안", "명령"], cmp_)
        parts.append(section("①", "기준과 포기한 것", body))
    f = d.get("flow", {})
    if f:
        steps = []
        for i, s in enumerate(f.get("steps", [])):
            steps.append(f'<div class="step"><b>{i + 1}. {esc(s.get("name"))}</b><p>{coords(s.get("what"))}</p>'
                         f'<p class="state">{coords(s.get("state"))}</p><p class="where">{coords(s.get("where"))}</p></div>')
        parts.append(section("②", "입력에서 공개까지 — 모듈과 상태 순서", q(f) + f'<div class="flow">{"<i>→</i>".join(steps)}</div>'))
    k = d.get("checked", {})
    if k:
        done = "".join(f"<li><b>{coords(x.get('what'))}</b><br><code>{esc(x.get('how'))}</code> {status(x.get('when'))}</li>" for x in k.get("done", []))
        ass = "".join(f"<li><b>{coords(x.get('what'))}</b><br>틀리면: {coords(x.get('risk'))} {coords(x.get('where'))}</li>" for x in k.get("assumed", []))
        parts.append(section("③", "확인한 것과 가정한 것", q(k) + f'<div class="two"><div class="card ok"><h3>확인함 (명령·시각)</h3><ul>{done}</ul></div>'
                             f'<div class="card miss"><h3>가정·확인 안 함</h3><ul>{ass}</ul></div></div>'))
    for no, key, title, head, cols in (
            ("④", "failures", "동시 실행 · 도중 오류 · 취소", ["경우", "일어나는 일", "근거", "확인"], ("case", "happens", "where", "checked")),
            ("⑤", "changes", "조건·자료가 바뀌면", ["바꾼 것", "결과", "근거", "확인"], ("change", "result", "where", "checked"))):
        sec = d.get(key, {})
        if sec:
            rows = [f"<tr><td><b>{esc(r.get(cols[0]))}</b></td><td>{coords(r.get(cols[1]))}</td><td>{coords(r.get(cols[2]))}</td><td>{status(r.get(cols[3]))}</td></tr>"
                    for r in sec.get("rows", [])]
            parts.append(section(no, title, q(sec) + table(head, rows)))
    s = d.get("sources", {})
    if s:
        rows = [f"<tr><td><b>{esc(r.get('value'))}</b></td><td><code>{esc(r.get('from'))}</code></td><td>{coords(r.get('code'))}</td><td>{esc(r.get('shown'))}</td></tr>"
                for r in s.get("rows", [])]
        extra = "".join(f'<p class="note"><b>{lab}</b> {coords(s.get(key))}</p>' for lab, key in (("검증에 실패한 데이터셋이면:", "invalid"), ("파일끼리 다르면:", "conflict")) if s.get(key))
        parts.append(section("⑥", "자료 출처 — 어느 CSV 의 어느 열에서", q(s) + table(["값·판정", "CSV·열", "코드", "보이는 곳"], rows) + extra))
    if d.get("decisions"):
        rows = []
        for r in d["decisions"]:
            cls = "req" if "요청자" in str(r.get("by")) else "me"
            rows.append(f"<tr><td>{coords(r.get('what'))}</td><td><span class='tag {cls}'>{esc(r.get('by'))}</span></td><td>{coords(r.get('note'))}</td></tr>")
        parts.append(section("·", "결정 — 누가 정했나", table(["결정", "누가·언제", "메모"], rows)))
    if d.get("numbers"):
        cards = "".join(f'<div class="num"><span>{esc(n.get("value"))}</span><b>{esc(n.get("name"))}</b><code>{esc(n.get("cmd"))}</code></div>' for n in d["numbers"])
        parts.append(section("·", "외울 숫자", f'<div class="nums">{cards}</div>'))
    return parts


CSS = """
:root{--paper:#f2f4ef;--sheet:#fbfcf8;--ink:#1d2421;--soft:#58625c;--line:#d5dbd2;--brand:#24543f;--brandSoft:#e3ece5;--warn:#7a4e06;--warnSoft:#f6ecd6;--miss:#8b2a1c;--missSoft:#f5e2dd}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:1120px;margin:0 auto;padding:32px 28px 80px}
header h1{margin:0 0 4px;font-size:26px;font-weight:700}
header p{margin:0;color:var(--soft);font-size:13px}
header .problem{margin:14px 0 0;font-size:17px;color:var(--ink);background:var(--sheet);border-radius:12px;padding:14px 16px}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:16px 0 0;font-size:13px}nav a{color:var(--brand)}
h2{font-size:18px;margin:44px 0 10px;font-weight:700;display:flex;gap:10px;align-items:baseline}
h2 .no{color:var(--brand);font-size:22px}
h3{font-size:13px;margin:18px 0 8px;color:var(--soft);font-weight:600}
.q{margin:0 0 12px;color:var(--warn);background:var(--warnSoft);border-radius:8px;padding:6px 10px;font-size:14px}
code{font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--brandSoft);color:var(--brand);padding:1px 5px;border-radius:4px;word-break:break-all}
.co{display:inline}.co q{display:block;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--soft);quotes:none;margin:2px 0 4px;white-space:pre-wrap;word-break:break-all}
.co.bad code{background:var(--missSoft);color:var(--miss)}.co.bad{color:var(--miss);font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{background:var(--sheet);border-radius:12px;padding:14px 16px}.card h3{margin-top:0}
.card.ok{border-top:3px solid var(--brand)}.card.miss{border-top:3px solid var(--miss)}
.card ul,.card ol{margin:0;padding-left:20px}.card li{margin:0 0 10px}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch}
.flow i{align-self:center;color:var(--brand);font-style:normal;font-size:20px}
.step{background:var(--sheet);border-radius:12px;padding:12px 14px;flex:1 1 200px;max-width:260px}
.step p{margin:6px 0 0;font-size:14px}.step .state{color:var(--brand);font-weight:500}.step .where{font-size:12.5px}
table{width:100%;border-collapse:collapse;background:var(--sheet);border-radius:12px;overflow:hidden;font-size:14px}
th,td{text-align:left;padding:9px 12px;vertical-align:top}
th{font-size:12.5px;color:var(--soft);font-weight:600;background:var(--paper)}
tbody tr+tr td{border-top:1px solid var(--line)}
td.b{font-weight:700;color:var(--brand)}
.tag{display:inline-block;font-size:12px;padding:1px 7px;border-radius:5px;white-space:nowrap}
.tag.ok{background:var(--brandSoft);color:var(--brand)}.tag.miss{background:var(--missSoft);color:var(--miss);font-weight:600}
.tag.req{background:var(--brandSoft);color:var(--brand)}.tag.me{background:var(--warnSoft);color:var(--warn)}
.note{background:var(--sheet);border-radius:10px;padding:10px 14px;margin:10px 0 0}
.nums{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.num{background:var(--sheet);border-radius:12px;padding:14px}.num span{display:block;font-size:26px;font-weight:700;color:var(--brand);line-height:1.1}
.num b{display:block;margin:6px 0;font-weight:500}
@media (max-width:760px){.two{grid-template-columns:1fr}}
"""


def main(src="view/explain.json", dst="view/explain.html"):
    d = json.load(open(src, encoding="utf-8"))
    parts = build(d)
    nav = "".join(f'<a href="#s{n}">{n} {t}</a>' for n, t in (("①", "기준"), ("②", "흐름"), ("③", "확인·가정"), ("④", "실패·동시"), ("⑤", "조건 변경"), ("⑥", "자료 출처")))
    head = (f'<header><h1>{esc(d.get("title", "내가 만든 것"))}</h1>'
            f'<p>{datetime.now().strftime("%H:%M")} 생성 · 좌표 {stats["ok"]}개 확인'
            + (f' · <b style="color:var(--miss)">좌표 없음 {stats["bad"]}개</b>' if stats["bad"] else "") + "</p>"
            + (f'<p class="problem">{esc(d.get("problem"))}</p>' if d.get("problem") else "") + f"<nav>{nav}</nav></header>")
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    open(dst, "w", encoding="utf-8").write(
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(d.get("title", "설명"))}</title><style>{CSS}</style></head><body><main>{head}{"".join(parts)}</main></body></html>')
    print(f"{dst} · 섹션 {len(parts)} · 좌표 확인 {stats['ok']} · 좌표 없음 {stats['bad']}")
    return 1 if stats["bad"] else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
