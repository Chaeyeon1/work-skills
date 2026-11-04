"""계산 — 요청마다 채우는 곳 (2/2). 아래는 예시 자료용 예시 계산이다. 통째로 바꾼다.

generate(data, params) 는 DB·시각·전역 상태를 읽지 않는다(같은 입력 → 같은 결과). 돌려줄 모양(화면 약속):
  summary  {이름: 값}                            운영자 화면 맨 위 숫자
  issues   [{"what", "where"}]                   '확인 필요'. 하나라도 있으면 결재·공개에 확인 체크가 필요하다
  rows     [{열: 값}]                            운영자 전체 표 (열 순서 = 첫 행의 키 순서)
  graph    {"nodes": [{"id","label","x","y","group"}], "edges": [{"from","to","label","group"}]}
  members  {아이디: [{"date","start","end","where","what","next","next_min","nodes"}]}   두 번째 역할 화면
           (nodes = 그래프에서 강조할 노드 id 목록. date = 묶는 날짜(자정을 넘는 구간은 시작한 날).
            그 구간 안에서 다음 날 새벽에 시작하는 항목은 "day" 에 실제 달력 날짜를 따로 넣는다)
  export   EXPORT_SCHEMA 모양 그대로
규칙을 옮긴 곳에 `# 규칙 N`. 빠지는 대상은 조용히 버리지 말고 issues 에 남긴다.
"""
from . import clock


def finish_export(export, meta):
    """내보내기 직전에 한 번. meta = {plan_id, dataset, digest, created_at} (CLI 는 plan_id·created_at 이 None).
    EXPORT_SCHEMA 에 머리 칸(계획 번호·데이터셋·만든 시각)이 있으면 여기서 채운다."""
    return export


def generate(data, params):
    places = {p["place_id"]: p for p in data["places"]}
    people = {p["person_id"]: p for p in data["people"]}
    minutes = {(l["from_id"], l["to_id"]): l["minutes"] for l in data["links"]}
    cap = {k: min(p["capacity"], params["max_per_place"] or p["capacity"]) for k, p in places.items()}
    period = set(clock.days(params["date_from"], params["date_to"]))

    rows, issues, members, out = [], [], {k: [] for k in people}, []
    slots = sorted((s for s in data["slots"] if s["date"] in period and s["status"] == "work"),
                   key=lambda s: (s["date"], s["start"], s["person_id"]))
    used, left = {}, []
    for s in slots:
        who = people[s["person_id"]]
        key = (s["date"], s["start"])
        home = who["home_place"]
        order = [home] + sorted((k for k in places if k != home), key=lambda k: minutes.get((home, k), 10**9))
        place = next((k for k in order if used.get((key, k), 0) < cap[k]), None)
        if place is None:
            issues.append({"what": "자리 없음", "where": f"{s['date']} {s['start']} {who['name']}"})
            left.append({"date": s["date"], "person_id": who["person_id"], "start": s["start"], "reason": "자리 없음"})
            continue
        used[(key, place)] = used.get((key, place), 0) + 1
        moved = place != home
        rows.append({"날짜": s["date"], "시작": s["start"], "끝": s["end"], "이름": who["name"],
                     "자리": places[place]["name"], "기본 자리에서 옮김": "예" if moved else ""})
        members[who["person_id"]].append({"date": s["date"], "start": s["start"], "end": s["end"],
                                          "where": places[place]["name"], "what": "배정" if not moved else "옮겨 배정",
                                          "place_id": place, "nodes": [place]})
        out.append({"date": s["date"], "person_id": who["person_id"], "place_id": place,
                    "start": s["start"], "end": s["end"]})

    for (key, place), n in sorted(used.items()):
        leads = sum(1 for o in out if (o["date"], o["start"]) == key and o["place_id"] == place
                    and people[o["person_id"]]["lead"])
        if leads == 0:
            issues.append({"what": "책임자 없음", "where": f"{key[0]} {key[1]} {places[place]['name']}"})

    for items in members.values():
        for a, b in zip(items, items[1:] + [None]):
            a["next"] = b["where"] if b else ""
            a["next_min"] = minutes.get((a["place_id"], b["place_id"])) if b and b["place_id"] != a["place_id"] else (0 if b else None)

    graph = {"nodes": [{"id": k, "label": p["name"], "x": p["x"], "y": p["y"], "group": "자리"} for k, p in places.items()],
             "edges": [{"from": a, "to": b, "label": f"{m}분", "group": "길"} for (a, b), m in minutes.items() if a < b]}
    summary = {"기간": f"{params['date_from']} ~ {params['date_to']}", "배정": len(out), "확인 필요": len(issues),
               "옮긴 배정": sum(1 for r in rows if r["기본 자리에서 옮김"])}
    return {"summary": summary, "issues": issues, "rows": rows, "graph": graph, "members": members,
            "export": {"params": params, "assignments": out, "unassigned": left}}
