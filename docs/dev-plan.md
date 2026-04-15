# Compliance Checker Legalized (CCL) — System Design Document

> **Version:** 2.0  
> **Goal:** 외부 API 의존 없이 번들된 법령 기반으로 데이터 컴플라이언스만 검증하는 독립 실행형 엔진  
> **Distribution:** Docker Public Registry (offline-capable)

---

## 1. Overview

CCL(Compliance Checker Legalized)은 저장된 데이터에 대해 각 국가별 법령을 기반으로 컴플라이언스 검증을 수행하는 **독립 실행형 오픈소스 엔진**이다.

### 핵심 설계 방향

| 항목          | 기존 방식                | 최적화 방향                                |
| ------------- | ------------------------ | ------------------------------------------ |
| 법령 조회     | 런타임 MCP/외부 API 호출 | **번들 법령 파일(`.md`) 로컬 로드**        |
| 실행 환경     | 범용 서버                | **Docker 컨테이너 (Public Registry 배포)** |
| 네트워크 요구 | 외부 접근 필요           | **완전 오프라인 실행 가능**                |
| 검증 범위     | 폭넓은 정책 적용         | **데이터 컴플라이언스 검증만**             |

### 시스템 목표

- **Post-ingestion validation only** — 적재된 데이터만 검증, 실시간 트래픽 무영향
- **Offline-first** — 법령은 이미지에 번들, 외부 API 호출 없음
- **Fail-closed** — 판단 불가 시 무조건 FAIL
- **Immutable execution** — 데이터 변경 없음, read-only

---

## 2. Design Principles

### 2.1 Offline-First Law Bundle

- 법령 텍스트를 `.md` 파일로 미리 가공하여 이미지에 포함
- 런타임 외부 API 호출 **Zero** (MCP 의존 제거)
- 법령 갱신은 **이미지 재빌드**를 통해 관리 (버전 태그로 추적)

### 2.2 Safety First (Fail Closed)

- 위반 또는 판단 불가 시 → 무조건 `FAIL`
- 외부 시스템에 영향 없이 실행

### 2.3 Isolation by Default

- 모든 검증은 컨테이너 샌드박스 환경에서 수행
- 네트워크 egress 완전 차단 (오프라인 모드 기본값)

### 2.4 Post-Data Validation Only

- 입력 데이터가 아닌 "**적재된 데이터**"만 검증
- 실시간 트래픽 영향 없음

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CCL Docker Image                        │
│                                                             │
│  ┌──────────────┐    ┌───────────────────────────────────┐  │
│  │ Law Bundle   │    │         Execution Engine          │  │
│  │ /laws/       │    │                                   │  │
│  │  kr-pipa.md  │───▶│  ┌────────────┐ ┌─────────────┐  │  │
│  │  gdpr.md     │    │  │ PII Scanner│ │Policy Engine│  │  │
│  │  appi.md     │    │  └─────┬──────┘ └──────┬──────┘  │  │
│  └──────────────┘    │        │                │         │  │
│                      │        ▼                ▼         │  │
│  ┌──────────────┐    │  ┌──────────────────────────────┐ │  │
│  │  Input Data  │───▶│  │   Compliance Decision        │ │  │
│  │ (Read-only)  │    │  │   (PASS / FAIL / UNKNOWN)    │ │  │
│  └──────────────┘    │  └──────────────┬───────────────┘ │  │
│                      │                 │                  │  │
│                      │                 ▼                  │  │
│                      │  ┌──────────────────────────────┐ │  │
│                      │  │        Audit Logger          │ │  │
│                      │  └──────────────────────────────┘ │  │
│                      └───────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**외부 API 호출 없음. 모든 컴포넌트가 컨테이너 내부에서 동작.**

---

## 4. Law Bundle Strategy

### 4.1 번들 구조

법령 원문을 정규화된 `.md` 파일로 미리 가공하여 이미지에 포함한다.

```
/laws/
├── kr/
│   ├── personal-information-protection-act.md   # 개인정보 보호법
│   ├── credit-information-use-act.md            # 신용정보법
│   └── network-utilization-act.md               # 정보통신망법
├── eu/
│   ├── gdpr.md                                  # GDPR
│   └── ai-act.md                                # EU AI Act
├── us/
│   ├── ccpa.md                                  # CCPA
│   └── hipaa.md                                 # HIPAA
└── jp/
    └── appi.md                                  # 개인정보보호법 (일본)
```

### 4.2 법령 파일 포맷 (`.md` 표준)

각 법령 파일은 다음 구조를 따른다:

```markdown
---
law_id: KR-PIPA
jurisdiction: KR
version: "2023-09-15"
source_url: https://www.law.go.kr/법령/개인정보보호법
---

# 개인정보 보호법 (컴플라이언스 참조본)

## Article 23 — 민감정보 처리 제한

**원문 요약:** 사상·신념, 노동조합·정당 가입/탈퇴, 정치적 견해, 건강, 성생활,
유전정보, 범죄경력, 생체인식정보는 원칙적으로 처리 금지.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART23-001
- check: sensitive_category IN dataset
- action: FAIL if not explicitly consented

## Article 24 — 고유식별정보 처리 제한
...
```

### 4.3 법령 갱신 프로세스

```
법령 개정 감지 (수동/자동)
        │
        ▼
laws/*.md 파일 수정
        │
        ▼
docker build --tag ccl:YYYY-MM-DD
        │
        ▼
docker push ghcr.io/org/ccl:YYYY-MM-DD
        │
        ▼
사용자: docker pull → 최신 법령 적용
```

> **버전 태그 규칙:** `ghcr.io/org/ccl:2025-10-01-kr` (날짜 + 관할권)

---

## 5. Core Components

### 5.1 Data Extractor

- **Read-only** 접근만 허용
- SQL / Snapshot / Export 기반
- Production DB 직접 접근 금지 (Replica 또는 Export 파일 사용)

**허용 입력 타입:**

| 형식                 | 허용 | 비고           |
| -------------------- | ---- | -------------- |
| CSV                  | ✅   | sanitized 필수 |
| Parquet              | ✅   |                |
| DB Read Replica      | ✅   |                |
| Direct API ingestion | ❌   | 금지           |
| Streaming            | ❌   | 금지           |
| Live query execution | ❌   | 금지           |

### 5.2 Secure Sandbox (Docker)

- 컨테이너 기반 실행
- **네트워크 egress 완전 차단** (`--network none`)
- CPU / Memory 제한
- Read-only filesystem (입력 데이터 mountpoint 제외)
- Ephemeral runtime (실행 후 컨테이너 삭제)

### 5.3 PII Scanner

데이터 내 민감정보 탐지 (외부 API 없이 로컬 실행)

**탐지 범위:**

- Direct Identifiers: email, phone, SSN, 주민등록번호
- Indirect Identifiers: 날짜 + 지역 조합, context-based
- Sensitive Categories: 건강정보, 생체정보, 정치적 견해

**탐지 방법 (로컬 실행 전용):**

- Regex 기반 탐지 (기본)
- spaCy / 내장 NLP 모델 (optional, 이미지에 번들)
- 외부 LLM API 호출 **금지**

### 5.4 Policy Engine

법령 파일(`.md`)을 파싱하여 검증 룰로 변환

```
/laws/kr/personal-information-protection-act.md
        │
        ▼ (LawParser)
┌──────────────────────────────┐
│  Rule Set                    │
│  - KR-PIPA-ART23-001        │
│  - KR-PIPA-ART24-001        │
│  - KR-PIPA-ART29-001        │
└──────────────────────────────┘
        │
        ▼ (RuleEvaluator)
┌──────────────────────────────┐
│  Data Sample                 │
│  + Rule Evaluation           │
│  → PASS / FAIL / UNKNOWN     │
└──────────────────────────────┘
```

**룰 DSL 예시 (Rego-style):**

```rego
# KR-PIPA-ART23-001
deny[msg] {
    input.columns[_].category == "sensitive"
    input.columns[_].masked == false
    msg := "민감정보가 마스킹되지 않음 (개인정보보호법 제23조 위반)"
}

# KR-PIPA-ART29-001
deny[msg] {
    input.retention_days > 365
    input.purpose_specified == false
    msg := "보유기간 초과 또는 목적 미명시"
}
```

---

## 6. Docker Distribution

### 6.1 이미지 구성

```dockerfile
FROM python:3.12-slim

# 법령 번들 복사
COPY laws/ /app/laws/

# 의존성 (오프라인 실행 전용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 엔진 소스
COPY src/ /app/src/

WORKDIR /app
ENTRYPOINT ["python", "-m", "ccl.cli"]
```

### 6.2 퍼블릭 레지스트리 배포

```
ghcr.io/org/ccl:latest          # 최신 (모든 법령)
ghcr.io/org/ccl:kr-latest       # 한국 법령만
ghcr.io/org/ccl:eu-latest       # EU 법령만
ghcr.io/org/ccl:2025-10-01      # 날짜 고정 버전
```

### 6.3 실행 예시

```bash
# 기본 실행 (네트워크 차단)
docker run --rm \
  --network none \
  --read-only \
  -v /path/to/data.csv:/data/input.csv:ro \
  ghcr.io/org/ccl:kr-latest \
  validate --input /data/input.csv --law kr-pipa

# CI/CD 통합
docker run --rm \
  --network none \
  -v $(pwd)/export.parquet:/data/input.parquet:ro \
  ghcr.io/org/ccl:latest \
  validate --input /data/input.parquet --output /tmp/report.json
```

---

## 7. Compliance Validation Scope

### 7.1 검증 항목

| Check ID    | 설명                     | 근거 법령                  |
| ----------- | ------------------------ | -------------------------- |
| PII-001     | PII 존재 여부            | KR-PIPA Art.2, GDPR Art.4  |
| PII-002     | 민감정보 마스킹 여부     | KR-PIPA Art.23, GDPR Art.9 |
| PII-003     | 고유식별정보 암호화 여부 | KR-PIPA Art.24             |
| RETAIN-001  | 보유기간 초과 여부       | KR-PIPA Art.21             |
| PURPOSE-001 | 목적 외 사용 가능성      | KR-PIPA Art.18             |
| CONSENT-001 | 동의 기록 누락 여부      | GDPR Art.7                 |

### 7.2 검증 범위 명시적 제외

- 시스템 보안 취약점 스캔 (범위 외)
- 코드 정적 분석 (범위 외)
- 실시간 트래픽 모니터링 (범위 외)
- 법적 자문 / 최종 법령 해석 (인간 전문가 필요)

---

## 8. Output Specification

```json
{
  "dataset_id": "string",
  "law_bundle_version": "2025-10-01",
  "jurisdiction": ["KR", "EU"],
  "status": "PASS | FAIL | UNKNOWN",
  "violations": [
    {
      "rule_id": "KR-PIPA-ART23-001",
      "article": "개인정보보호법 제23조",
      "description": "민감정보(건강정보)가 마스킹되지 않음",
      "severity": "HIGH",
      "column": "health_status",
      "sample_count": 142
    }
  ],
  "summary": {
    "total_checks": 12,
    "passed": 10,
    "failed": 2,
    "unknown": 0
  },
  "timestamp": "2025-10-01T12:00:00Z",
  "engine_version": "2.0.0"
}
```

---

## 9. CI/CD Integration

### 9.1 GitHub Actions 예시

```yaml
- name: Run CCL Compliance Check
  run: |
    docker run --rm \
      --network none \
      -v ${{ github.workspace }}/data-export:/data:ro \
      ghcr.io/org/ccl:kr-latest \
      validate --input /data/snapshot.parquet \
               --output /tmp/ccl-report.json \
               --fail-on-violation

- name: Upload Report
  uses: actions/upload-artifact@v3
  with:
    name: ccl-report
    path: /tmp/ccl-report.json
```

### 9.2 종료 코드 규칙

| 코드 | 의미                              |
| ---- | --------------------------------- |
| 0    | PASS — 위반 없음                  |
| 1    | FAIL — 위반 감지                  |
| 2    | UNKNOWN — 판단 불가 (데이터 부족) |
| 3    | ERROR — 실행 오류                 |

---

## 10. Security Controls

### 10.1 System Safety

- No write-back to source
- No mutation of data
- Immutable execution environment

### 10.2 Data Safety

- In-memory processing only
- No persistent storage
- 컨테이너 종료 시 모든 임시 데이터 삭제

### 10.3 Network Isolation

- 기본값: `--network none` (완전 오프라인)
- 법령 조회 외부 API 호출 없음
- 외부 LLM/AI API 호출 없음

### 10.4 Access Control

- RBAC for execution trigger
- Audit trail 필수 (변경 불가 로그)

---

## 11. Extensibility

- **새 법령 추가:** `/laws/<jurisdiction>/` 에 `.md` 파일 추가 후 이미지 재빌드
- **새 관할권 추가:** 동일 구조로 확장
- **정책 DSL 확장:** Rule evaluator 플러그인 방식 지원
- **오프라인 NLP 모델 교체:** 이미지 레이어 분리로 독립 업데이트 가능

---

## 12. Risks & Limitations

| 리스크                      | 설명                  | 완화 방안                         |
| --------------------------- | --------------------- | --------------------------------- |
| 법령 해석 모호성            | 자동 해석의 한계      | 법령 파일 주석으로 해석 근거 명시 |
| 법령 번들 최신성            | 이미지 갱신 주기 지연 | 날짜 버전 태그 + CHANGELOG 관리   |
| 완전 자동 컴플라이언스 불가 | 맥락 판단 한계        | UNKNOWN 결과 → 인간 검토 필수     |
| 이미지 크기 증가            | 법령 번들 + NLP 모델  | 관할권별 slim 태그 제공           |

---

## 13. Future Enhancements

- **법령 파일 자동 갱신 CI:** 공식 법령 포털 크롤링 → MD 변환 파이프라인
- **Differential compliance analysis:** 이전 검증 결과 대비 변화 감지
- **SBOM(Software Bill of Materials) for Laws:** 어떤 법령 버전으로 검증했는지 추적
- **Multi-jurisdiction parallel check:** 단일 데이터셋에 복수 법령 동시 검증

---

## Appendix A: Design Checklist

- [ ] 법령 파일 번들 완료 (`/laws/` 디렉토리)
- [ ] 외부 API 호출 없음 검증 (네트워크 격리 테스트)
- [ ] Read-only data access 보장
- [ ] Docker 이미지 퍼블릭 레지스트리 배포
- [ ] Fail-closed 동작 검증
- [ ] Audit logging 활성화
- [ ] 법령 버전 태그 관리 체계 수립
- [ ] CI/CD 파이프라인 통합 테스트

---

## Appendix B: Law Bundle File List

> 아래 파일들은 이미지 빌드 시 포함되어야 한다.

```
laws/
├── kr/
│   ├── personal-information-protection-act.md   # 개인정보보호법 (최종 개정: 2023-09)
│   ├── credit-information-use-act.md            # 신용정보의 이용 및 보호에 관한 법률
│   └── network-utilization-act.md               # 정보통신망 이용촉진 및 정보보호 등에 관한 법률
├── eu/
│   ├── gdpr.md                                  # General Data Protection Regulation
│   └── ai-act.md                                # EU AI Act (2024)
├── us/
│   ├── ccpa.md                                  # California Consumer Privacy Act
│   └── hipaa.md                                 # Health Insurance Portability and Accountability Act
└── jp/
    └── appi.md                                  # Act on the Protection of Personal Information
```

각 파일 우선 생성 순서 (구현 단계별):

1. `kr/personal-information-protection-act.md` — MVP 필수
2. `eu/gdpr.md` — MVP 필수
3. 나머지 — v1.1 이후
