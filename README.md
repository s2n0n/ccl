# CCL — Compliance Checker Legalized

오프라인 우선 데이터 컴플라이언스 검증 엔진. 외부 API 없이 데이터셋이 GDPR, HIPAA, 개인정보보호법 등 각국 개인정보 보호법을 준수하는지 검사합니다.

## 특징

- **오프라인 우선**: 법령 번들이 Docker 이미지에 내장 — 네트워크 불필요
- **Fail-Closed**: 준수 여부를 판단할 수 없을 경우 기본값 FAIL (안전 우선)
- **읽기 전용**: 데이터를 수정하지 않고 분석만 수행
- **다중 관할권**: GDPR, HIPAA, 개인정보보호법(한국), APPI(일본), CCPA 지원
- **감사 로그**: 변경 불가능한 JSONL 감사 추적

## 지원 법령

| 법령 ID | 법령 | 관할권 |
|---------|------|--------|
| `kr-pipa` | 개인정보 보호법 | 한국 |
| `gdpr` | General Data Protection Regulation | EU |
| `ccpa` | California Consumer Privacy Act | 미국(캘리포니아) |
| `hipaa` | Health Insurance Portability and Accountability Act | 미국 |
| `jp-appi` | Act on Protection of Personal Information | 일본 |

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

## CLI 옵션

```
ccl validate [OPTIONS]
```

| 옵션 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--input PATH` | Y | — | 입력 데이터 파일 (CSV 또는 Parquet) |
| `--law TEXT` | Y | — | 적용 법령 ID (반복 사용 가능) |
| `--metadata PATH` | N | — | JSON 메타데이터 파일 (`retention_days`, `purpose_specified`, `consent_records_present`) |
| `--output PATH` | N | stdout | 결과 보고서 저장 경로 |
| `--audit-log PATH` | N | stderr | 감사 로그 저장 경로 (JSONL) |
| `--fail-on-violation` | N | False | 위반 발견 시 exit code 1 반환 |
| `--sample-rows INT` | N | 500 | PII 스캔에 사용할 샘플 행 수 |

## 출력 예시

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
      "sample_count": 3
    }
  ],
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
   [EXTRACTOR]   ← 읽기 전용 데이터 샘플링
        ↓
   [PII SCANNER] ← 정규식 기반 PII 탐지
        ↓
  [RULE ENGINE]  ← 법령 로드, 규칙 파싱, 조건 평가
        ↓
    [REPORT]     ← 컴플라이언스 보고서 생성
        ↓
  [AUDIT LOG]    ← 변경 불가능한 JSONL 감사 로그
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
