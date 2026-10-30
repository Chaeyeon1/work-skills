#!/usr/bin/env bash
# 마무리 전 점검. 작업 폴더에서 실행한다: bash check.sh [작업폴더]
# 결과: ✓ 통과 / ! 확인 필요 / ✗ 고칠 것. 고칠 것이 있으면 exit 1.
set -u
cd "${1:-.}" || exit 2
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

bad=0
ok()   { echo "✓ $*"; }
warn() { echo "! $*"; }
fail() { echo "✗ $*"; bad=1; }

# 섹션 제목(## …) 아래, 다음 제목 전까지 내용이 있는 줄 수
section_lines() {
  awk -v pat="$2" '
    /^#/ { on = ($0 ~ pat); next }
    on && $0 !~ /^[[:space:]]*$/ && $0 !~ /^[[:space:]]*\(/ { n++ }
    END { print n + 0 }' "$1"
}

echo "== 문서"
for f in README.md PLAN.md NOTES.md AGENTS.md; do
  if [ ! -f "$f" ]; then fail "$f 없음 (README 가 다른 이름을 정했으면 그 파일을 확인)"; continue; fi
  n=$(grep -cvE '^[[:space:]]*(#.*)?$' "$f")
  if [ "$n" -lt 3 ]; then fail "$f 내용이 거의 없음 (${n}줄)"; else ok "$f (${n}줄)"; fi
done
if [ -f README.md ]; then
  grep -qE '^#+ .*(실행|사용|Run|run|Usage)' README.md && ok "README 에 실행 방법 제목 있음" || fail "README 에 실행 방법 제목 없음"
fi
if [ -f NOTES.md ]; then
  grep -qE '확인 ?:|^- .*→' NOTES.md && ok "NOTES 에 확인 기록 있음" || fail "NOTES 에 확인 기록(명령 → 결과) 없음"
fi
lim=0
for f in README.md NOTES.md; do [ -f "$f" ] && lim=$((lim + $(section_lines "$f" '한계'))); done
[ "$lim" -gt 0 ] && ok "남은 한계 있음" || fail "README·NOTES 에 '남은 한계'가 비어 있음"

echo "== git"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  c=$(git rev-list --count HEAD 2>/dev/null || echo 0)
  [ "$c" -ge 3 ] && ok "커밋 ${c}개" || warn "커밋 ${c}개 (단계마다 커밋했는지)"
  d=$(git status --porcelain | wc -l | tr -d ' ')
  [ "$d" -eq 0 ] && ok "커밋 안 된 변경 없음" || warn "커밋 안 된 변경 ${d}개"
  files=$(git ls-files -co --exclude-standard)
else
  fail "git 저장소가 아님"
  files=$(find . -type f -not -path './.git/*' -not -path '*/node_modules/*' | sed 's|^\./||')
fi
code=$(printf '%s\n' "$files" | grep -vE '(^|/)\.agents/|\.(md|txt|csv|json|lock|png|jpg|pdf|xlsx)$' | grep -v '^$')

echo "== 규칙 ↔ 코드"
if [ -f AGENTS.md ]; then
  rules=$(awk '/^#/ { on = ($0 ~ /확정된 규칙/); next } on' AGENTS.md | grep -oE '^[[:space:]]*[0-9]+\)' | tr -dc '0-9\n')
  if [ -z "$rules" ]; then
    warn "AGENTS.md '확정된 규칙'에 번호 붙은 규칙이 없음"
  else
    for n in $rules; do
      hit=$(printf '%s\n' "$code" | while IFS= read -r f; do [ -f "$f" ] && grep -lE "규칙 ?${n}([^0-9]|$)" "$f" 2>/dev/null; done | head -3 | tr '\n' ' ')
      [ -n "$hit" ] && ok "규칙 $n → $hit" || fail "규칙 $n 이 코드 어디에도 없음 ('# 규칙 ${n}' 주석)"
    done
  fi
fi

echo "== 서버·비밀"
if [ -n "$code" ]; then
  # 'localhost'·'127.0.0.1' 를 따옴표째 넘기는 곳(바인딩 인자), 기본값이 127.0.0.1 인 실행 명령
  lh=$( { printf '%s\n' "$code"; ls README.md package.json 2>/dev/null; } | sort -u | while IFS= read -r f; do
    [ -f "$f" ] || continue
    grep -nHE "['\"](127\.0\.0\.1|localhost)['\"]" "$f" 2>/dev/null
    grep -nHE "(\.run\(|uvicorn |flask run|vite( |$)|next dev)" "$f" 2>/dev/null | grep -v '0\.0\.0\.0'
  done | head -5)
  [ -z "$lh" ] && ok "localhost 전용 바인딩 안 보임" || { warn "localhost 전용 바인딩 의심 (다른 기기·미리보기에서 열려면 0.0.0.0)"; echo "$lh"; }
fi
sec=$(printf '%s\n' "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -nHE "sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY *= *['\"]?[A-Za-z0-9]" "$f" 2>/dev/null; done | head -3)
[ -z "$sec" ] && ok "파일에 키 값 없음" || { fail "키 값으로 보이는 문자열"; echo "$sec" | cut -c1-80; }

echo
[ "$bad" -eq 0 ] && echo "고칠 것 없음" || echo "✗ 부터 고치세요"
exit "$bad"
