"""데이터셋 읽기·검증 — 고치지 않는 곳. 열 형식은 spec.FILES 에서.

read_dir(폴더) → {표: 원문}      원문을 그대로 DB 에 넣는다(재시작·재현용)
parse(원문들) → (data, errors)    errors 가 하나라도 있으면 data 는 None. 적용하지 않는다.
"""
import csv
import io
import os
import re
from datetime import date

from . import spec

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def read_dir(path):
    out = {}
    for t, f in spec.FILES.items():
        p = os.path.join(path, f["file"])
        out[t] = open(p, encoding="utf-8-sig").read() if os.path.exists(p) else None
    return out


def _cast(kind, v):
    if kind == "id" or kind == "str":
        if v.strip() != v:
            raise ValueError("앞뒤 공백")
        return v
    if kind == "int":
        return int(v)
    if kind == "num":
        return float(v)
    if kind == "date":
        date.fromisoformat(v)
        if len(v) != 10:
            raise ValueError("YYYY-MM-DD 아님")
        return v
    if kind == "time":
        if not _TIME.match(v):
            raise ValueError("HH:MM 아님")
        return v
    if kind == "yn":
        if v not in ("Y", "N"):
            raise ValueError("Y/N 아님")
        return v == "Y"
    if isinstance(kind, tuple) and kind[0] == "enum":
        if v not in kind[1]:
            raise ValueError(f"허용 값 {kind[1]} 아님")
        return v
    raise ValueError(f"spec 형식 모름: {kind}")


def parse(texts):
    errs, data = [], {}
    for t, f in spec.FILES.items():
        name, text = f["file"], texts.get(t)
        if text is None:
            errs.append(f"{name}: 파일 없음")
            continue
        rows = list(csv.DictReader(io.StringIO(text)))
        head = next(csv.reader(io.StringIO(text)), [])
        need = [c.rstrip("?") for c in f["cols"]]
        miss = [c for c in need if c not in head]
        if miss:
            errs.append(f"{name}: 필수 열 없음 {miss}")
            continue
        dup_head = {c for c in head if head.count(c) > 1}
        if dup_head:
            errs.append(f"{name}: 같은 열 이름이 두 번 {sorted(dup_head)}")
        out = []
        for i, r in enumerate(rows, start=2):
            row = {}
            for c, kind in f["cols"].items():
                opt, c = c.endswith("?"), c.rstrip("?")
                v = r.get(c)
                if v is None or v == "":
                    if opt:
                        row[c] = None
                        continue
                    errs.append(f"{name}:{i} {c} 빈 값")
                    continue
                try:
                    row[c] = _cast(kind, v)
                except ValueError as e:
                    errs.append(f"{name}:{i} {c}={v!r} 형식 오류({e})")
            out.append(row)
        if not rows:
            errs.append(f"{name}: 행이 없음")
        key = f.get("key")
        if key:
            seen = {}
            for i, row in enumerate(out, start=2):
                k = row.get(key)
                if k in seen:
                    errs.append(f"{name}:{i} {key}={k!r} 중복 (처음 {seen[k]}줄)")
                seen.setdefault(k, i)
        data[t] = out
    if errs:
        return None, errs
    for t, f in spec.FILES.items():
        for c, target in f.get("refs", {}).items():
            tt, tc = target.split(".")
            have = {r[tc] for r in data[tt]}
            for i, row in enumerate(data[t], start=2):
                if row.get(c) is not None and row[c] not in have:
                    errs.append(f"{f['file']}:{i} {c}={row[c]!r} 가 {spec.FILES[tt]['file']} 에 없음")
    errs += spec.extra_checks(data) if not errs else []
    return (None, errs) if errs else (data, [])


def default_params(data):
    return {p["name"]: (p["default"](data) if callable(p["default"]) else p["default"]) for p in spec.PARAMS}


def check_params(raw, data):
    """화면에서 온 조건을 형식대로 바꾼다. (params, errors)"""
    out, errs = {}, []
    for p in spec.PARAMS:
        v = raw.get(p["name"])
        kind, opt = p["type"].rstrip("?"), p["type"].endswith("?")
        if v is None or v == "":
            if opt:
                out[p["name"]] = None
                continue
            errs.append(f"{p['label']}: 빈 값")
            continue
        try:
            out[p["name"]] = _cast(kind, str(v)) if kind != "num" else float(v)
        except ValueError as e:
            errs.append(f"{p['label']}={v!r} 형식 오류({e})")
    if not errs and "date_from" in out and "date_to" in out and out["date_from"] > out["date_to"]:
        errs.append("기간 시작이 끝보다 늦음")
    return out, errs
