// 화면 — 서버 API 와 planner 의 결과 모양(summary·issues·rows·graph·members)만 읽는다. 요청마다 고칠 일은 문구 정도.
const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k instanceof Node ? k : String(k));
  return e;
};
const svgEl = (tag, attrs = {}) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let data = {};
  try { data = await r.json(); } catch { data = { error: `응답을 읽지 못함 (${r.status})` }; }
  if (r.status === 401) { show("login"); throw new Error(data.error); }
  return { status: r.status, ok: r.ok, data };
}

function show(id) {
  for (const s of ["login", "operator", "member"]) $("#" + s).hidden = s !== id;
}

function table(target, rows, cols) {
  target.replaceChildren();
  if (!rows.length) { target.append(el("tr", {}, el("td", { class: "muted" }, "없음"))); return; }
  cols = cols || Object.keys(rows[0]).map((k) => [k, k]);
  target.append(el("tr", {}, cols.map(([, h]) => el("th", {}, h))));
  for (const r of rows) target.append(el("tr", { class: r._class || "" }, cols.map(([k]) => el("td", {}, r[k] instanceof Node ? r[k] : r[k] ?? ""))));
}

function graph(target, g, highlight = new Set()) {
  target.replaceChildren();
  if (!g || !g.nodes.length) return;
  const W = 640, H = 380, P = 40;
  const xs = g.nodes.map((n) => n.x), ys = g.nodes.map((n) => n.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const sx = (x) => P + ((x - x0) / (x1 - x0 || 1)) * (W - 2 * P);
  const sy = (y) => P + ((y - y0) / (y1 - y0 || 1)) * (H - 2 * P);
  const pos = Object.fromEntries(g.nodes.map((n) => [n.id, [sx(n.x), sy(n.y)]]));
  const groups = [...new Set(g.edges.map((e) => e.group))];
  const colors = ["#5d6673", "#1f5fbf", "#a14a00", "#1d6b3a", "#7a3e9d", "#b3261e"];
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img" });
  for (const e of g.edges) {
    if (!pos[e.from] || !pos[e.to]) continue;
    const [a, b] = [pos[e.from], pos[e.to]];
    const grp = svgEl("g", { class: "edge" });
    grp.append(svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: colors[groups.indexOf(e.group) % colors.length] }));
    if (e.label) { const t = svgEl("text", { x: (a[0] + b[0]) / 2 + 3, y: (a[1] + b[1]) / 2 - 3 }); t.textContent = e.label; grp.append(t); }
    svg.append(grp);
  }
  for (const n of g.nodes) {
    const [x, y] = pos[n.id];
    const grp = svgEl("g", { class: "node" + (highlight.has(n.id) ? " on" : "") });
    grp.append(svgEl("circle", { cx: x, cy: y, r: 7 }));
    const t = svgEl("text", { x: x + 10, y: y + 4 }); t.textContent = n.label; grp.append(t);
    svg.append(grp);
  }
  target.append(svg);
  if (groups.length > 1) target.append(el("div", { class: "row muted" }, groups.map((gname, i) => el("span", { style: `color:${colors[i % colors.length]}` }, "— " + gname))));
}

// ---------- 운영자 ----------
let current = null;

async function loadOperator() {
  const { data } = await api("/api/datasets");
  const a = data.active;
  $("#active-bar").replaceChildren(a ? el("span", {}, "적용된 데이터셋: ", el("strong", {}, a.name), ` (버전 ${a.id}, ${a.applied_at}, ${a.digest})`) : el("span", { class: "err" }, "적용된 데이터셋 없음"));
  const sel = $("#ds-name");
  const keep = sel.value;
  sel.replaceChildren(...data.names.map((n) => el("option", { value: n }, n)));
  if (keep) sel.value = keep;
  table($("#events"), data.events, [["at", "시각"], ["who", "누가"], ["what", "무엇"], ["plan_id", "계획"], ["detail", "내용"]]);
  await loadParams();
  await loadPlans();
}

async function loadParams() {
  const { data } = await api("/api/params");
  const f = $("#params-form");
  f.dataset.datasetId = data.dataset_id;
  f.replaceChildren(...data.fields.map((x) => el("label", {}, x.label, el("input", {
    name: x.name, value: data.params[x.name] ?? "", type: x.type.startsWith("date") ? "date" : x.type.startsWith("int") || x.type.startsWith("num") ? "number" : "text",
    step: x.type.startsWith("num") ? "any" : false,
  }))), el("button", {}, "조건 저장"));
}

async function loadPlans() {
  const { data } = await api("/api/plans");
  table($("#plans"), data.plans.map((p) => ({
    ...p, open: el("button", { onclick: () => openPlan(p.id) }, "보기"),
    data: p.stale ? el("span", { class: "stale" }, `이전 데이터셋(버전 ${p.dataset_id})`) : `지금 데이터셋(버전 ${p.dataset_id})`,
    issues: p.issues_n ? el("span", { class: "warn" }, `확인 필요 ${p.issues_n}`) : "0",
  })), [["id", "번호"], ["status_ko", "상태"], ["data", "데이터"], ["issues", "확인 필요"], ["created_at", "만든 때"], ["created_by", "누가"], ["open", ""]]);
  if (current) openPlan(current);
}

async function openPlan(id) {
  current = id;
  const { ok, data: p } = await api(`/api/plans/${id}`);
  if (!ok) return;
  const r = p.result;
  $("#plan").hidden = false;
  $("#plan-title").textContent = `계획 ${p.id} · ${p.status_ko}`;
  $("#plan-bar").replaceChildren(p.stale
    ? el("span", { class: "stale" }, `이 계획은 이전 데이터셋(버전 ${p.dataset_id})으로 만든 결과입니다. 지금 데이터의 결과가 아닙니다. 다시 생성하세요.`)
    : el("span", { class: "muted" }, `데이터셋 버전 ${p.dataset_id} · 조건 ${JSON.stringify(p.params)}`));
  $("#plan-summary").replaceChildren(...Object.entries(r.summary).map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, v))));
  $("#plan-issues").replaceChildren(r.issues.length
    ? el("details", { open: true }, el("summary", { class: "warn" }, `확인 필요 ${r.issues.length}건`), el("ul", {}, r.issues.map((i) => el("li", {}, `${i.what} — ${i.where}`))))
    : el("p", { class: "ok" }, "확인 필요 없음"));
  const ack = el("input", { type: "checkbox", id: "ack" });
  const act = (name, label) => el("button", { disabled: p.stale, onclick: async () => {
    const res = await api(`/api/plans/${id}/${name}`, { ack: ack.checked });
    $("#gen-result").replaceChildren(el("span", { class: res.ok ? "ok" : "err" }, res.ok ? `${label} 완료` : res.data.error));
    loadOperator();
  } }, label);
  $("#plan-actions").replaceChildren(
    ...(r.issues.length && ["draft", "approved"].includes(p.status) ? [el("label", { class: "warn" }, ack, `확인 필요 ${r.issues.length}건을 봤음`)] : []),
    ...(p.status === "draft" ? [act("approve", "결재")] : []),
    ...(p.status === "approved" ? [act("publish", "공개")] : []),
  );
  graph($("#plan-graph"), r.graph);
  table($("#plan-rows"), r.rows.slice(0, 500));
  $("#export-json").hidden = true;
  $("#export-path").textContent = r.rows.length > 500 ? `표는 앞 500행만 (전체 ${r.rows.length})` : "";
}

$("#ds-check").onclick = async () => {
  const { data } = await api("/api/datasets/check", { name: $("#ds-name").value });
  $("#ds-result").replaceChildren(data.ok
    ? el("p", { class: "ok" }, "검사 통과 · ", Object.entries(data.counts).map(([k, v]) => `${k} ${v}행`).join(" · "))
    : el("div", { class: "err" }, el("p", {}, `오류 ${data.errors.length}건 — 적용하지 않습니다`), el("ul", {}, data.errors.slice(0, 50).map((e) => el("li", {}, e)))));
};
$("#ds-apply").onclick = async () => {
  const { ok, data } = await api("/api/datasets/apply", { name: $("#ds-name").value });
  $("#ds-result").replaceChildren(ok
    ? el("p", { class: "ok" }, `적용함 (버전 ${data.dataset_id}). 조건은 이 데이터의 기본값으로 돌아갑니다. 이전 계획은 '이전 데이터셋'으로 표시됩니다.`)
    : el("div", { class: "err" }, el("p", {}, `적용하지 않음 — 기존 데이터와 결과를 유지합니다. 오류 ${data.errors.length}건`), el("ul", {}, data.errors.slice(0, 50).map((e) => el("li", {}, e)))));
  loadOperator();
};
$("#params-form").onsubmit = async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const params = Object.fromEntries([...f.querySelectorAll("input")].map((i) => [i.name, i.value]));
  const { ok, data } = await api("/api/params", { dataset_id: Number(f.dataset.datasetId), params });
  $("#params-result").replaceChildren(el("p", { class: ok ? "ok" : "err" }, ok ? "저장함. 다시 생성해야 결과에 반영됩니다." : (data.errors || [data.error]).join(" · ")));
};
$("#gen").onclick = async (ev) => {
  ev.target.disabled = true;
  $("#gen-result").textContent = "생성 중…";
  try {
    const { ok, data } = await api("/api/plans", {});
    $("#gen-result").replaceChildren(el("span", { class: ok ? "ok" : "err" }, ok ? `계획 ${data.plan_id} 생성(초안)` : data.error));
    if (ok) current = data.plan_id;
    loadPlans();
  } finally { ev.target.disabled = false; }
};
$("#export").onclick = async () => {
  const { ok, data } = await api(`/api/plans/${current}/export`);
  if (!ok) return;
  $("#export-path").replaceChildren(el("span", { class: data.stale ? "stale" : "ok" }, `서버에 저장: ${data.path} · ${data.status}${data.stale ? " · 이전 데이터셋" : ""}`));
  const pre = $("#export-json");
  pre.textContent = JSON.stringify(data.data, null, 1);
  pre.hidden = false;
};

// ---------- 두 번째 역할 ----------
async function loadMember(date) {
  const { data } = await api("/api/my" + (date ? `?date=${encodeURIComponent(date)}` : ""));
  if (!data.published) { $("#my-bar").textContent = data.message; return; }
  $("#my-bar").replaceChildren(el("span", {}, `지금 ${data.now} · 공개된 계획 ${data.published.id} (${data.published.created_at})`));
  const sel = $("#my-date");
  const dates = data.dates.includes(data.date) ? data.dates : [...data.dates, data.date].sort();
  sel.replaceChildren(...dates.map((d) => el("option", { value: d, selected: d === data.date }, d)));
  const now = data.now_item, next = data.next_item;
  $("#my-now").replaceChildren(
    el("p", {}, "지금 있어야 할 곳: ", el("strong", {}, now ? `${now.where} (${now.start}~${now.end} ${now.what})` : "이 날짜에 지금 걸친 일정 없음")),
    el("p", {}, "다음: ", next ? `${next.start} ${next.where}` : (now && now.next ? `${now.next}${now.next_min != null ? ` · ${now.next_min}분` : ""}` : "없음")),
  );
  const on = new Set(data.items.flatMap((i) => i.nodes || []));
  graph($("#my-graph"), data.graph, on);
  table($("#my-items"), data.items.map((i) => ({ ...i, _class: i === now || (now && i.start === now.start && i.where === now.where) ? "now" : "",
    nextText: i.next ? `${i.next}${i.next_min != null ? ` (${i.next_min}분)` : ""}` : "" })),
  [["start", "시작"], ["end", "끝"], ["where", "어디"], ["what", "무엇"], ["nextText", "다음까지"]]);
}
$("#my-date").onchange = (ev) => loadMember(ev.target.value);

// ---------- 시작 ----------
$("#login-form").onsubmit = async (ev) => {
  ev.preventDefault();
  const f = new FormData(ev.target);
  const { ok, data } = await api("/api/login", { id: f.get("id"), pw: f.get("pw") });
  if (!ok) { $("#login-err").textContent = data.error; return; }
  start();
};
$("#logout").onclick = async () => { await api("/api/logout", {}); location.reload(); };

async function start() {
  const r = await fetch("/api/me");
  if (r.status !== 200) { show("login"); return; }
  const { user } = await r.json();
  $("#who").textContent = `${user.name} (${user.role === "operator" ? "운영자" : "조회"})`;
  $("#logout").hidden = false;
  show(user.role);
  if (user.role === "operator") loadOperator();
  else { loadMember(); setInterval(() => loadMember($("#my-date").value), 60000); }
}
start();
