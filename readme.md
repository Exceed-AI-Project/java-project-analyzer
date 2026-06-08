# ☕ Java Refactor Assistant

> **Java 프로젝트를 앱 실행 없이 분석하고, AI가 리팩토링 제안까지 드립니다.**  
> AST 파싱 · 결함 탐지 · RAG 질의응답 · API 시뮬레이션 · 의존성 시각화를 하나의 웹 UI에서.

---

## 📌 프로젝트 소개

Java/Spring Boot 프로젝트를 업로드하면:

1. **tree-sitter** 또는 **JavaParser 사이드카**로 소스를 파싱해 AST 모델을 구축합니다.
2. 규칙 기반 탐지기가 데드코드, 순환 의존성, Nullable 필드 불일치 등 **코드 결함을 자동 탐지**합니다.
3. OpenAI 임베딩 + FAISS 벡터 인덱스로 **자연어 질의에 맥락 있는 답변**을 돌려줍니다.
4. LLM이 결함별 **수정 diff를 생성**하고, 사람이 검토 후 적용합니다.
5. 앱을 띄우지 않아도 **HTTP 엔드포인트 가상 요청 시뮬레이션**으로 제약 위반을 미리 잡습니다.
6. Controller → Service → Repository 의존 흐름을 **그래프로 시각화**합니다.

---

## 🖥️ 화면 구성

| 메뉴 | 설명 |
|---|---|
| 🏠 홈 | 프로젝트 등록 및 선택 |
| 🔍 AST 분석 | 클래스/메서드 구조 + 결함 목록 |
| 🛠️ 리팩토링 제안 | LLM이 결함별 diff 생성 · 검토 후 적용 |
| 💬 RAG 질의응답 | 소스 기반 자연어 질의 |
| 🚀 API 시뮬레이터 | 가상 HTTP 요청 → 제약 위반 탐지 |
| 🕸 의존성 맵 | 클래스 의존성 그래프 + 순환 감지 |

---

## ⚙️ 기술 스택

| 분류 | 기술 |
|---|---|
| **UI** | Streamlit 1.39 |
| **파싱** | tree-sitter 0.25 · tree-sitter-java 0.23 · JavaParser (사이드카 JAR) |
| **임베딩/검색** | OpenAI Embeddings · FAISS (faiss-cpu) |
| **LLM** | OpenAI GPT (openai 1.54) |
| **API 시뮬레이션** | FastAPI · Uvicorn · httpx |
| **사이드카** | Java 17+ · Maven |

---

## 🚀 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. (선택) JavaParser 사이드카 빌드

tree-sitter보다 정밀한 심볼 리졸브가 필요할 때 사용합니다.  
사이드카가 없으면 자동으로 tree-sitter로 폴백하므로 **필수는 아닙니다.**

```bash
cd sidecar
mvn -q package
# → sidecar/target/java-analyzer-sidecar.jar 생성
```

> JDK 17 이상 필요. 다른 경로에 JAR를 뒀다면 `JP_SIDECAR_JAR` 환경변수로 지정하세요.

### 3. 앱 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속 후, **홈 화면의 🔑 OpenAI API 키 설정** 란에 `sk-...` 키를 입력하고 **확인** 버튼을 누릅니다.  
검증이 통과되면 LLM 기반 기능(리팩토링 제안 · RAG 질의응답)이 활성화됩니다.  
키를 입력하지 않아도 정적 분석 · API 시뮬레이터 · 의존성 맵은 바로 사용 가능합니다.

---

## 🔍 주요 기능 상세

### AST 분석 엔진

- **파서 자동 선택**: 사이드카 JAR가 있으면 JavaParser, 없으면 tree-sitter 사용
- **탐지 항목**
  - 데드코드 (일반 / 심볼 리졸브 기반 정밀 탐지)
  - Nullable 필드 / `@NotNull` 불일치
  - 순환 의존성 (Spring 부팅 실패 위험)
  - 고아 클래스 (아무도 의존하지 않는 Bean)
- Spring 어노테이션(`@GetMapping`, `@Scheduled`, `@Test` 등) 인식 → 오탐 방지

### RAG 질의응답

- `.java` 파일을 1,200자 단위(200자 겹침)로 청킹
- OpenAI 임베딩 → FAISS 인덱스 생성 (`.analysis/` 에 영속화)
- 질의 시 유사 청크를 검색해 LLM 컨텍스트로 제공

### 리팩토링 제안

- Finding → LLM 한국어 수정 요청 자동 변환
- **통합 diff 생성** — 자동 적용 없이 사람이 검토 후 명시적으로 적용
- 적용 후 동일 결함이 사라졌는지 재탐지로 검증

### API 시뮬레이터

- Controller 엔드포인트 자동 추출 (경로 · HTTP 메서드 · Path Variable · RequestParam)
- `@RequestBody` DTO의 `@NotNull` / `@NotBlank` / `@Column(nullable=false)` / `@Id` 등 제약 수집
- 가상 페이로드 입력 → **앱 구동 없이** 제약 위반 사전 탐지
- Controller → Service → Repository 호출 경로 휴리스틱 추적

### 의존성 맵

- 필드 타입 기반 클래스 의존 그래프 (DOT → Graphviz 렌더링)
- 스테레오타입별 색상 구분 (Controller · Service · Repository · Entity · DTO)
- 순환 의존성 · 고아 클래스 강조 표시

---

## 📁 프로젝트 구조

```
java-project-analyzer/
├── app.py                  # 진입점 (Streamlit 라우팅)
├── requirements.txt
├── models/
│   ├── analysis.py         # ProjectModel, ClassInfo, Finding 등 도메인 모델
│   └── project.py
├── services/
│   ├── ast_analyzer.py     # AST 파싱 + 규칙 기반 결함 탐지
│   ├── ts_analyzer.py      # tree-sitter 파서
│   ├── javaparser_sidecar.py  # JavaParser 사이드카 연동
│   ├── embedding.py        # 청킹 + FAISS 임베딩
│   ├── query_refactor.py   # 자연어 → diff 생성
│   ├── refactor_loop.py    # Finding → LLM → apply → 검증 오케스트레이션
│   ├── api_simulator.py    # 가상 API 시뮬레이터
│   ├── depgraph.py         # 의존성 그래프
│   ├── llm.py              # LLM 클라이언트
│   ├── llm_review.py       # LLM 리뷰 유틸
│   ├── project_scanner.py  # 프로젝트 파일 스캐너
│   ├── project_manager.py  # 프로젝트 상태 관리
│   ├── report.py           # 분석 리포트 생성
│   └── verify.py           # 적용 후 검증
├── ui/
│   ├── home.py             # 홈 화면
│   ├── analysis.py         # AST 분석 화면
│   ├── refactor.py         # 리팩토링 화면
│   ├── query.py            # RAG 질의 화면
│   ├── simulator.py        # API 시뮬레이터 화면
│   ├── graph.py            # 의존성 맵 화면
│   ├── project_card.py     # 프로젝트 카드 컴포넌트
│   └── styles/
├── utils/
│   └── workspace.py
└── sidecar/                # JavaParser 사이드카 (Maven)
    ├── pom.xml
    └── src/
```

---

## 👥 팀원

| 이름 | 담당 |
|---|---|
| 고윤 | |
| 나은주 | |
| 김태영 | |

---

## 📄 라이선스

본 프로젝트는 학습 및 연구 목적으로 제작되었습니다.
