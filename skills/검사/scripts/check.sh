#!/usr/bin/env bash
# 마무리 전 점검. 작업 폴더에서 실행한다: bash check.sh [작업폴더]
# 결과: ✓ 통과 / ! 확인 필요 / ✗ 고칠 것. 고칠 것이 있으면 exit 1.
set -u
cd "${1:-.}" || exit 2
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

bad=0
nw=0
ok()   { echo "✓ $*"; }
warn() { echo "! $*"; nw=$((nw + 1)); }
fail() { echo "✗ $*"; bad=1; }

# 섹션 제목(## …) 아래, 다음 제목 전까지 내용이 있는 줄 수
section_lines() {
  # pat 이 든 제목(수준 상관없이) 아래, 같은 수준이거나 더 높은 다음 제목 전까지 내용 줄 수
  awk -v pat="$2" '
    /^```/ { fence = !fence }
    !fence && /^#+ / { lv = length($1)
             if (on && lv <= onlv) on = 0
             if (!on && $0 ~ pat) { on = 1; onlv = lv }
             next }
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
  if grep -qE '^#+ .*(실행 방법|실행방법|사용법|Usage|How to run|Run)' README.md; then
    # 코드 블록(```) 안의 '# 주석' 은 제목이 아니다. 실행 방법 제목 아래, 같은 수준 이상의 다음 제목 전까지
    run=$(awk '/^```/ { fence = !fence; if (on) print; next }
      !fence && /^#+ / { lv = length($1); if (on && lv <= onlv) on = 0
                         if (!on && $0 ~ /(실행 방법|실행방법|사용법|Usage|How to run|Run)/) { on = 1; onlv = lv; next } }
      on' README.md | grep -vE '^[[:space:]]*$|^```|여기에 적어|TODO' | wc -l | tr -d ' ')
    [ "$run" -gt 0 ] && ok "README 실행 방법 ${run}줄" || warn "README 실행 방법이 비어 있음 (\$보고서 에서 채운다)"
  else fail "README 에 실행 방법 제목 없음"; fi
fi
if [ -f NOTES.md ]; then
  grep -qE '확인 ?:|^- .*→' NOTES.md && ok "NOTES 에 확인 기록 있음" || fail "NOTES 에 확인 기록(명령 → 결과) 없음"
fi
if [ -f NOTES.md ]; then
  # NOTES 에 적힌 가장 늦은 시각이 지금보다 늦으면 어림해 적은 것 (자정 넘김은 6시간 안쪽만 의심)
  late=$(grep -oE '\b[0-2][0-9]:[0-5][0-9]\b' NOTES.md | sort | tail -1)
  nowhm=$(date +%H:%M)
  if [ -n "$late" ]; then
    lm=$((10#${late%:*} * 60 + 10#${late#*:})); nm=$((10#${nowhm%:*} * 60 + 10#${nowhm#*:}))
    [ "$lm" -gt "$nm" ] && [ $((lm - nm)) -lt 360 ] && warn "NOTES 시각 $late 가 지금($nowhm)보다 늦음 — 어림한 시각인지 확인 (date·git log)"
  fi
  multi=$(grep -nE 'Q:.*Q:' NOTES.md | head -2)
  [ -z "$multi" ] && ok "NOTES 문답이 한 줄에 하나씩" || { fail "NOTES 한 줄에 문답이 여러 개 붙어 있음"; echo "$multi" | cut -c1-80; }
fi
lim=0
for f in README.md NOTES.md; do [ -f "$f" ] && lim=$((lim + $(section_lines "$f" '한계'))); done
[ "$lim" -gt 0 ] && ok "남은 한계 있음" || warn "README·NOTES 에 '남은 한계'가 비어 있음 (\$보고서 에서 채운다)"

echo "== git"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  c=$(git rev-list --count HEAD 2>/dev/null || echo 0)
  [ "$c" -ge 3 ] && ok "커밋 ${c}개" || warn "커밋 ${c}개 (단계마다 커밋했는지)"
  for f in README.md PLAN.md NOTES.md AGENTS.md; do
    [ -f "$f" ] && [ -z "$(git log -1 --format=%h -- "$f" 2>/dev/null)" ] && fail "$f 가 한 번도 커밋되지 않음"
  done
  d=$(git -c core.quotepath=off status --porcelain | wc -l | tr -d ' ')
  [ "$d" -eq 0 ] && ok "커밋 안 된 변경 없음" || warn "커밋 안 된 변경 ${d}개"
  files=$(git -c core.quotepath=off ls-files -co --exclude-standard)
  junk=$(git -c core.quotepath=off ls-files | grep -E '(^|/)(__pycache__/|\.DS_Store$|.*\.pyc$|node_modules/)' | head -3)
  [ -z "$junk" ] && ok "커밋에 부산물 없음" || { fail "커밋에 들어간 부산물 (.gitignore 에 넣고 git rm --cached)"; echo "$junk"; }
else
  fail "git 저장소가 아님"
  files=$(find . -type f -not -path './.git/*' -not -path '*/node_modules/*' | sed 's|^\./||')
fi
# 코드 = 원본 자료·결과물·문서가 아닌 파일 (out/·output/·dist/·build/·.verify/ 생성물과 checks/ 독립 검산은 코드로 세지 않는다)
code=$(printf '%s\n' "$files" | grep -vE '(^|/)(\.agents|out|output|dist|build|\.verify|checks)/|\.(md|txt|csv|tsv|json|lock|png|jpg|svg|pdf|xlsx|log)$' | grep -v '^$')

echo "== 규칙 ↔ 코드"
if [ -f AGENTS.md ]; then
  # '(코드 아님)' 이 붙은 규칙과 다른 규칙으로 바뀐 규칙은 코드 대조에서 뺀다
  rules=$(awk '/^#/ { on = ($0 ~ /확정된 규칙/); next } on' AGENTS.md | grep -vE '\(코드 아님\)|→ 규칙 [0-9]+ ?(으)?로 바뀜' | grep -oE '^[[:space:]]*[0-9]+\)' | tr -dc '0-9\n')
  if [ -z "$rules" ]; then
    warn "AGENTS.md '확정된 규칙'에 번호 붙은 규칙이 없음"
  else
    for n in $rules; do
      # '규칙 3', '규칙 1, 9', '규칙 5·8' 처럼 나열한 번호도 읽는다
      hit=$(printf '%s\n' "$code" | while IFS= read -r f; do
        [ -f "$f" ] || continue
        # 번호 바로 뒤에 한글·숫자가 붙으면('3분기') 규칙 번호로 보지 않는다
        # '규칙 16~20' 같은 범위는 펼쳐서 센다
        perl -CSD -Mutf8 -ne 'while (/규칙 ?(\d+(?:\s*[~–-]\s*\d+|[ ,·와및]+\d+)*)(?![\d\p{Hangul}])/g) { my $g = $1; $g =~ s/(\d+)\s*[~–-]\s*(\d+)/join(",", $1 .. $2)/ge; print "$g\n" }' "$f" 2>/dev/null | grep -oE "[0-9]+" | grep -qx "$n" && echo "$f"
      done | head -3 | tr '\n' ' ')
      if [ -n "$hit" ]; then ok "규칙 $n → $hit"
      elif printf '%s\n' "$files" | grep -E '(^|/)checks/' | while IFS= read -r f; do [ -f "$f" ] && grep -qE "규칙 ?${n}([^0-9]|$)" "$f" && echo y; done | grep -q y; then
        warn "규칙 $n: checks/ 에만 있음 (측정·검산 규칙이면 괜찮다. 결과물 코드에 있어야 할 규칙이면 빠진 것)"
      else warn "규칙 $n 주석이 코드에 없음 (코드가 아닌 규칙이면 \$검사 대조표에 근거를 적는다)"; fi
    done
  fi
fi

echo "== 서버·비밀"
if [ -n "$code" ]; then
  # 'localhost'·'127.0.0.1' 를 따옴표째 넘기는 곳(바인딩 인자), 기본값이 127.0.0.1 인 실행 명령
  lh=$( { printf '%s\n' "$code"; ls README.md package.json 2>/dev/null; } | sort -u | while IFS= read -r f; do
    [ -f "$f" ] || continue
    grep -nHE "['\"](127\.0\.0\.1|localhost)['\"]" "$f" 2>/dev/null
    grep -nHE "(\.run\(|uvicorn |flask run|vite( |$)|next dev)" "$f" 2>/dev/null | grep -vE '0\.0\.0\.0|subprocess\.run|asyncio\.run'
  done | head -5)
  [ -z "$lh" ] && ok "localhost 전용 바인딩 안 보임" || { warn "localhost 전용 바인딩 의심 (다른 기기·미리보기에서 열려면 0.0.0.0)"; echo "$lh"; }
fi
sec=$(printf '%s\n' "$files" | while IFS= read -r f; do [ -f "$f" ] && grep -nHE "sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY *= *['\"]?[A-Za-z0-9]" "$f" 2>/dev/null; done | head -3)
[ -z "$sec" ] && ok "파일에 키 값 없음" || { fail "키 값으로 보이는 문자열"; echo "$sec" | cut -c1-80; }

echo
if [ "$bad" -ne 0 ]; then echo "✗ 부터 고치세요"; elif [ "$nw" -gt 0 ]; then echo "고칠 것 없음 · 확인 필요 ${nw}개 (! 줄을 \$검사 대조표에서 따진다)"; else echo "고칠 것 없음"; fi
exit "$bad"
