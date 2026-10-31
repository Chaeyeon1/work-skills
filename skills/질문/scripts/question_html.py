#!/usr/bin/env python3
"""질문 JSON → view/questions.html (고르는 질문 페이지). 표준 라이브러리만, Python 3.9 이상.

사용: python3 question_html.py <질문.json>

질문.json 모양:
{
  "title": "단계 2 전에 정할 것",
  "lead": "무엇을 왜 묻는지 한두 문장",
  "questions": [
    {
      "id": "Q1",
      "title": "한 줄 질문?",
      "ctx": "쉬운 말로 상황 한두 문장",
      "table": {"caption": "자료 3줄 (data/a.csv:12-14)", "head": ["id", "값"], "rows": [["A-1", "12"]], "mark": [[0, 1]]},
      "options": [
        {"key": "A", "label": "선택지", "effect": "고르면 결과가 어떻게 바뀌나 (건수·합계)", "recommended": true,
         "table": {"caption": "A 로 하면", "head": [...], "rows": [[...]]}}
      ]
    }
  ]
}
- table.mark: 강조할 칸 [행, 열] 목록(이 질문이 가리키는 값)
- "직접 적기" 선택지와 메모 칸은 질문마다 자동으로 붙는다
- 답은 페이지 아래 상자에 모이고, '답 복사' 버튼(클립보드) 또는 상자 안 글을 선택해 복사한다
"""
import html
import json
import os
import sys

if len(sys.argv) < 2:
    sys.exit("사용: python3 question_html.py <질문.json>")
with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)


def e(s):
    return html.escape(str(s), quote=True)


def table(t):
    if not t:
        return ""
    marks = {tuple(m) for m in t.get("mark", [])}
    head = "".join("<th>%s</th>" % e(h) for h in t.get("head", []))
    rows = "".join(
        "<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="mk"' if (i, j) in marks else "", e(c)) for j, c in enumerate(r))
        for i, r in enumerate(t.get("rows", [])))
    cap = '<figcaption>%s</figcaption>' % e(t["caption"]) if t.get("caption") else ""
    return '<figure>%s<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></figure>' % (cap, head, rows)


qs = []
for q in data.get("questions", []):
    qid = e(q["id"])
    opts = []
    for o in q.get("options", []):
        k = e(o["key"])
        opts.append(
            '<label class="opt"><input type="radio" name="%s" value="%s"%s data-label="%s">'
            '<span class="ok">%s</span><span class="body"><b>%s</b>%s%s%s</span></label>' % (
                qid, k, " checked data-rec" if o.get("recommended") else "", e(o["label"]), k, e(o["label"]),
                ' <span class="rec">추천</span>' if o.get("recommended") else "",
                '<span class="eff">%s</span>' % e(o["effect"]) if o.get("effect") else "",
                table(o.get("table"))))
    opts.append(
        '<label class="opt other"><input type="radio" name="%s" value="기타" data-label="직접 적기">'
        '<span class="ok">✎</span><span class="body"><b>다른 안 (직접 적기)</b>'
        '<input class="own" type="text" placeholder="내 안을 적기" data-own="%s"></span></label>' % (qid, qid))
    qs.append(
        '<section class="q" id="%s"><h2><span class="qid">%s</span>%s</h2>%s%s<div class="opts">%s</div>'
        '<textarea class="memo" data-memo="%s" rows="2" placeholder="메모 (근거, 조건, 되물을 것)"></textarea></section>' % (
            qid, qid, e(q["title"]), '<p class="ctx">%s</p>' % e(q["ctx"]) if q.get("ctx") else "", table(q.get("table")),
            "".join(opts), qid))

key = "q-" + str(abs(hash(data.get("title", "") + "".join(q["id"] for q in data.get("questions", [])))))
doc = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>질문 · %(title)s</title>
<style>
:root{--paper:#f2f4ef;--sheet:#fbfcf8;--ink:#1d2421;--soft:#58625c;--line:#d5dbd2;--brand:#24543f;--brandSoft:#e3ece5;--warn:#7a4e06;--warnSoft:#f6ecd6}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:860px;margin:0 auto;padding:36px 24px 220px}
h1{margin:0 0 6px;font-size:24px}
.lead{margin:0 0 28px;color:var(--soft)}
.q{background:var(--sheet);border-radius:14px;padding:22px 24px;margin-bottom:18px}
.q h2{font-size:17px;margin:0 0 8px;display:flex;gap:10px;align-items:baseline}
.qid{color:var(--brand);font-weight:700;font-size:14px}
.ctx{margin:0 0 12px;color:var(--soft)}
figure{margin:10px 0 12px}
figcaption{font-size:12.5px;color:var(--soft);margin-bottom:4px}
table{border-collapse:collapse;font-size:13px;background:#fff;border-radius:8px;overflow:hidden}
th,td{padding:5px 10px;text-align:left;font-variant-numeric:tabular-nums}
th{background:var(--paper);color:var(--soft);font-weight:600}
tbody tr+tr td{border-top:1px solid var(--line)}
td.mk{background:var(--warnSoft);color:var(--warn);font-weight:700}
.opts{display:grid;gap:8px;margin-top:6px}
.opt{display:grid;grid-template-columns:28px 1fr;gap:10px;padding:12px 14px;border-radius:10px;background:#fff;cursor:pointer;border:1.5px solid transparent}
.opt input[type=radio]{position:absolute;opacity:0;pointer-events:none}
.opt .ok{width:26px;height:26px;border-radius:50%%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:var(--brand);background:var(--brandSoft)}
.opt:has(input:checked){border-color:var(--brand)}
.opt:has(input:checked) .ok{background:var(--brand);color:#fff}
.opt .body b{font-weight:600}
.rec{font-size:12px;color:var(--brand);margin-left:6px;font-weight:600}
.eff{display:block;color:var(--soft);font-size:13.5px;margin-top:2px}
.own{width:100%%;margin-top:6px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font:inherit}
.memo{width:100%%;margin-top:10px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;resize:vertical;background:#fff}
.dock{position:fixed;left:0;right:0;bottom:0;background:var(--ink);color:#eef2ec;padding:14px 24px}
.dock .in{max-width:860px;margin:0 auto;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}
.dock textarea{width:100%%;height:96px;border:0;border-radius:8px;padding:8px 10px;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:#2b3330;color:#eef2ec;resize:none}
.dock button{padding:12px 18px;border:0;border-radius:10px;background:#e3ece5;color:var(--ink);font:inherit;font-weight:700;cursor:pointer}
.dock button:hover{background:#fff}
.dock small{display:block;color:#a9b4ad;font-size:12px;margin-top:6px;text-align:right}
@media (max-width:640px){.dock .in{grid-template-columns:1fr}}
</style></head><body><main>
<h1>%(title)s</h1><p class="lead">%(lead)s</p>
%(qs)s
</main>
<div class="dock"><div class="in"><textarea id="out" readonly aria-label="답 (선택해서 복사해도 된다)"></textarea>
<div><button id="copy" type="button">답 복사</button><small id="msg">고르면 여기에 모인다</small></div></div></div>
<script>
(function(){
  var KEY=%(key)s, TITLE=%(jtitle)s;
  var store={get:function(){try{return JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){return {}}},set:function(v){try{localStorage.setItem(KEY,JSON.stringify(v))}catch(e){}}};
  var qs=[].slice.call(document.querySelectorAll(".q"));
  function collect(){
    var lines=["["+TITLE+" 답]"], save={};
    qs.forEach(function(q){
      var id=q.id, t=q.querySelector("h2").textContent.replace(id,"").trim();
      var c=q.querySelector("input[type=radio]:checked"), own=q.querySelector(".own").value.trim(), memo=q.querySelector(".memo").value.trim();
      var pick=c?(c.value==="기타"?"직접: "+(own||"(비어 있음)"):c.value+" "+c.dataset.label):"(안 고름)";
      lines.push(id+" "+t+" → "+pick+(memo?" / 메모: "+memo:""));
      save[id]={v:c?c.value:"",own:own,memo:memo};
    });
    document.getElementById("out").value=lines.join("\\n");
    store.set(save);
  }
  var saved=store.get();
  qs.forEach(function(q){
    var s=saved[q.id];
    if(s){ if(s.v){var r=q.querySelector('input[type=radio][value="'+s.v+'"]'); if(r) r.checked=true;}
           q.querySelector(".own").value=s.own||""; q.querySelector(".memo").value=s.memo||""; }
    q.addEventListener("change",collect); q.addEventListener("input",collect);
    var own=q.querySelector(".own");
    own.addEventListener("focus",function(){q.querySelector('input[value="기타"]').checked=true;collect();});
    q.querySelector('input[value="기타"]').addEventListener("change",function(){own.focus();});
  });
  collect();
  document.getElementById("copy").addEventListener("click",function(){
    var out=document.getElementById("out"), msg=document.getElementById("msg");
    var settled=false;
    function done(){settled=true;msg.textContent="복사했다 · 에이전트에게 붙여 넣기";}
    function fallback(){if(settled)return;settled=true;out.focus();out.select();var ok=false;try{ok=document.execCommand("copy");}catch(e){}
      msg.textContent=ok?"복사했다 · 에이전트에게 붙여 넣기":"글을 선택해 두었다 · ⌘C 로 복사";}
    if(navigator.clipboard&&window.isSecureContext){
      setTimeout(fallback,700);  /* 권한 요청이 끝나지 않는 환경 */
      navigator.clipboard.writeText(out.value).then(function(){if(!settled)done();},fallback);
    }else{fallback();}
  });
})();
</script></body></html>
""" % {"title": e(data.get("title", "질문")), "lead": e(data.get("lead", "")), "qs": "".join(qs),
       "key": json.dumps(key), "jtitle": json.dumps(data.get("title", "질문"), ensure_ascii=False)}

os.makedirs("view", exist_ok=True)
with open(os.path.join("view", "questions.html"), "w", encoding="utf-8") as f:
    f.write(doc)
print("→ view/questions.html  (질문 %d개)" % len(data.get("questions", [])))
