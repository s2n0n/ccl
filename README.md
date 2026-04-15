# CCL — Compliance Checker Legalized

오프라인 우선 데이터 컴플라이언스 검증 엔진. 외부 API 없이 데이터셋이 GDPR, HIPAA, 개인정보보호법 등 각국 개인정보 보호법을 준수하는지 검사합니다. 선택적으로 로컬 LLM(Ollama) 또는 클라우드 API(Claude, OpenAI)를 연동하여 위반 설명 생성·UNKNOWN 재평가·비정형 PII 탐지를 수행할 수 있습니다.

## 특징

- **오프라인 우선**: 법령 번들이 Docker 이미지에 내장 — 기본 모드에서 네트워크 불필요
- **Fail-Closed**: 준수 여부를 판단할 수 없을 경우 기본값 FAIL (안전 우선)
- **읽기 전용**: 데이터를 수정하지 않고 분석만 수행
- **다중 관할권**: GDPR, HIPAA, 개인정보보호법(한국), APPI(일본), CCPA, ISO 27001 지원
- **감사 로그**: 변경 불가능한 JSONL 감사 추적
- **모델 무관 LLM 보강**: Ollama / Claude / OpenAI를 선택적으로 연동하여 분석 품질 향상

## 지원 법령

| 법령 ID | 법령 | 관할권 |
|---------|------|--------|
| `kr-pipa` | 개인정보 보호법 | 한국 |
| `gdpr` | General Data Protection Regulation | EU |
| `ccpa` | California Consumer Privacy Act | 미국(캘리포니아) |
| `hipaa` | Health Insurance Portability and Accountability Act | 미국 |
| `jp-appi` | Act on Protection of Personal Information | 일본 |
| `iso27001` | ISO/IEC 27001:2022 Information Security Management | 국제 |

## 설치

```bash
# 저장소 클론
git clone <repo-url>
cd ccl

# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements-dev.txt
pip install -e .

# 설치 확인
ccl --version
```

**요구사항:** Python 3.12+, Docker 20.10+

## 빠른 시작

```bash
# CSV 파일을 한국 개인정보보호법으로 검사
ccl validate --input data.csv --law kr-pipa

# 메타데이터 사이드카와 함께 실행
ccl validate \
  --input data.csv \
  --law kr-pipa \
  --metadata metadata.json \
  --output report.json

# 여러 법령 동시 적용
ccl validate \
  --input data.parquet \
  --law gdpr \
  --law kr-pipa \
  --output report.json

# CI/CD: 위반 발견 시 exit code 1
ccl validate --input data.csv --law kr-pipa --fail-on-violation
```

### Docker로 실행

```bash
# 이미지 빌드
docker build -t ccl:latest .

# 네트워크 차단, 읽기 전용 마운트로 실행
docker run --rm \
  --network none \
  --read-only \
  -v /path/to/data.csv:/data/input.csv:ro \
  ccl:latest \
  validate --input /data/input.csv --law kr-pipa
```

---

## LLM 보강 기능

규칙 기반 엔진의 결과를 LLM으로 보강합니다. **규칙 엔진은 항상 먼저 실행**되며, LLM은 그 이후 선택적 보강 레이어로만 동작합니다. LLM 오류가 발생해도 규칙 엔진 결과는 그대로 출력됩니다.

### 지원 제공자

| 제공자 | 옵션 값 | 인증 | 오프라인 가능 |
|--------|---------|------|--------------|
| Ollama (로컬 LLM) | `ollama` | 없음 | ✅ |
| Anthropic Claude | `claude` | `ANTHROPIC_API_KEY` 환경변수 | ❌ |
| OpenAI | `openai` | `OPENAI_API_KEY` 환경변수 | ❌ |

### 보강 모드

| 모드 | 설명 |
|------|------|
| `enrich` | FAIL 위반 항목마다 한국어 설명(`llm_explanation`) 추가. 판정 변경 없음 |
| `resolve` | UNKNOWN 위반 항목을 LLM이 재평가하여 `LLM_FAIL` 또는 `LLM_PASS`로 판정 |
| `full` | enrich + resolve + 비정형 텍스트 PII 탐지 + 준식별자 조합 위험도 분석 |

> **exit code는 항상 규칙 엔진 결과 기준**입니다. LLM 판정은 리포트에 참고용으로만 기록됩니다.

### 사용 예시

#### Ollama — 로컬 실행 (오프라인 유지)

```bash
# Ollama 설치 및 모델 준비
ollama pull llama3.2

# FAIL 위반 항목에 한국어 설명 추가
ccl validate \
  --input data.csv \
  --law kr-pipa \
  --llm-provider ollama \
  --llm-model llama3.2 \
  --llm-mode enrich

# UNKNOWN 항목 재평가
ccl validate \
  --input data.csv \
  --law gdpr \
  --llm-provider ollama \
  --llm-model llama3.2 \
  --llm-mode resolve

# 전체 분석 (비정형 PII + 준식별자 포함)
ccl validate \
  --input data.csv \
  --law iso27001 \
  --llm-provider ollama \
  --llm-model mistral \
  --llm-mode full
```

#### Claude API

```bash
export ANTHROPIC_API_KEY=sk-ant-...

ccl validate \
  --input data.csv \
  --law kr-pipa \
  --law gdpr \
  --llm-provider claude \
  --llm-model claude-sonnet-4-6 \
  --llm-mode enrich \
  --output report.json
```

#### OpenAI API

```bash
export OPENAI_API_KEY=sk-...

ccl validate \
  --input data.parquet \
  --law gdpr \
  --llm-provider openai \
  --llm-model gpt-4o \
  --llm-mode full \
  --llm-max-samples 3
```

### LLM 포함 출력 예시

```json
{
  "dataset_id": "customer_data",
  "law_bundle_version": "kr-pipa=2023-09-15",
  "jurisdiction": ["KR-PIPA"],
  "status": "FAIL",
  "violations": [
    {
      "rule_id": "KR-PIPA-ART23-001",
      "article": "개인정보보호법 제23조 (민감정보 처리 제한)",
      "description": "민감정보(건강정보)가 마스킹되지 않음",
      "severity": "HIGH",
      "status": "FAIL",
      "column": "health_status",
      "sample_count": null,
      "llm_explanation": "health_status 컬럼에 '당뇨병', '고혈압' 등 건강정보가 평문으로 저장되어 있습니다. 개인정보보호법 제23조는 건강정보를 민감정보로 분류하여 원칙적으로 처리를 금지하며, 처리 시 마스킹 또는 별도 동의가 필요합니다."
    }
  ],
  "llm_findings": [
    {
      "finding_type": "UNSTRUCTURED_PII",
      "column": "memo",
      "rationale": "[contact] '010-1234-5678' 형태의 전화번호가 자유형식 텍스트에 포함되어 있습니다.",
      "severity": "MEDIUM",
      "source": "llm:ollama/llama3.2"
    },
    {
      "finding_type": "QUASI_IDENTIFIER",
      "columns": ["age", "zip_code", "gender"],
      "rationale": "컬럼 ['age', 'zip_code', 'gender'] 조합은 개인을 재식별할 수 있는 준식별자 집합입니다. 위험도: HIGH",
      "severity": "HIGH",
      "source": "llm:ollama/llama3.2"
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
  },
  "summary": {
    "total_checks": 6,
    "passed": 4,
    "failed": 2,
    "unknown": 0
  },
  "timestamp": "2025-04-15T12:34:56.789Z",
  "engine_version": "2.0.0"
}
```

---

## CLI 옵션

```
ccl validate [OPTIONS]
```

### 기본 옵션

| 옵션 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--input PATH` | Y | — | 입력 데이터 파일 (CSV 또는 Parquet) |
| `--law TEXT` | Y | — | 적용 법령 ID (반복 사용 가능) |
| `--metadata PATH` | N | — | JSON 메타데이터 파일 (`retention_days`, `purpose_specified`, `consent_records_present`) |
| `--output PATH` | N | stdout | 결과 보고서 저장 경로 |
| `--audit-log PATH` | N | stderr | 감사 로그 저장 경로 (JSONL) |
| `--fail-on-violation` | N | False | 위반 발견 시 exit code 1 반환 |
| `--sample-rows INT` | N | 500 | PII 스캔에 사용할 샘플 행 수 |

### LLM 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--llm-provider TEXT` | — (비활성) | LLM 제공자: `ollama` \| `claude` \| `openai` |
| `--llm-model TEXT` | 제공자별 기본값 | 모델명 (예: `llama3.2`, `claude-sonnet-4-6`, `gpt-4o`) |
| `--llm-endpoint TEXT` | `http://localhost:11434` | Ollama 서버 주소 (cloud 제공자는 무시) |
| `--llm-mode TEXT` | `enrich` | 보강 모드: `enrich` \| `resolve` \| `full` |
| `--llm-max-samples INT` | `5` | 컬럼당 LLM에 전달하는 최대 샘플 수 |
| `--llm-timeout INT` | `30` | LLM API 호출 타임아웃 (초) |

**제공자별 기본 모델:**

| 제공자 | 기본 모델 |
|--------|-----------|
| `ollama` | `llama3.2` |
| `claude` | `claude-sonnet-4-6` |
| `openai` | `gpt-4o-mini` |

## 출력 예시 (규칙 엔진만)

```json
{
  "dataset_id": "customer_data",
  "law_bundle_version": "kr-pipa=2023-09-15",
  "jurisdiction": ["KR-PIPA"],
  "status": "FAIL",
  "violations": [
    {
      "rule_id": "KR-PIPA-ART23-001",
      "article": "개인정보보호법 제23조 (민감정보 처리 제한)",
      "description": "민감정보(건강정보)가 마스킹되지 않음",
      "severity": "HIGH",
      "status": "FAIL",
      "column": "health_status",
      "sample_count": null,
      "llm_explanation": null
    }
  ],
  "llm_findings": [],
  "llm_meta": null,
  "summary": {
    "total_checks": 6,
    "passed": 4,
    "failed": 2,
    "unknown": 0
  },
  "timestamp": "2025-04-15T12:34:56.789Z",
  "engine_version": "2.0.0"
}
```

## 종료 코드

종료 코드는 항상 규칙 엔진 결과 기준입니다. LLM 판정은 영향을 주지 않습니다.

| 코드 | 의미 |
|------|------|
| `0` | PASS — 위반 없음 |
| `1` | FAIL — 위반 발견 |
| `2` | UNKNOWN — 판단 불가 (수동 검토 필요) |
| `3` | ERROR — 실행 오류 |

## 아키텍처

```
입력 데이터 (CSV/Parquet)
        ↓
   [EXTRACTOR]      ← 읽기 전용 데이터 샘플링
        ↓
   [PII SCANNER]    ← 정규식 기반 PII 탐지 및 분류
        ↓
  [RULE ENGINE]     ← 법령 로드, 규칙 파싱, 조건 평가
        ↓
    [REPORT]        ← status/summary/exit_code 확정 (규칙 엔진 기준)
        ↓
  [LLM AUGMENTOR]  ← 선택적 보강 (--llm-provider 지정 시만 실행)
  │  enrich  : FAIL 위반 항목에 자연어 설명 추가
  │  resolve : UNKNOWN 항목 LLM 재평가
  │  full    : + 비정형 PII 탐지 + 준식별자 분석
  │
  ├─ OllamaAdapter  (로컬, 오프라인)
  ├─ ClaudeAdapter  (ANTHROPIC_API_KEY)
  └─ OpenAIAdapter  (OPENAI_API_KEY)
        ↓
  [AUDIT LOG]       ← 변경 불가능한 JSONL 감사 로그
        ↓
   JSON 보고서 (PASS/FAIL/UNKNOWN)
```

## 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ --cov=src/ccl --cov-report=html
```

## 메타데이터 파일 형식

```json
{
  "retention_days": 365,
  "purpose_specified": true,
  "consent_records_present": true
}
```

## 라이선스

[LICENSE 파일 참조]
