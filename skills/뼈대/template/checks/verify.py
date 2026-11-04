"""독립 검사기 — app/ 를 import 하지 않는다. 원본 CSV 와 내보낸 JSON 만 읽는다.

python3 checks/verify.py out/export.json [data/provided]
규칙마다 '위반 k / 대상 n' 을 찍고, 위반이 있으면 종료 코드 1. 아래 규칙은 예시 자료용이다. 확정된 규칙으로 바꾼다.
규칙 문장이 두 가지로 읽히면 NOTES 결정 쪽으로 세고, 다른 읽기로 달라지는 건수를 '다른 읽기' 줄로 따로 찍는다.
"""
import csv
import json
import sys
from collections import Counter
from datetime import date, timedelta

RULES = []


def rule(name):
    def deco(f):
        RULES.append((name, f))
        return f
    return deco


def load(folder, name):
    with open(f"{folder}/{name}", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def period(ex):
    d, end = date.fromisoformat(ex["params"]["date_from"]), date.fromisoformat(ex["params"]["date_to"])
    out = set()
    while d <= end:
        out.add(d.isoformat())
        d += timedelta(days=1)
    return out


@rule("규칙 1 자리마다 같은 시간 인원 ≤ 정원")
def capacity(ex, src):
    cap = {r["place_id"]: int(r["capacity"]) for r in src["places"]}
    lim = ex["params"].get("max_per_place")
    n = Counter((a["date"], a["start"], a["place_id"]) for a in ex["assignments"])
    bad = [f"{k} {v}명 > {min(cap[k[2]], lim or cap[k[2]])}" for k, v in n.items() if v > min(cap[k[2]], lim or cap[k[2]])]
    return bad, len(n)


@rule("규칙 2 기간 안 work 행은 배정되거나 '자리 없음' 으로 남는다(빠짐 없음)")
def coverage(ex, src):
    days = period(ex)
    want = {(r["date"], r["person_id"], r["start"]) for r in src["slots"] if r["status"] == "work" and r["date"] in days}
    got = Counter((a["date"], a["person_id"], a["start"]) for a in ex["assignments"])
    left = {(u["date"], u["person_id"], u["start"]) for u in ex["unassigned"]}
    bad = [f"{k} 빠짐(배정도 '자리 없음'도 아님)" for k in sorted(want - set(got) - left)]
    bad += [f"{k} {v}번 배정" for k, v in got.items() if v > 1]
    return bad, len(want)


@rule("규칙 3 쉬는 사람·기간 밖 날짜는 배정하지 않는다")
def no_off(ex, src):
    work = {(r["date"], r["person_id"], r["start"]) for r in src["slots"] if r["status"] == "work"}
    days = period(ex)
    bad = [f"{a['date']} {a['person_id']}" for a in ex["assignments"]
           if (a["date"], a["person_id"], a["start"]) not in work or a["date"] not in days]
    return bad, len(ex["assignments"])


def main(path, folder="data/provided"):
    ex = json.load(open(path, encoding="utf-8"))
    src = {n: load(folder, f"{n}.csv") for n in ("places", "people", "slots", "links")}
    total = 0
    for name, f in RULES:
        bad, n = f(ex, src)
        total += len(bad)
        print(f"{'위반' if bad else '통과'} {len(bad)} / 대상 {n} — {name}")
        for b in bad[:5]:
            print("   ", b)
    print(f"합계 위반 {total} (규칙 {len(RULES)}개)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
