# CCL LLM 연동 설계서 — Model-Agnostic Compliance Enhancement

> **Version:** 1.0
> **Status:** Draft
> **대상:** CCL v2.0 기반, LLM 선택적 연동 설계
> **원칙:** 기존 규칙 기반 엔진은 변경 없이 유지. LLM은 보강(augment) 레이어로만 동작.

---

## 1. 배경 및 목적

현재 CCL의 규칙 기반 엔진(Rule-Based Engine)은 고정된 DSL 조건 6개로 컴플라이언스를 판정한다.
이 방식은 결정론적이고 감사 가능하나, 다음 상황에서 한계를 드러낸다.

| 현재 한계                        | 상황 예시                                                    |
| -------------------------------- | ------------------------------------------------------------ |
| 비정형 텍스트 컬럼 분석 불가     | `memo`, `notes`, `description` 등 자유형식 컬럼 내 PII 미탐지 |
| 모호한 컬럼명 해석 불가          | `uid`, `ref_code`, `val1` 등 regex/휴리스틱으로 판별 불가    |
| 준식별자 조합 위험 미탐지        | `age + zip + gender` 조합의 재식별 가능성 판단 불가           |
| UNKNOWN 결과의 맥락 판단 불가    | 보유기간·목적 메타데이터 부재 시 단순 UNKNOWN 반환에 그침      |
| 위반 설명이 고정 텍스트           | 컬럼·데이터 맥락을 반영한 구체적 설명 생성 불가               |

LLM을 선택적으로 연동하면 위 한계를 보완할 수 있다. 단, **LLM은 규칙 엔진을 대체하지 않으며**,
항상 규칙 엔진 실행 이후에 보강 단계로만 동작한다.

---

## 2. 현재 시스템 구조 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CCL v2.0 — 현재 구조                              │
│                                                                             │
│  CLI (click)                                                                │
│  ccl validate --input <file> --law <law_id> [--metadata <json>]            │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       _run_validate()                               │   │
│  │                                                                     │   │
│  │  [1] EXTRACT                  [2] METADATA                         │   │
│  │  ┌──────────────┐             ┌──────────────┐                     │   │
│  │  │ CSVExtractor │             │ JSON sidecar │                     │   │
│  │  │ ParquetExtractor│─────────▶│ retention_days│                   │   │
│  │  └──────┬───────┘             │ purpose_specified│                │   │
│  │         │                     │ consent_present  │                │   │
│  │         │ SampleSchema        └──────────────┘                    │   │
│  │         ▼                                                          │   │
│  │  [3] PII SCAN                                                      │   │
│  │  ┌───────────────────────────────────────────────────┐            │   │
│  │  │ PIIScanner                                        │            │   │
│  │  │  ┌──────────────┐  ┌────────────────────────────┐│            │   │
│  │  │  │ patterns.py  │  │ Column name heuristics     ││            │   │
│  │  │  │ (compiled RE)│  │ (email/phone/rrn/ssn/...)  ││            │   │
│  │  │  └──────────────┘  └────────────────────────────┘│            │   │
│  │  │  → category: SENSITIVE | UNIQUE_ID | DIRECT_ID | GENERAL      │   │
│  │  │  → masked: bool, encrypted: bool                  │            │   │
│  │  └───────────────────────────┬───────────────────────┘            │   │
│  │                              │ SampleSchema (annotated)           │   │
│  │                              ▼                                     │   │
│  │  [4] RULE LOAD & EVAL                                              │   │
│  │  ┌────────────────────┐  ┌──────────────────────────────────────┐ │   │
│  │  │ RuleRegistry       │  │ RuleEvaluator                        │ │   │
│  │  │  law_id            │  │  pii_present()           → bool|None │ │   │
│  │  │  → laws/*.md       │─▶│  any_column(cat, field)  → bool|None │ │   │
│  │  │  LawParser         │  │  retention_exceeded(N)   → bool|None │ │   │
│  │  │  → Rule[]          │  │  purpose_unspecified()   → bool|None │ │   │
│  │  └────────────────────┘  │  consent_missing()       → bool|None │ │   │
│  │                          └──────────────────┬───────────────────┘ │   │
│  │                                             │ Violation[]         │   │
│  │                                             ▼                     │   │
│  │  [5] REPORT                                                        │   │
│  │  ┌──────────────────────────────────────────────────────────────┐ │   │
│  │  │ ReportBuilder                                                │ │   │
│  │  │  status: FAIL > UNKNOWN > PASS                               │ │   │
│  │  │  summary: total / passed / failed / unknown                  │ │   │
│  │  └──────────────────────────────┬───────────────────────────────┘ │   │
│  │                                 │                                  │   │
│  └─────────────────────────────────┼──────────────────────────────────┘   │
│                                    │                                       │
│          ┌─────────────────────────┼──────────────────────┐               │
│          ▼                         ▼                       │               │
│  ┌───────────────┐       ┌──────────────────┐             │               │
│  │  stdout       │       │ AuditLogger      │             │               │
│  │  JSON report  │       │ JSONL append-only│             │               │
│  └───────────────┘       └──────────────────┘             │               │
│                                                            │               │
│  laws/                                                     │               │
│  ├── kr/pipa.md                                            │               │
│  ├── eu/gdpr.md          ← 오프라인 번들, 이미지 내 포함   │               │
│  ├── us/hipaa.md ccpa.md                                   │               │
│  ├── jp/appi.md                                            │               │
│  └── iso/iso27001.md                                       │               │
│                                                            │               │
│  EXIT CODE: 0=PASS  1=FAIL  2=UNKNOWN  3=ERROR            │               │
└────────────────────────────────────────────────────────────────────────────┘

규칙 DSL 조건 (현재 지원):
  pii_present()                                → PII 감지 여부
  any_column(category='X', masked=False)       → 비마스킹 컬럼
  any_column(category='X', encrypted=False)    → 미암호화 컬럼
  retention_exceeded(days=N)                   → 보유기간 초과
  purpose_unspecified()                        → 목적 미명시
  consent_missing()                            → 동의 기록 부재

판정 결과: True(위반) | False(준수) | None(데이터 부족 → UNKNOWN)
```

---

## 3. LLM 연동 시 기능 설계 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CCL + LLM — 연동 아키텍처                               │
│                                                                             │
│  CLI (확장된 옵션)                                                           │
│  ccl validate --input <file> --law <law_id>                                 │
│               --llm-provider {ollama|claude|openai}                         │
│               --llm-model <model>                                           │
│               --llm-endpoint <url>          ← Ollama 전용                   │
│               --llm-mode {enrich|resolve|full}                              │
│               --llm-timeout 30                                              │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  [1~5] 기존 규칙 엔진 (변경 없음)                    │   │
│  │                  EXTRACT → PII SCAN → RULE EVAL → REPORT           │   │
│  └──────────────────────────────────────┬────────────────────────────┘   │
│                                         │ ComplianceReport (draft)        │
│                                         ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    LLM Augmentation Layer                            │  │
│  │                    (--llm-provider 미지정 시 전체 스킵)              │  │
│  │                                                                      │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │ LLMAdapter (인터페이스)                                        │  │  │
│  │  │   complete(prompt: str, schema: dict) → LLMResponse           │  │  │
│  │  │                                                                │  │  │
│  │  │  ┌──────────────────┐ ┌─────────────────┐ ┌───────────────┐ │  │  │
│  │  │  │ OllamaAdapter    │ │ ClaudeAdapter   │ │ OpenAIAdapter │ │  │  │
│  │  │  │                  │ │                 │ │               │ │  │  │
│  │  │  │ endpoint:        │ │ api_key: env    │ │ api_key: env  │ │  │  │
│  │  │  │   localhost:11434│ │   ANTHROPIC_KEY │ │   OPENAI_KEY  │ │  │  │
│  │  │  │ model:           │ │ model:          │ │ model:        │ │  │  │
│  │  │  │   llama3.2       │ │   claude-*      │ │   gpt-4o      │ │  │  │
│  │  │  │   mistral        │ │                 │ │   gpt-4o-mini │ │  │  │
│  │  │  │   qwen2.5        │ │ HTTP POST       │ │               │ │  │  │
│  │  │  │                  │ │   api.anthropic │ │ HTTP POST     │ │  │  │
│  │  │  │ 완전 오프라인    │ │   .com          │ │   api.openai  │ │  │  │
│  │  │  │ 가능             │ │                 │ │   .com        │ │  │  │
│  │  │  └──────────────────┘ └─────────────────┘ └───────────────┘ │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  LLM 활용 모드 (--llm-mode):                                        │  │
│  │                                                                      │  │
│  │  ┌─ enrich ──────────────────────────────────────────────────────┐  │  │
│  │  │ 규칙 엔진 FAIL/UNKNOWN 위반 항목에 자연어 설명 추가           │  │  │
│  │  │ 입력: violation + 해당 컬럼 샘플값 + 법령 원문 요약           │  │  │
│  │  │ 출력: violation.llm_explanation (string)                      │  │  │
│  │  │ 판정 변경 없음 — 기존 FAIL/UNKNOWN 유지                       │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  ┌─ resolve ─────────────────────────────────────────────────────┐  │  │
│  │  │ 규칙 엔진 UNKNOWN 항목을 LLM으로 재평가                       │  │  │
│  │  │ 입력: UNKNOWN violation + schema + metadata + 법령 조항 전문  │  │  │
│  │  │ 출력: {status: FAIL|PASS|UNKNOWN, rationale: string}          │  │  │
│  │  │ LLM이 FAIL 반환 → violation.status = LLM_FAIL                │  │  │
│  │  │ LLM이 PASS 반환 → violation 제거 (단, audit에 기록)           │  │  │
│  │  │ LLM 응답 파싱 실패 → 기존 UNKNOWN 유지 (fail-closed)          │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  ┌─ full ────────────────────────────────────────────────────────┐  │  │
│  │  │ 규칙 엔진 결과 + LLM 독립 분석 병행 실행                      │  │  │
│  │  │                                                                │  │  │
│  │  │  [A] 비정형 텍스트 컬럼 분석                                   │  │  │
│  │  │      GENERAL 카테고리 컬럼의 샘플값을 LLM에 전달              │  │  │
│  │  │      → 숨겨진 PII 여부 판단 (주소, 이름, 진단명 등)           │  │  │
│  │  │                                                                │  │  │
│  │  │  [B] 모호한 컬럼명 재분류                                      │  │  │
│  │  │      regex 미탐지 컬럼(uid, ref, val1 등)의 컨텍스트 분석     │  │  │
│  │  │      → ColumnCategory 재분류 제안                              │  │  │
│  │  │                                                                │  │  │
│  │  │  [C] 준식별자 조합 위험도 평가                                 │  │  │
│  │  │      전체 컬럼 목록 + 카테고리를 LLM에 전달                   │  │  │
│  │  │      → 조합 재식별 위험 컬럼 집합 반환                        │  │  │
│  │  │                                                                │  │  │
│  │  │  [D] UNKNOWN resolve (위의 resolve 모드 포함)                  │  │  │
│  │  │                                                                │  │  │
│  │  │  결과: llm_findings[] 섹션으로 리포트에 분리 추가             │  │  │
│  │  │  기존 violations[] 판정에는 직접 반영하지 않음 (권고 전용)    │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  보안 원칙:                                                          │  │
│  │  - 샘플값 전송 시 최대 N개 값만 전달 (기본: 5개)                  │  │  │
│  │  - 원본 데이터 전체를 LLM에 전송하지 않음                         │  │  │
│  │  - 외부 API 사용 시 --network none 불가 (사용자 인지 경고)        │  │  │
│  │  - Ollama 사용 시 오프라인 원칙 유지 가능                         │  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                         │                                   │
│                                         ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 최종 ComplianceReport (확장)                                         │  │
│  │                                                                      │  │
│  │  violations[]:         기존 규칙 엔진 결과 (변경 없음)              │  │
│  │    status: FAIL | UNKNOWN | PASS                                     │  │
│  │    llm_explanation: string  ← enrich/resolve/full 모드 시 추가     │  │
│  │                                                                      │  │
│  │  llm_findings[]:       LLM 독립 발견 (full 모드만)                 │  │
│  │    finding_type: UNSTRUCTURED_PII | AMBIGUOUS_COLUMN | QUASI_ID     │  │
│  │    column: string                                                    │  │
│  │    rationale: string                                                 │  │
│  │    severity: HIGH | MEDIUM | LOW                                     │  │
│  │    source: "llm:<provider>/<model>"                                 │  │
│  │                                                                      │  │
│  │  llm_meta:             LLM 연동 메타정보                            │  │
│  │    provider: ollama | claude | openai                                │  │
│  │    model: string                                                     │  │
│  │    mode: enrich | resolve | full                                     │  │
│  │    tokens_used: int                                                  │  │
│  │    latency_ms: int                                                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  EXIT CODE: 규칙 엔진 결과 기준 (LLM findings는 exit code에 미영향)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 컴포넌트 설계

### 4.1 LLMAdapter 인터페이스

```
LLMAdapter (Protocol)
│
├── complete(prompt: str) → LLMResponse
│     LLMResponse:
│       content: str          ← 모델 원문 응답
│       tokens_used: int
│       latency_ms: int
│
├── health_check() → bool     ← 연결 가능 여부 사전 확인
│
└── metadata() → dict
      provider: str
      model: str
      endpoint: str | None
```

**구현체별 연동 방식:**

| 구현체 | 연결 방식 | 인증 | 오프라인 가능 |
|---|---|---|---|
| `OllamaAdapter` | HTTP POST `http://<endpoint>/api/chat` | 없음 | ✅ (로컬 실행 시) |
| `ClaudeAdapter` | HTTPS `api.anthropic.com/v1/messages` | `ANTHROPIC_API_KEY` 환경변수 | ❌ |
| `OpenAIAdapter` | HTTPS `api.openai.com/v1/chat/completions` | `OPENAI_API_KEY` 환경변수 | ❌ |

### 4.2 프롬프트 구조 설계

LLM에 전달하는 프롬프트는 세 부분으로 구성된다.

```
[SYSTEM]
You are a data compliance analyst. Analyze the provided dataset schema and respond
only in structured JSON matching the requested format. Do not include explanation
outside the JSON block.

[CONTEXT]
Law: {law_id} ({law_version})
Article: {article}
Article text: {article_summary}
Rule condition: {rule_condition}

Dataset schema:
- column: {name}, category: {category}, sample_values: [{v1}, {v2}, ...]
...

[TASK]
<mode별 태스크 정의>
```

**모드별 태스크 정의:**

```
enrich:
  Explain in Korean (max 3 sentences) why the column '{column}'
  violates {article} given the sample values provided.
  Respond: {"explanation": "..."}

resolve:
  Given the context, determine if the data LIKELY violates {article}.
  Respond: {"status": "FAIL" | "PASS" | "UNKNOWN", "rationale": "..."}

full - unstructured PII:
  Identify any PII in the column values below (free-form text).
  Classify each finding: name | address | health | financial | other.
  Respond: {"findings": [{"type": "...", "evidence": "..."}]}

full - quasi-identifier:
  Given these columns and categories, identify sets of columns that
  together could re-identify individuals (quasi-identifiers).
  Respond: {"quasi_id_sets": [["col1", "col2"], ...], "risk": "HIGH|MEDIUM|LOW"}
```

### 4.3 실패 처리 원칙

```
LLM 호출 실패 시 처리 흐름:

  LLM 호출
       │
       ├── 타임아웃 초과      → 기존 결과 유지 + audit에 llm_error 기록
       ├── API 오류 (4xx/5xx) → 기존 결과 유지 + audit에 llm_error 기록
       ├── JSON 파싱 실패     → 기존 결과 유지 + audit에 llm_parse_error 기록
       └── 성공              → 응답 적용
```

규칙 엔진 결과는 LLM 오류와 무관하게 항상 출력된다.

### 4.4 데이터 최소화 원칙 (샘플 전송)

외부 LLM API 호출 시 원본 데이터 전체를 전송하지 않는다.

```
전송 대상:
  - 컬럼명, 탐지 카테고리, masked/encrypted 여부
  - 샘플값: 최대 5개, 각 최대 64자로 truncate
  - 법령 조항 요약 (laws/*.md 내 Summary 섹션)

전송 금지:
  - 원본 파일 전체
  - 행 수 초과 샘플 (--llm-max-samples 옵션으로 제한)
  - audit log 내용
```

---

## 5. CLI 옵션 확장 명세

현재 `ccl validate` 옵션에 추가할 플래그:

```
--llm-provider     TEXT     LLM 공급자: ollama | claude | openai
                            (미지정 시 LLM 기능 전체 비활성화)

--llm-model        TEXT     모델명
                            ollama 예: llama3.2, mistral, qwen2.5
                            claude 예: claude-opus-4-6, claude-sonnet-4-6
                            openai 예: gpt-4o, gpt-4o-mini

--llm-endpoint     TEXT     Ollama 서버 주소 (기본: http://localhost:11434)
                            claude/openai 에는 무시됨

--llm-mode         TEXT     동작 모드 (기본: enrich)
                            enrich   — 위반 항목 자연어 설명 추가
                            resolve  — UNKNOWN 항목 재평가
                            full     — 비정형/모호/준식별자 분석 포함

--llm-max-samples  INT      LLM에 전달하는 최대 샘플값 수 (기본: 5)

--llm-timeout      INT      LLM API 호출 타임아웃 (초, 기본: 30)
```

**실행 예시:**

```bash
# Ollama (로컬, 오프라인 유지)
ccl validate --input data.csv --law gdpr \
  --llm-provider ollama \
  --llm-model llama3.2 \
  --llm-mode resolve

# Claude API (UNKNOWN 해소 + 설명 생성)
ANTHROPIC_API_KEY=sk-... \
ccl validate --input data.parquet --law kr-pipa --law iso27001 \
  --llm-provider claude \
  --llm-model claude-sonnet-4-6 \
  --llm-mode enrich

# OpenAI (전체 분석)
OPENAI_API_KEY=sk-... \
ccl validate --input data.csv --law gdpr \
  --llm-provider openai \
  --llm-model gpt-4o \
  --llm-mode full \
  --llm-max-samples 3
```

---

## 6. 출력 스키마 확장

기존 `ComplianceReport` JSON에 다음 필드가 추가된다.

```json
{
  "dataset_id": "...",
  "status": "FAIL",
  "violations": [
    {
      "rule_id": "GDPR-ART9-001",
      "status": "FAIL",
      "column": "health_notes",
      "llm_explanation": "health_notes 컬럼에 '당뇨병 진단', '혈압 측정' 등 건강정보가
                          비마스킹 상태로 저장되어 있어 GDPR Article 9의 특별범주 데이터
                          처리 제한 요건을 위반합니다."
    }
  ],

  "llm_findings": [
    {
      "finding_type": "UNSTRUCTURED_PII",
      "column": "memo",
      "rationale": "샘플값 '홍길동, 서울시 강남구 거주, 010-xxxx' 등에서 성명·주소·연락처가
                    자유형식 텍스트에 포함되어 있습니다.",
      "severity": "HIGH",
      "source": "llm:ollama/llama3.2"
    },
    {
      "finding_type": "QUASI_IDENTIFIER",
      "columns": ["age", "zip_code", "gender"],
      "rationale": "세 컬럼의 조합은 전체 인구의 87%를 유일하게 식별할 수 있는
                    준식별자 집합에 해당합니다 (Sweeney 1997 기준).",
      "severity": "MEDIUM",
      "source": "llm:claude/claude-sonnet-4-6"
    }
  ],

  "llm_meta": {
    "provider": "ollama",
    "model": "llama3.2",
    "endpoint": "http://localhost:11434",
    "mode": "full",
    "tokens_used": 1842,
    "latency_ms": 3210,
    "errors": []
  }
}
```

---

## 7. 모드별 기능 비교

| 항목 | 규칙 엔진만 (현재) | + enrich | + resolve | + full |
|---|---|---|---|---|
| PII 탐지 (정형) | ✅ regex + 휴리스틱 | ✅ | ✅ | ✅ |
| 위반 판정 | ✅ 결정론적 | ✅ | ✅ | ✅ |
| 위반 설명 | 고정 텍스트 | LLM 생성 | LLM 생성 | LLM 생성 |
| UNKNOWN 재평가 | ❌ | ❌ | ✅ LLM 판단 | ✅ LLM 판단 |
| 비정형 텍스트 분석 | ❌ | ❌ | ❌ | ✅ |
| 모호한 컬럼명 해석 | ❌ | ❌ | ❌ | ✅ |
| 준식별자 조합 탐지 | ❌ | ❌ | ❌ | ✅ |
| 오프라인 실행 | ✅ | Ollama만 | Ollama만 | Ollama만 |
| 결정론적 판정 | ✅ | ✅ (판정 불변) | 부분적 | 부분적 |
| 추가 지연시간 | 없음 | 중간 | 중간 | 높음 |
| 감사 추적 가능 | ✅ | ✅ | ✅ (rationale 기록) | ✅ |

---

## 8. 구현 단계 계획

### Phase 1 — 어댑터 기반 + enrich 모드

- `LLMAdapter` 프로토콜 정의
- `OllamaAdapter`, `ClaudeAdapter`, `OpenAIAdapter` 구현
- `enrich` 모드: 기존 violations에 `llm_explanation` 필드 추가
- CLI 옵션 추가 (`--llm-provider`, `--llm-model`, `--llm-endpoint`, `--llm-mode`)
- `llm_meta` 출력 필드 추가

### Phase 2 — resolve 모드

- UNKNOWN violations 필터링 → 프롬프트 생성 → LLM 재평가
- `LLM_FAIL` / `LLM_PASS` 상태 구분 (감사 추적용)
- 응답 파싱 실패 시 fallback 처리

### Phase 3 — full 모드

- 비정형 텍스트 컬럼 분석 파이프라인
- 모호한 컬럼명 재분류 제안
- 준식별자 조합 위험도 평가
- `llm_findings[]` 출력 섹션 추가

---

## 9. 제약 및 유의사항

| 항목 | 내용 |
|---|---|
| 판정 권위 | LLM 결과는 **참고용**. 규칙 엔진 FAIL은 LLM이 PASS를 반환해도 exit code 1 유지 |
| 외부 API 사용 시 네트워크 격리 | `--network none` 적용 불가 — 사용자에게 경고 출력 필수 |
| 오프라인 원칙 유지 | Ollama 로컬 모드 사용 시만 기존 offline-first 원칙 충족 |
| 응답 형식 의존 | JSON 파싱 실패 시 항상 기존 결과 유지 (fail-closed) |
| 토큰 비용 | 컬럼 수·샘플 수 비례. `--llm-max-samples` 로 제어 |
| 모델 비결정성 | 동일 입력에 대해 LLM 응답이 달라질 수 있음 — audit log에 모델/버전 기록 필수 |
| 법적 효력 | LLM 분석 결과는 법적 컴플라이언스 판단의 최종 근거가 될 수 없음 |
