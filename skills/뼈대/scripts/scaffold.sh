#!/usr/bin/env bash
# bash scaffold.sh [작업폴더]            뼈대를 작업 폴더에 깐다. 있는 파일은 덮지 않는다
# bash scaffold.sh --example [작업폴더]  예시 자료까지 data/provided 에 (뼈대 자체를 확인할 때만)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
example=0
WORK="$PWD"
for a in "$@"; do
  case "$a" in
    --example) example=1 ;;
    -*) echo "모르는 옵션: $a" >&2; exit 2 ;;
    *) WORK="$(cd "$a" && pwd)" ;;
  esac
done
cd "$HERE/template"
made=0; kept=0
while IFS= read -r f; do
  f="${f#./}"
  if [ -e "$WORK/$f" ]; then echo "있음, 건너뜀: $f"; kept=$((kept+1)); continue; fi
  mkdir -p "$WORK/$(dirname "$f")"
  cp "$f" "$WORK/$f"; made=$((made+1))
done < <(find . -type f ! -name '.DS_Store' ! -path '*/__pycache__/*' | sort)
touch "$WORK/.gitignore"
for line in var/ out/plan-*.json __pycache__/ .verify/ .env; do
  grep -qxF "$line" "$WORK/.gitignore" || echo "$line" >> "$WORK/.gitignore"
done
if [ "$example" = 1 ] && [ ! -e "$WORK/data/provided" ]; then
  mkdir -p "$WORK/data/provided"; cp "$HERE"/example/data/*.csv "$WORK/data/provided/"
  echo "예시 자료: data/provided"
fi
echo "만듦 ${made}개 · 건너뜀 ${kept}개 → $WORK"
echo "채울 곳: app/spec.py · app/planner.py · checks/verify.py · checks/smoke.py 머리(MEMBER_ID·NIGHT) · HOW_TO_RUN.md (채움)"
