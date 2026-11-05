"""API 문서 — /openapi.json (OpenAPI 3.0) · /docs (Swagger UI, CDN. 못 불러오면 표로 대신).

ROUTES 는 문서용 선언이다. 라우팅은 server.py 의 api() 가 한다. 새 API 를 더하면 여기에도 한 줄.
checks/smoke.py 가 GET 경로마다 404 가 아닌지 본다(문서와 코드가 어긋나면 실패).
"""
import html
import json

# (메서드, 경로, 역할, 요약, 요청 본문 예시 또는 None, {상태: 설명})
ROUTES = [
    ("GET", "/health", None, "DB 연결·활성 데이터셋 확인", None, {200: '{"ok": true, "dataset": true}'}),
    ("POST", "/api/login", None, "로그인 → Set-Cookie sid", {"id": "operator", "pw": "…"}, {200: "user", 401: "틀림"}),
    ("POST", "/api/logout", "any", "세션 삭제", {}, {200: "ok"}),
    ("GET", "/api/me", "any", "현재 사용자·서버 현지 시각", None, {200: "user, now", 401: "로그인 필요"}),
    ("GET", "/api/datasets", "operator", "데이터셋 폴더 목록·활성 버전·최근 events", None, {200: "names, active, events"}),
    ("POST", "/api/datasets/check", "operator", "검증만(쓰기 없음)", {"name": "provided"}, {200: "ok, errors[], counts"}),
    ("POST", "/api/datasets/apply", "operator", "트랜잭션 안에서 다시 검증 → 새 버전 활성(조건은 새 기본값)",
     {"name": "provided"}, {200: "dataset_id", 422: "errors[] — 아무것도 안 바뀜"}),
    ("GET", "/api/params", "operator", "활성 버전의 조건과 필드 정의", None, {200: "dataset_id, params, fields"}),
    ("POST", "/api/params", "operator", "조건 저장(보낸 dataset_id 가 활성일 때만)",
     {"dataset_id": 1, "params": {}}, {200: "params", 422: "형식 오류", 409: "그사이 데이터셋 바뀜"}),
    ("POST", "/api/plans", "operator", "생성: 활성을 읽고 잠금 밖에서 계산 → 잠금 안에서 버전 재확인 후 draft 저장",
     {}, {200: "plan_id", 409: "계산 중 데이터셋 바뀜"}),
    ("GET", "/api/plans", "operator", "계획 목록(stale 포함)", None, {200: "plans[]"}),
    ("GET", "/api/plans/{id}", "operator", "계획 상세(result 스냅숏·stale·needs)", None, {200: "plan", 404: "없음"}),
    ("GET", "/api/plans/{id}/export", "operator", "스냅숏 export → out/plan-{id}.json 저장 + 응답",
     None, {200: "path, stale, data"}),
    ("POST", "/api/plans/{id}/approve", "operator", "draft → approved (같은 tx 에서 상태·데이터셋·확인 필요·NEEDS 검사)",
     {"ack": True, "fields": {}}, {200: "status", 409: "거절 이유"}),
    ("POST", "/api/plans/{id}/publish", "operator", "approved → published, 이전 공개는 replaced",
     {"ack": True, "fields": {}}, {200: "status", 409: "거절 이유"}),
    ("GET", "/api/my", "member", "공개 스냅숏에서 내 항목·지금 항목·다음 항목·그래프 (?date=YYYY-MM-DD)",
     None, {200: "published, date, items, now_item, next_item, graph"}),
]


def openapi():
    paths = {}
    for method, path, role, summary, body, resp in ROUTES:
        op = {"summary": summary, "tags": [role or "public"],
              "responses": {str(k): {"description": v} for k, v in resp.items()}}
        params = [{"name": n, "in": "path", "required": True, "schema": {"type": "integer"}}
                  for n in ("id",) if "{" + n + "}" in path]
        if path == "/api/my":
            params.append({"name": "date", "in": "query", "required": False, "schema": {"type": "string", "format": "date"}})
        if params:
            op["parameters"] = params
        if body is not None:
            op["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}, "example": body}}}
        if role:
            op["security"] = [{"cookie": []}]
        paths.setdefault(path, {})[method.lower()] = op
    return {"openapi": "3.0.3", "info": {"title": "계획 서비스 API", "version": "1"},
            "components": {"securitySchemes": {"cookie": {"type": "apiKey", "in": "cookie", "name": "sid"}}},
            "paths": paths}


def docs_html():
    rows = "".join(f"<tr><td>{m}</td><td><code>{html.escape(p)}</code></td><td>{r or '-'}</td><td>{html.escape(s)}</td>"
                   f"<td>{html.escape(', '.join(f'{k} {v}' for k, v in resp.items()))}</td></tr>"
                   for m, p, r, s, _, resp in ROUTES)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
<style>body{{margin:0;font:14px system-ui,sans-serif}}#fallback{{padding:20px}}table{{border-collapse:collapse}}td,th{{border-bottom:1px solid #ddd;padding:4px 10px;text-align:left;vertical-align:top}}</style>
</head><body><div id="swagger"></div>
<div id="fallback"><p>Swagger UI 를 불러오지 못하면(오프라인) 아래 표로 본다. 원본: <a href="/openapi.json">/openapi.json</a>. 로그인은 메인 화면에서 먼저 — 쿠키가 같이 간다.</p>
<table><tr><th>메서드</th><th>경로</th><th>역할</th><th>하는 일</th><th>응답</th></tr>{rows}</table></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>if (window.SwaggerUIBundle) {{ document.getElementById("fallback").hidden = true;
  SwaggerUIBundle({{ url: "/openapi.json", dom_id: "#swagger", withCredentials: true }}); }}</script>
</body></html>"""


def as_json():
    return json.dumps(openapi(), ensure_ascii=False)
