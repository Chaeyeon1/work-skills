#!/usr/bin/env bash
# bash install.sh [작업폴더]            스킬 → ~/.agents/skills, AGENTS.md → 작업폴더
# bash install.sh --project [작업폴더]  스킬 → 작업폴더/.agents/skills
# 작업 폴더에 AGENTS.md 가 이미 있으면 덮지 않고 AGENTS.kit.md 로 둔다.
set -euo pipefail

KIT="$(cd "$(dirname "$0")" && pwd)"
mode=user
WORK="$PWD"
for a in "$@"; do
  case "$a" in
    --project) mode=project ;;
    -*) echo "모르는 옵션: $a" >&2; exit 2 ;;
    *) WORK="$(cd "$a" && pwd)" ;;
  esac
done

if [ "$mode" = project ]; then dest="$WORK/.agents/skills"; else dest="$HOME/.agents/skills"; fi
mkdir -p "$dest"
for d in "$KIT"/skills/*/; do
  name="$(basename "$d")"
  rm -rf "${dest:?}/$name"
  cp -R "$d" "$dest/$name"
  echo "스킬: $dest/$name"
done

if [ -e "$WORK/AGENTS.md" ]; then
  cp "$KIT/AGENTS.md" "$WORK/AGENTS.kit.md"
  echo "AGENTS.md 가 이미 있어 AGENTS.kit.md 로 두었습니다. 에이전트에게 'AGENTS.kit.md 규칙도 따라 줘'"
else
  cp "$KIT/AGENTS.md" "$WORK/AGENTS.md"
  echo "규칙: $WORK/AGENTS.md"
fi
echo "다음: codex 를 (다시) 켜고 /skills 에서 확인"
