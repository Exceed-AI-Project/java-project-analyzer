"""
가상 API 요청 시뮬레이터  (담당 파트)

접근법: '정적 요청 경로 추적'.
실제 Spring 앱을 띄우지 않고, AST 모델만으로
  1) Controller 엔드포인트를 추출하고
  2) @RequestBody DTO/Entity 의 제약(@NotNull, @Column(nullable=false), @Id 등)을 모아
  3) 가상 페이로드가 그 제약을 위반하는지 검사하고
  4) Controller→Service→Repository 호출 경로를 휴리스틱으로 추적한다.

→ "이 요청 이대로 들어오면 어디서 깨진다"를 앱 구동 없이 미리 보여주는 게 목표.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from models.analysis import ProjectModel, ClassInfo, MethodInfo
from services.ast_analyzer import NOT_NULL_ANNS

# HTTP 매핑 어노테이션 → 메서드
_MAPPING_HTTP = {
    "GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
    "DeleteMapping": "DELETE", "PatchMapping": "PATCH",
}


# ============================================================
# 모델
# ============================================================
@dataclass
class RequiredField:
    name: str
    type: str
    reason: str          # 어떤 제약 때문에 필수인지


@dataclass
class Endpoint:
    http_method: str
    path: str
    controller: str
    method: str
    request_body_type: Optional[str]
    path_vars: list[str] = field(default_factory=list)
    request_params: list[tuple[str, bool]] = field(default_factory=list)  # (name, required)


@dataclass
class Violation:
    severity: str        # high / medium / low
    field: str
    rule: str
    message: str


# ============================================================
# 1) 엔드포인트 추출
# ============================================================
def _path_of(params: dict) -> str:
    return params.get("_value") or params.get("value") or params.get("path") or ""


def extract_endpoints(model: ProjectModel) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for ci in model.of_stereotype("controller"):
        # 클래스 레벨 @RequestMapping 경로 prefix
        prefix = _path_of(ci.annotations.get("RequestMapping", {}))

        for m in ci.methods:
            http = None
            sub_path = ""
            for ann, params in m.annotations.items():
                if ann in _MAPPING_HTTP:
                    http = _MAPPING_HTTP[ann]
                    sub_path = _path_of(params)
                    break
                if ann == "RequestMapping":
                    http = (params.get("method") or "ANY").replace("RequestMethod.", "")
                    sub_path = _path_of(params)
                    break
            if http is None:
                continue  # 엔드포인트 아님

            body_type = None
            path_vars: list[str] = []
            req_params: list[tuple[str, bool]] = []
            for p in m.params:
                if "RequestBody" in p.annotations:
                    body_type = p.type
                elif "PathVariable" in p.annotations:
                    path_vars.append(p.name)
                elif "RequestParam" in p.annotations:
                    rp = p.annotations["RequestParam"]
                    required = str(rp.get("required", "true")).lower() != "false"
                    req_params.append((p.name, required))

            full = "/" + "/".join(s.strip("/") for s in (prefix, sub_path) if s)
            endpoints.append(Endpoint(
                http_method=http, path=full or "/",
                controller=ci.name, method=m.name,
                request_body_type=body_type,
                path_vars=path_vars, request_params=req_params,
            ))
    return endpoints


# ============================================================
# 2) 요청 스키마(필수 필드) 해석
# ============================================================
def resolve_schema(type_name: Optional[str], model: ProjectModel,
                   _seen: set | None = None) -> list[RequiredField]:
    """DTO/Entity 타입에서 필수 필드를 재귀적으로 수집."""
    if not type_name:
        return []
    _seen = _seen or set()
    if type_name in _seen:
        return []
    _seen.add(type_name)

    ci = model.by_name.get(type_name)
    if ci is None:
        return []

    required: list[RequiredField] = []
    for f in ci.fields:
        # @NotNull / @NotBlank / @NotEmpty
        for ann in NOT_NULL_ANNS:
            if ann in f.annotations:
                required.append(RequiredField(f.name, f.type, f"@{ann}"))
                break
        else:
            # @Column(nullable=false)
            col = f.annotations.get("Column")
            if col and str(col.get("nullable", "true")).lower() == "false":
                required.append(RequiredField(f.name, f.type, "@Column(nullable=false)"))
    return required


# ============================================================
# 3) 가상 요청 시뮬레이션
# ============================================================
def simulate_request(endpoint: Endpoint, payload: dict, model: ProjectModel) -> list[Violation]:
    """payload(가상 요청 바디)가 제약을 위반하는지 검사."""
    violations: list[Violation] = []

    # 바디 제약 검사
    required = resolve_schema(endpoint.request_body_type, model)
    for rf in required:
        if rf.name not in payload or payload.get(rf.name) in (None, ""):
            violations.append(Violation(
                "high", rf.name, rf.reason,
                f"필수 필드 '{rf.name}' ({rf.reason}) 누락/널 → 저장 시 제약 위반 예외 발생.",
            ))

    # @Id 직접 할당 필요 여부 (생성 요청에서 PK 자동생성 아닌 엔티티)
    body_ci = model.by_name.get(endpoint.request_body_type or "")
    if endpoint.http_method == "POST" and body_ci and body_ci.stereotype == "entity":
        for f in body_ci.fields:
            if "Id" in f.annotations and "GeneratedValue" not in f.annotations:
                if f.name not in payload:
                    violations.append(Violation(
                        "medium", f.name, "@Id(no GeneratedValue)",
                        f"PK '{f.name}' 가 자동생성이 아닌데 요청에 없음 → null PK 저장 시도.",
                    ))

    # 정의되지 않은 필드 (오타/스키마 불일치)
    if body_ci:
        known = {f.name for f in body_ci.fields}
        for key in payload:
            if key not in known:
                violations.append(Violation(
                    "low", key, "UNKNOWN_FIELD",
                    f"요청 필드 '{key}' 가 {body_ci.name} 에 없음 (무시되거나 역직렬화 오류 가능).",
                ))

    # PathVariable 누락 (경로에 {x} 있는데 핸들러 인자에 없음 — 정적 점검)
    for pv in endpoint.path_vars:
        if "{" + pv + "}" not in endpoint.path:
            violations.append(Violation(
                "medium", pv, "PATH_VAR_MISMATCH",
                f"@PathVariable '{pv}' 가 경로 패턴 {endpoint.path} 에 없음.",
            ))
    return violations


# ============================================================
# 4) 호출 경로 추적 (휴리스틱)
# ============================================================
def trace_call_path(endpoint: Endpoint, model: ProjectModel, max_depth: int = 4) -> list[str]:
    """Controller 메서드에서 시작해 Service/Repository 호출을 이름 기반으로 따라간다.
    ※ javalang 은 타입 리졸브를 안 하므로 '호출된 메서드명'을 가진 빈을 매칭하는 근사치.
    """
    controller = model.by_name.get(endpoint.controller)
    if not controller:
        return []
    start = next((m for m in controller.methods if m.name == endpoint.method), None)
    if not start:
        return []

    # 빠른 조회용: 메서드명 -> 그 메서드를 가진 (클래스, 메서드)
    owner: dict[str, list[tuple[ClassInfo, MethodInfo]]] = {}
    for ci in model.classes:
        for m in ci.methods:
            owner.setdefault(m.name, []).append((ci, m))

    path: list[str] = [f"{endpoint.controller}.{endpoint.method}()"]
    visited: set[str] = {f"{endpoint.controller}.{endpoint.method}"}

    def walk(m: MethodInfo, depth: int):
        if depth > max_depth:
            return
        for callee in m.invokes:
            for ci2, m2 in owner.get(callee, []):
                if ci2.stereotype not in ("service", "repository", "component"):
                    continue
                key = f"{ci2.name}.{m2.name}"
                if key in visited:
                    continue
                visited.add(key)
                path.append(f"{ci2.name}.{m2.name}()  [{ci2.stereotype}]")
                walk(m2, depth + 1)

    walk(start, 0)
    return path


# ============================================================
# 5) LLM 기반 페이로드 생성  (키 검증된 경우에만 호출)
# ============================================================
import json as _json
from services import llm as _llm


def _strip_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def generate_payload(endpoint: "Endpoint", model: ProjectModel, api_key: str,
                     mode: str = "valid") -> tuple[Optional[dict], str]:
    """LLM 이 DTO 제약을 보고 JSON 요청 바디를 짜준다.
    mode: 'valid' = 제약 만족 정상 데이터 / 'edge' = 일부 제약 위반 엣지 케이스
    반환: (payload dict or None, note)
    """
    body_ci = model.by_name.get(endpoint.request_body_type or "")
    if not body_ci:
        return None, "이 엔드포인트는 @RequestBody 가 없어 페이로드 생성 대상이 아님"

    field_lines = []
    for f in body_ci.fields:
        anns = " ".join("@" + a for a in f.annotations)
        field_lines.append(f"- {f.name}: {f.type} {anns}".rstrip())
    field_ctx = "\n".join(field_lines) or "(필드 없음)"

    mode_hint = {
        "valid": "모든 제약(@NotNull/@NotBlank/@Column(nullable=false) 등)을 만족하는 현실적인 정상 데이터",
        "edge": "일부 제약을 일부러 위반하는 엣지 케이스 (필수 필드 누락/빈값/타입 불일치를 섞어라)",
    }.get(mode, "현실적인 정상 데이터")

    system = ("You generate JSON request bodies for API testing. "
              "Output ONLY a single valid JSON object. No markdown, no comments, no prose.")
    user = (
        f"엔드포인트: {endpoint.http_method} {endpoint.path}\n"
        f"바디 타입: {body_ci.name}\n"
        f"필드:\n{field_ctx}\n\n"
        f"{mode_hint} 를 담은 JSON 한 개만 출력."
    )

    try:
        raw = _llm.chat(api_key, [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
    except Exception as e:
        return None, f"LLM 호출 실패: {e}"

    try:
        payload = _json.loads(_strip_json(raw))
    except Exception as e:
        return None, f"LLM 응답 JSON 파싱 실패: {e}\n원문: {raw[:200]}"

    if not isinstance(payload, dict):
        return None, "LLM 이 객체가 아닌 JSON 을 반환함"
    return payload, f"LLM 이 '{mode}' 페이로드 생성 완료"
