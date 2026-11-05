"""과제 한 장 (코드 전) — view/brief.json → view/brief.html

python3 brief_html.py [view/brief.json] [view/brief.html]   (작업 폴더 맨 위에서)

`$파악` 직후, 코드를 만들기 전에 사용자가 과제 전체를 한눈에 잡으려고 읽는 그림.
좌표 처리는 explain_html.py 와 같다(`README.md:12`·`data/provided/a.csv:3` 처럼 쓴 좌표마다 그 줄 원문을 붙이고,
없으면 빨간 '좌표 없음' · 종료 1).
json 모양 (칸은 짧은 명사구. 없는 칸은 빼도 된다):
{
 "title": "과제 이름", "oneline": "누가 · 언제 · 무엇에 쓰는 무엇",
 "asks": [{"what": "만들 것·요구", "where": "README.md:40"}],
 "out_of_scope": ["범위 밖 항목 그대로"],
 "data": [{"file": "data/provided/a.csv", "rows": "데이터 행 수(코드로 센 값)", "key": "key 열", "what": "한 줄",
           "refs": [{"col": "b_id", "to": "data/provided/b.csv"}]}],
 "flow": [{"who": "운영자", "step": "데이터셋 적용", "what": "하는 일 한 줄"}],
 "rules": [{"rule": "규칙·제약", "where": "README.md:52", "status": "README | 자료에서 읽음 | 미확인(물을 것)"}],
 "traps": [{"what": "이상한 점·숨은 규칙 후보", "why": "왜 함정인가: 글자 그대로 하면 무엇이 틀리나",
            "count": "걸리는 건수(명령으로 센 값, 없으면 빼기)", "where": "파일:줄", "ask": "물을 것"}],
 "conflicts": [{"topic": "무엇이 부딪히나",
                "a": {"src": "README", "says": "말한 것", "where": "README.md:30"},
                "b": {"src": "data/provided/a.csv", "says": "자료가 보여 주는 것", "where": "data/provided/a.csv:8"},
                "diff": "어디가 다른가 한 줄", "ask": "물을 것", "now": "답 전까지 어느 쪽을 따르나 | 미정"}],
 "ask_first": [{"q": "★ 먼저 물을 것 (AGENTS [파악] 줄과 같은 말)", "changes": "이 답이 바꾸는 것"}],
 "words": [{"word": "용어", "means": "뜻 (출처 좌표)"}],
 "env": "환경 터미널이 지금 깔고 있는 것 한 줄"
}
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from explain_html import CSS as BASE_CSS, coords, esc, stats  # noqa: E402


def kind(status):
    t = str(status or "")
    if not t or "미확인" in t or "물을" in t:
        return "miss"
    if "자료" in t:
        return "data"
    return "doc"


def short(path):
    return os.path.basename(str(path or ""))


# ---------- ② 자료 지도: 표를 상자로, refs 를 선으로 ----------
def data_map(items):
    n = len(items)
    cols = 1 if n == 1 else 2 if n <= 4 else 3
    bw, bh, gx, gy, pad = 250, 92, 130, 56, 14
    pos = {}
    for i, x in enumerate(items):
        r, c = divmod(i, cols)
        pos[short(x.get("file"))] = (pad + c * (bw + gx), pad + r * (bh + gy))
    rows = (n + cols - 1) // cols
    W = pad * 2 + cols * bw + (cols - 1) * gx
    H = pad * 2 + rows * bh + (rows - 1) * gy
    edges, boxes, missing = [], [], []
    for x in items:
        src = short(x.get("file"))
        for ref in x.get("refs", []) or []:
            dst = short(ref.get("to"))
            if dst not in pos:
                missing.append(f"{src}.{ref.get('col')} → {dst}")
                continue
            (x1, y1), (x2, y2) = pos[src], pos[dst]
            if y1 == y2:  # 같은 줄: 옆으로
                a, b = (x1 + bw, y1 + bh / 2), (x2, y2 + bh / 2)
                if x2 < x1:
                    a, b = (x1, y1 + bh / 2), (x2 + bw, y2 + bh / 2)
                mx = (a[0] + b[0]) / 2
                d = f"M{a[0]},{a[1]} C{mx},{a[1]} {mx},{b[1]} {b[0]},{b[1]}"
                lx, ly, anc = mx, a[1] - 10, "middle"
            else:  # 위아래: 아래쪽 가장자리에서
                a = (x1 + bw / 2, y1 + bh) if y2 > y1 else (x1 + bw / 2, y1)
                b = (x2 + bw / 2, y2) if y2 > y1 else (x2 + bw / 2, y2 + bh)
                my = (a[1] + b[1]) / 2
                d = f"M{a[0]},{a[1]} C{a[0]},{my} {b[0]},{my} {b[0]},{b[1]}"
                lx, ly, anc = (a[0] + b[0]) / 2 + 8, my + 4, "start"
            edges.append(f'<path d="{d}" class="ln" marker-end="url(#arr)"/>'
                         f'<text x="{lx}" y="{ly}" class="lb" text-anchor="{anc}">{esc(ref.get("col"))}</text>')
    for x in items:
        bx, by = pos[short(x.get("file"))]
        boxes.append(
            f'<g><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="10" class="bx"/>'
            f'<text x="{bx + 14}" y="{by + 26}" class="nm">{esc(short(x.get("file")))}</text>'
            f'<text x="{bx + bw - 14}" y="{by + 26}" class="rw" text-anchor="end">{esc(x.get("rows"))}행</text>'
            f'<text x="{bx + 14}" y="{by + 50}" class="ky">key {esc(x.get("key") or "없음")}</text>'
            f'<text x="{bx + 14}" y="{by + 74}" class="wh">{esc(str(x.get("what") or "")[:24])}</text></g>')
    svg = (f'<div class="mapwrap"><svg viewBox="0 0 {W} {H}" width="{W}" role="img" aria-label="자료 지도">'
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M0,1 L9,5 L0,9 z" class="ah"/></marker></defs>'
           f'{"".join(edges)}{"".join(boxes)}</svg></div>')
    if missing:
        svg += '<p class="warnline">지도에 없는 표를 가리키는 열: ' + " · ".join(esc(m) for m in missing) + "</p>"
    rows_html = "".join(
        f'<tr><td class="b">{coords(x.get("file"))}</td><td>{coords(x.get("what"))}</td>'
        f'<td>{" · ".join(esc(r.get("col")) + " → " + esc(short(r.get("to"))) for r in x.get("refs", []) or []) or "없음"}</td></tr>'
        for x in items)
    return svg + f'<details><summary>표로 보기 · 좌표</summary><table><thead><tr><th>파일</th><th>무엇</th><th>이어지는 열</th></tr></thead><tbody>{rows_html}</tbody></table></details>'


# ---------- ③ 흐름: 역할마다 한 줄 ----------
def flow_lanes(steps):
    lanes = []
    for s in steps:
        if s.get("who") not in lanes:
            lanes.append(s.get("who"))
    n = len(steps)
    cells = []
    for li, who in enumerate(lanes):
        cells.append(f'<div class="lane" style="grid-row:{li + 1};grid-column:1">{esc(who)}</div>')
        cells.append(f'<div class="track" style="grid-row:{li + 1};grid-column:2/{n + 2}"></div>')
    for i, s in enumerate(steps):
        li = lanes.index(s.get("who"))
        cells.append(f'<div class="st" style="grid-row:{li + 1};grid-column:{i + 2}"><span class="sn">{i + 1}</span>'
                     f'<b>{esc(s.get("step"))}</b><p>{coords(s.get("what"))}</p></div>')
    return (f'<div class="lanes" style="grid-template-columns:96px repeat({n}, minmax(150px, 1fr));'
            f'grid-template-rows:repeat({len(lanes)}, auto)">{"".join(cells)}</div>'
            '<p class="hint">번호 순서대로 일이 넘어간다. 줄이 바뀌는 곳이 역할이 바뀌는 곳(넘겨받는 화면·권한이 필요한 곳).</p>')


# ---------- ④ 규칙: 출처별 세 칸 ----------
def rule_columns(rules):
    groups = {"doc": [], "data": [], "miss": []}
    for r in rules:
        groups[kind(r.get("status"))].append(r)
    title = {"doc": "README 에 적힘", "data": "자료에서 읽음", "miss": "아직 모름 · 물어야 함"}
    out = []
    for k in ("doc", "data", "miss"):
        items = "".join(f'<li><span>{esc(r.get("rule"))}</span><small>{coords(r.get("where"))}</small></li>' for r in groups[k])
        out.append(f'<div class="rc {k}"><h3>{title[k]} <em>{len(groups[k])}</em></h3><ul>{items or "<li class=none>없음</li>"}</ul></div>')
    return f'<div class="rcols">{"".join(out)}</div>'


# ---------- ⑤ 함정: 왜 함정인지 ----------
def trap_cards(traps):
    out = []
    for i, t in enumerate(traps, 1):
        cnt = f'<div class="cnt"><b>{esc(t.get("count"))}</b><span>걸리는 건수</span></div>' if t.get("count") else ""
        out.append(
            f'<article class="trap"><header><span class="tn">{i}</span><h3>{esc(t.get("what"))}</h3>{cnt}</header>'
            f'<div class="why"><b>왜 함정</b><p>{coords(t.get("why") or "적지 않음")}</p></div>'
            f'<dl><dt>근거</dt><dd>{coords(t.get("where"))}</dd><dt>물을 것</dt><dd>{esc(t.get("ask") or "없음")}</dd></dl></article>')
    return f'<div class="traps">{"".join(out)}</div>'


# ---------- ⑥ 충돌: 양옆 비교 ----------
def conflict_rows(cs):
    out = []
    for c in cs:
        a, b = c.get("a", {}), c.get("b", {})
        now = c.get("now") or "미정"
        out.append(
            f'<article class="cf"><h3>{esc(c.get("topic"))}</h3>'
            f'<div class="vs"><div class="side"><span class="src">{esc(a.get("src"))}</span><p>{esc(a.get("says"))}</p><small>{coords(a.get("where"))}</small></div>'
            f'<div class="mid">≠</div>'
            f'<div class="side"><span class="src">{esc(b.get("src"))}</span><p>{esc(b.get("says"))}</p><small>{coords(b.get("where"))}</small></div></div>'
            f'<div class="cfoot"><p><b>다른 곳</b>{esc(c.get("diff"))}</p><p><b>물을 것</b>{esc(c.get("ask") or "없음")}</p>'
            f'<p class="{"miss" if "미정" in now else ""}"><b>답 전까지</b>{esc(now)}</p></div></article>')
    return "".join(out)


def ask_list(items):
    li = []
    for x in items:
        x = x if isinstance(x, dict) else {"q": x}
        ch = f'<small>이 답이 바꾸는 것: {esc(x.get("changes"))}</small>' if x.get("changes") else ""
        li.append(f'<li><span>{coords(x.get("q"))}</span>{ch}</li>')
    return f'<ol class="asks">{"".join(li)}</ol>'


def section(sid, no, title, body, sub=""):
    s = f'<p class="sub">{esc(sub)}</p>' if sub else ""
    return f'<section id="{sid}"><h2><span class="no">{no}</span>{esc(title)}</h2>{s}{body}</section>'


def build(d):
    parts, nav = [], []

    def add(sid, no, title, body, sub=""):
        parts.append(section(sid, no, title, body, sub))
        nav.append(f'<a href="#{sid}">{no} {esc(title)}</a>')

    if d.get("asks") or d.get("out_of_scope"):
        rows = "".join(f'<li><span>{esc(a.get("what"))}</span><small>{coords(a.get("where"))}</small></li>' for a in d.get("asks", []))
        body = f'<ol class="make">{rows}</ol>'
        if d.get("out_of_scope"):
            body += '<div class="oos"><b>만들지 않는 것</b>' + "".join(f"<span>{esc(x)}</span>" for x in d["out_of_scope"]) + "</div>"
        add("make", "①", "무엇을 만드나", body)
    if d.get("data"):
        add("data", "②", "자료 지도", data_map(d["data"]), "화살표 = 이 열의 값이 저 표의 key 를 가리킨다")
    if d.get("flow"):
        add("flow", "③", "누가 어떤 순서로 쓰나", flow_lanes(d["flow"]))
    if d.get("rules"):
        add("rules", "④", "규칙", rule_columns(d["rules"]), "오른쪽 칸이 비어야 계획서를 쓸 수 있다")
    if d.get("traps"):
        add("traps", "⑤", "함정 후보", trap_cards(d["traps"]), "글자 그대로 만들면 틀리는 곳")
    if d.get("conflicts"):
        add("conflicts", "⑥", "부딪히는 곳", conflict_rows(d["conflicts"]), "두 출처가 다르게 말하는 곳. 어느 쪽을 믿을지는 요청자에게")
    if d.get("ask_first"):
        add("ask", "⑦", "먼저 물을 것", ask_list(d["ask_first"]))
    if d.get("words"):
        rows = "".join(f'<tr><td class="b">{esc(w.get("word"))}</td><td>{coords(w.get("means"))}</td></tr>' for w in d["words"])
        add("words", "⑧", "용어", f'<table><tbody>{rows}</tbody></table>')
    return parts, nav


def strip(d):
    rules = d.get("rules", [])
    miss = sum(1 for r in rules if kind(r.get("status")) == "miss")
    cells = [("만들 것", len(d.get("asks", [])), ""), ("자료 표", len(d.get("data", [])), ""),
             ("규칙", len(rules), ""), ("모르는 규칙", miss, "miss" if miss else ""),
             ("함정 후보", len(d.get("traps", [])), "warn" if d.get("traps") else ""),
             ("부딪히는 곳", len(d.get("conflicts", [])), "miss" if d.get("conflicts") else "")]
    return '<div class="strip">' + "".join(f'<div class="{k}"><b>{v}</b><span>{esc(n)}</span></div>' for n, v, k in cells) + "</div>"


CSS = BASE_CSS + """
header .meta{display:flex;flex-wrap:wrap;gap:4px 16px}
.envline{margin:10px 0 0;font-size:13px;color:var(--soft)}
nav.top{position:sticky;top:0;z-index:2;background:var(--paper);padding:10px 0;margin:18px 0 0;border-bottom:1px solid var(--line)}
.sub{margin:-4px 0 12px;color:var(--soft);font-size:13.5px}
.hint{margin:8px 0 0;color:var(--soft);font-size:13px}
.strip{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:16px 0 0}
.strip div{background:var(--sheet);border-radius:10px;padding:10px 12px}
.strip b{display:block;font-size:24px;line-height:1.15;color:var(--brand);font-variant-numeric:tabular-nums}
.strip span{font-size:12.5px;color:var(--soft)}
.strip .miss b{color:var(--miss)}.strip .warn b{color:var(--warn)}
ol.make,ol.asks{margin:0;padding:0;list-style:none;counter-reset:k;display:grid;gap:6px}
ol.make li,ol.asks li{counter-increment:k;background:var(--sheet);border-radius:10px;padding:10px 14px 10px 44px;position:relative}
ol.make li::before,ol.asks li::before{content:counter(k);position:absolute;left:14px;top:10px;font-weight:700;color:var(--brand);font-variant-numeric:tabular-nums}
ol.make small,ol.asks small{display:block;color:var(--soft);font-size:12.5px;margin-top:2px}
ol.asks li::before{color:var(--miss)}
.oos{margin:10px 0 0;font-size:14px;color:var(--soft)}.oos b{color:var(--ink);margin-right:8px}
.oos span{text-decoration:line-through;text-decoration-color:var(--miss);margin-right:12px}
.mapwrap{background:var(--sheet);border-radius:12px;padding:8px;overflow-x:auto}
.mapwrap svg{display:block;max-width:100%;height:auto;margin:0 auto}
.bx{fill:var(--paper);stroke:var(--brand);stroke-opacity:.35}
.nm{font-weight:700;font-size:14px;fill:var(--ink)}.rw{font-size:13px;fill:var(--brand);font-weight:600}
.ky{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;fill:var(--brand)}.wh{font-size:12.5px;fill:var(--soft)}
.ln{fill:none;stroke:var(--brand);stroke-width:1.6;stroke-linecap:round;opacity:.7}.ah{fill:var(--brand)}
.lb{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;fill:var(--warn);paint-order:stroke;stroke:var(--sheet);stroke-width:4px;stroke-linejoin:round}
.warnline{color:var(--miss);font-size:13px}
details{margin:10px 0 0}summary{cursor:pointer;color:var(--brand);font-size:13.5px;margin-bottom:8px}
.lanes{display:grid;gap:8px 10px;overflow-x:auto;padding-bottom:4px}
.lane{align-self:center;font-weight:700;font-size:14px;color:var(--brand)}
.track{background:var(--sheet);border-radius:10px;opacity:.6}
.st{position:relative;z-index:1;background:var(--sheet);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:6px 0}
.st b{display:block;font-size:14px}.st p{margin:4px 0 0;font-size:13px;color:var(--soft)}
.sn{display:block;font-size:13px;font-weight:700;color:var(--brand);font-variant-numeric:tabular-nums;margin-bottom:2px}
.rcols{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.rc{background:var(--sheet);border-radius:12px;padding:12px 14px}
.rc h3{margin:0 0 8px;font-size:14px;display:flex;justify-content:space-between}.rc h3 em{font-style:normal;font-variant-numeric:tabular-nums}
.rc.doc h3{color:var(--brand)}.rc.data h3{color:var(--warn)}.rc.miss h3{color:var(--miss)}
.rc.miss{background:var(--missSoft)}
.rc ul{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.rc li span{display:block;font-size:14px}.rc li small{font-size:12px;color:var(--soft)}.rc li.none{color:var(--soft);font-size:13px}
.traps{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.trap{background:var(--sheet);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:10px}
.trap header{display:flex;gap:10px;align-items:flex-start}
.trap h3{margin:0;font-size:15px;flex:1}
.tn{font-weight:700;color:var(--warn);font-variant-numeric:tabular-nums}
.cnt{text-align:right}.cnt b{display:block;font-size:20px;line-height:1.1;color:var(--warn)}.cnt span{font-size:11.5px;color:var(--soft)}
.why{background:var(--warnSoft);border-radius:8px;padding:8px 12px}
.why b{font-size:12.5px;color:var(--warn)}.why p{margin:2px 0 0;font-size:14px}
.trap dl{margin:0;display:grid;grid-template-columns:56px 1fr;gap:4px 8px;font-size:13.5px}
.trap dt{color:var(--soft)}.trap dd{margin:0}
.cf{background:var(--sheet);border-radius:12px;padding:14px 16px;margin:0 0 10px}
.cf h3{margin:0 0 10px;font-size:15px}
.vs{display:grid;grid-template-columns:1fr 36px 1fr;align-items:stretch}
.side{background:var(--paper);border-radius:10px;padding:10px 12px;display:flex;flex-direction:column}
.side .src{font-size:12.5px;font-weight:700;color:var(--brand)}
.side p{margin:4px 0 6px;font-size:14.5px;flex:1}.side small{font-size:12px}
.mid{display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:var(--miss)}
.cfoot{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 0;font-size:13.5px}
.cfoot p{margin:0}.cfoot b{display:block;font-size:12px;color:var(--soft)}
.cfoot p.miss{color:var(--miss);font-weight:600}
@media (max-width:860px){.strip{grid-template-columns:repeat(3,1fr)}.rcols,.traps,.cfoot{grid-template-columns:1fr}.vs{grid-template-columns:1fr;gap:6px}.mid{transform:rotate(90deg)}}
@media (max-width:520px){main{padding:20px 16px 60px}}
"""


def main(src="view/brief.json", dst="view/brief.html"):
    d = json.load(open(src, encoding="utf-8"))
    parts, nav = build(d)
    head = (f'<header><h1>{esc(d.get("title", "과제"))}</h1>'
            f'<p class="meta"><span>{datetime.now().strftime("%H:%M")} 생성 · 코드 전</span><span>좌표 {stats["ok"]}개 원문 확인</span>'
            + (f'<b style="color:var(--miss)">좌표 없음 {stats["bad"]}개</b>' if stats["bad"] else "") + "</p>"
            + (f'<p class="problem">{esc(d.get("oneline"))}</p>' if d.get("oneline") else "")
            + strip(d)
            + (f'<p class="envline">환경 터미널: {esc(d.get("env"))}</p>' if d.get("env") else "")
            + f'</header><nav class="top">{"".join(nav)}</nav>')
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    open(dst, "w", encoding="utf-8").write(
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(d.get("title", "과제"))}</title><style>{CSS}</style></head><body><main>{head}{"".join(parts)}</main></body></html>')
    print(f"{dst} · 섹션 {len(parts)} · 좌표 확인 {stats['ok']} · 좌표 없음 {stats['bad']}")
    return 1 if stats["bad"] else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
