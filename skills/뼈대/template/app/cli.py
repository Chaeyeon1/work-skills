"""DB 없이 돌리기 — 검사·내보내기.

python3 -m app.cli check  [폴더]                         검증 오류를 찍는다 (없으면 표별 행 수)
python3 -m app.cli export [폴더] --out out/export.json   기본 조건(전체 기간)으로 계획을 만들어 내보낸다
"""
import json
import os
import sys

sys.dont_write_bytecode = True

from . import dataset, planner  # noqa: E402


def main(argv):
    cmd, rest = argv[0], argv[1:]
    out = None
    if "--out" in rest:
        i = rest.index("--out")
        out = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    folder = rest[0] if rest else "data/provided"
    data, errs = dataset.parse(dataset.read_dir(folder))
    if errs:
        print("\n".join(errs))
        return 1
    if cmd == "check":
        print(json.dumps({t: len(r) for t, r in data.items()}, ensure_ascii=False))
        return 0
    params = dataset.default_params(data)
    result = planner.generate(data, params)
    out = out or "out/export.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result["export"], f, ensure_ascii=False, indent=1)
    print(f"{out} · 조건 {json.dumps(params, ensure_ascii=False)} · {json.dumps(result['summary'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
