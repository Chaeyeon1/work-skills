"""과제 한 장 (코드 전) — view/brief.json → view/brief.html

python3 brief_html.py [view/brief.json] [view/brief.html]   (작업 폴더 맨 위에서)

`$파악` 직후, 코드를 만들기 전에 사용자가 과제를 이해하려고 읽는 그림. 모양·좌표 처리는 explain_html.py 와 같다
(`README.md:12`·`data/provided/a.csv:3` 처럼 쓴 좌표마다 그 줄 원문을 붙이고, 없으면 빨간 '좌표 없음' · 종료 1).
json 모양 (칸은 짧은 명사구. 없는 칸은 빼도 된다):
{
 "title": "과제 이름", "oneline": "누가 · 언제 · 무엇에 쓰는 무엇",
 "asks": [{"what": "만들 것·요구", "where": "README.md:40"}],
 "out_of_scope": ["범위 밖 항목 그대로"],
 "data": [{"file": "data/provided/a.csv", "rows": "데이터 행 수(코드로 센 값)", "key": "key 열", "what": "한 줄", "links": "b.csv 의 a_id → a.id"}],
 "flow": [{"who": "운영자", "step": "데이터셋 적용", "what": "하는 일 한 줄"}],
 "rules": [{"rule": "규칙·제약", "where": "README.md:52", "status": "README | 자료에서 읽음 | 미확인(물을 것)"}],
 "traps": [{"what": "이상한 점·숨은 규칙 후보", "where": "파일:줄", "ask": "물을 것"}],
 "ask_first": ["★ 먼저 물을 것 (AGENTS [파악] 줄과 같은 말)"],
 "words": [{"word": "용어", "means": "뜻 (출처 좌표)"}],
 "env": "환경 터미널이 지금 깔고 있는 것 한 줄"
}
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from explain_html import CSS, coords, esc, section, stats, status, table  # noqa: E402


def build(d):
    parts = []
    if d.get("asks") or d.get("out_of_scope"):
        rows = [f'<tr><td>{esc(a.get("what"))}</td><td>{coords(a.get("where"))}</td></tr>' for a in d.get("asks", [])]
        body = table(["만들 것", "근거"], rows) if rows else ""
        if d.get("out_of_scope"):
            body += '<div class="note"><b>범위 밖</b> — ' + " · ".join(esc(x) for x in d["out_of_scope"]) + "</div>"
        parts.append(section("①", "무엇을 만드나", body))
    if d.get("data"):
        rows = [f'<tr><td class="b">{coords(x.get("file"))}</td><td>{esc(x.get("rows"))}</td><td>{esc(x.get("key"))}</td>'
                f'<td>{coords(x.get("what"))}</td><td>{coords(x.get("links"))}</td></tr>' for x in d["data"]]
        parts.append(section("②", "자료 지도", table(["파일", "행", "key", "무엇", "이어지는 곳"], rows)))
    if d.get("flow"):
        steps = '<i>→</i>'.join(f'<div class="step"><b>{esc(s.get("step"))}</b><p class="state">{esc(s.get("who"))}</p>'
                                f'<p>{coords(s.get("what"))}</p></div>' for s in d["flow"])
        parts.append(section("③", "누가 어떤 순서로 쓰나", f'<div class="flow">{steps}</div>'))
    if d.get("rules"):
        rows = [f'<tr><td>{esc(r.get("rule"))}</td><td>{coords(r.get("where"))}</td><td>{status(r.get("status"))}</td></tr>' for r in d["rules"]]
        parts.append(section("④", "규칙", table(["규칙", "근거", "상태"], rows)))
    if d.get("traps") or d.get("ask_first"):
        body = ""
        if d.get("ask_first"):
            body += '<div class="card miss"><h3>먼저 물을 것</h3><ol>' + "".join(f"<li>{coords(x)}</li>" for x in d["ask_first"]) + "</ol></div>"
        if d.get("traps"):
            rows = [f'<tr><td>{esc(t.get("what"))}</td><td>{coords(t.get("where"))}</td><td>{esc(t.get("ask"))}</td></tr>' for t in d["traps"]]
            body += '<div style="margin-top:12px">' + table(["이상한 점", "근거", "물을 것"], rows) + "</div>"
        parts.append(section("⑤", "함정 후보와 물을 것", body))
    if d.get("words"):
        rows = [f'<tr><td class="b">{esc(w.get("word"))}</td><td>{coords(w.get("means"))}</td></tr>' for w in d["words"]]
        parts.append(section("⑥", "용어", table(["용어", "뜻"], rows)))
    return parts


def main(src="view/brief.json", dst="view/brief.html"):
    d = json.load(open(src, encoding="utf-8"))
    parts = build(d)
    head = (f'<header><h1>{esc(d.get("title", "과제"))}</h1>'
            f'<p>{datetime.now().strftime("%H:%M")} 생성 · 코드 전 · 좌표 {stats["ok"]}개 확인'
            + (f' · <b style="color:var(--miss)">좌표 없음 {stats["bad"]}개</b>' if stats["bad"] else "") + "</p>"
            + (f'<p class="problem">{esc(d.get("oneline"))}</p>' if d.get("oneline") else "")
            + (f'<div class="note">환경 터미널: {esc(d.get("env"))}</div>' if d.get("env") else "") + "</header>")
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    open(dst, "w", encoding="utf-8").write(
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(d.get("title", "과제"))}</title><style>{CSS}</style></head><body><main>{head}{"".join(parts)}</main></body></html>')
    print(f"{dst} · 섹션 {len(parts)} · 좌표 확인 {stats['ok']} · 좌표 없음 {stats['bad']}")
    return 1 if stats["bad"] else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
