"""잘못된 입력 데이터셋을 만든다 — 원본은 읽기만.

python3 checks/break_data.py [원본=data/provided] [대상=data/datasets]
만드는 것: 91-오류-열누락 · 92-오류-없는ID · 93-오류-형식 · 94-오류-중복ID
각 폴더에 무엇을 바꿨는지 BROKEN.txt 를 남긴다. 내용이 바뀐 '정상' 데이터셋(상태 변경 등)은 요청마다 손으로 만든다.
"""
import csv
import io
import os
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import spec  # noqa: E402


def rows(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def write(path, data):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(data)
    open(path, "w", encoding="utf-8").write(buf.getvalue())


def copy(src, dst, name, note):
    d = os.path.join(dst, name)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(src, d)
    open(os.path.join(d, "BROKEN.txt"), "w", encoding="utf-8").write(note + "\n")
    return d


def main(src="data/provided", dst="data/datasets"):
    os.makedirs(dst, exist_ok=True)
    tables = list(spec.FILES.items())
    t, f = next((t, f) for t, f in tables if f.get("refs"))
    col, target = next(iter(f["refs"].items()))
    p = os.path.join(src, f["file"])
    data = rows(p)
    head = data[0]
    i = head.index(col)

    drop = next(c.rstrip("?") for c in f["cols"] if not c.endswith("?"))
    j = head.index(drop)
    d = copy(src, dst, "91-오류-열누락", f"{f['file']} 에서 {drop} 열을 뺐다")
    write(os.path.join(d, f["file"]), [r[:j] + r[j + 1:] for r in data])

    d = copy(src, dst, "92-오류-없는ID", f"{f['file']}:2 {col} 를 없는 값 NOPE-999 로 ({target} 에 없음)")
    write(os.path.join(d, f["file"]), [data[0], data[1][:i] + ["NOPE-999"] + data[1][i + 1:]] + data[2:])

    ft, ff = next(((t2, f2) for t2, f2 in tables
                   for c, k in f2["cols"].items() if k in ("int", "num", "date", "time", "yn")), (None, None))
    c, k = next((c, k) for c, k in ff["cols"].items() if k in ("int", "num", "date", "time", "yn"))
    p2 = os.path.join(src, ff["file"])
    data2 = rows(p2)
    m = data2[0].index(c.rstrip("?"))
    d = copy(src, dst, "93-오류-형식", f"{ff['file']}:2 {c} ({k}) 를 '형식틀림' 으로")
    write(os.path.join(d, ff["file"]), [data2[0], data2[1][:m] + ["형식틀림"] + data2[1][m + 1:]] + data2[2:])

    kt, kf = next(((t2, f2) for t2, f2 in tables if f2.get("key")), (None, None))
    if kf:
        data3 = rows(os.path.join(src, kf["file"]))
        d = copy(src, dst, "94-오류-중복ID", f"{kf['file']} 2번째 줄을 한 번 더 넣었다({kf['key']} 중복)")
        write(os.path.join(d, kf["file"]), data3 + [data3[1]])
    for n in sorted(os.listdir(dst)):
        b = os.path.join(dst, n, "BROKEN.txt")
        if os.path.exists(b):
            print(n, "—", open(b, encoding="utf-8").read().strip())


if __name__ == "__main__":
    main(*sys.argv[1:])
