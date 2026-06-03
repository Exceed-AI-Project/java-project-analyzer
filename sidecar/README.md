# JavaParser 사이드카 (심볼 리졸브)

tree-sitter 는 빠르지만 타입/심볼을 해석하지 않아 콜그래프가 이름 기반 휴리스틱이다.
이 사이드카는 JavaParser + SymbolSolver 로 **메서드 호출의 소유 타입을 리졸브**해
`resolvedCalls`("Owner.method")를 채운다 → 데드코드/콜그래프/레이어링 정밀도 향상.

## 빌드 (Maven Central 접근 필요 — 로컬에서)

```bash
cd sidecar
mvn -q package
# 결과: sidecar/target/java-analyzer-sidecar.jar
```

JDK 17+ 필요. (이 저장소의 Python 앱과 별개로 한 번만 빌드하면 됨)

## 동작 확인

```bash
java -jar target/java-analyzer-sidecar.jar /path/to/some/java/project | head
# stdout 으로 {"classes":[...], "parseErrors":[...]} JSON 출력
```

## 앱과 연결

Python 앱은 자동으로 사이드카를 우선 사용한다:
- 기본 경로 `sidecar/target/java-analyzer-sidecar.jar` 가 있으면 `build_model(parser="auto")` 가 이걸 먼저 쓴다.
- 다른 경로면 환경변수로 지정: `export JP_SIDECAR_JAR=/abs/path/to.jar`
- jar 가 없거나 java 가 없으면 자동으로 tree-sitter 로 폴백 (앱은 안 죽음).

리졸브 데이터가 있으면 데드코드 탐지가 `DEAD_CODE_PRECISE` 로 자동 전환된다
(동명 메서드 오탐 제거).

## 출력 JSON 스키마 (Python 래퍼와의 계약)

```json
{
  "classes": [{
    "name":"UserService","kind":"class","package":"com.demo","file":"src/.../UserService.java",
    "imports":["..."], "annotations":{"Service":{}},
    "fields":[{"name":"repo","type":"UserRepository","annotations":{"Autowired":{}},"modifiers":["private","final"]}],
    "methods":[{"name":"register","returnType":"User",
      "params":[{"name":"req","type":"UserRequest","annotations":{}}],
      "annotations":{"Transactional":{}},"modifiers":["public"],
      "invokes":["save"],"resolvedCalls":["UserRepository.save"],"riskyCatches":[]}]
  }],
  "parseErrors": [["file","message"]]
}
```

스키마를 바꾸면 `services/javaparser_sidecar.py` 의 `parse_payload` 도 함께 수정할 것.
