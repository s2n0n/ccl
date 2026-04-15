from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ColumnCategory(str, Enum):
    SENSITIVE = "sensitive"          # 건강정보, 생체정보, 정치적 견해
    UNIQUE_ID = "unique_id"          # 주민등록번호, 여권번호
    DIRECT_IDENTIFIER = "direct_identifier"  # 이메일, 전화번호
    GENERAL = "general"              # PII 아님


class ColumnSchema(BaseModel):
    name: str
    sample_values: list[str] = Field(default_factory=list)
    pii_detected: bool = False
    category: ColumnCategory = ColumnCategory.GENERAL
    masked: bool = False
    encrypted: bool = False


class SampleSchema(BaseModel):
    dataset_id: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    row_count: int = 0
    retention_days: int | None = None      # None = unknown
    purpose_specified: bool = False
    consent_records_present: bool = False
    source_path: str = ""


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RuleAction(str, Enum):
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"


class Rule(BaseModel):
    rule_id: str
    law_id: str
    severity: Severity = Severity.HIGH
    article: str = ""
    description: str = ""
    condition: str
    action: RuleAction = RuleAction.FAIL


class ViolationStatus(str, Enum):
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"
    LLM_FAIL = "LLM_FAIL"   # LLM이 UNKNOWN을 FAIL로 판정
    LLM_PASS = "LLM_PASS"   # LLM이 UNKNOWN을 PASS로 판정


class Violation(BaseModel):
    rule_id: str
    article: str
    description: str
    severity: Severity
    status: ViolationStatus
    column: str | None = None
    sample_count: int | None = None
    llm_explanation: str | None = None   # enrich/resolve/full 모드 시 추가


class ReportStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ReportSummary(BaseModel):
    total_checks: int
    passed: int
    failed: int
    unknown: int


# ── LLM 연동 모델 ─────────────────────────────────────────────────────────────

class LLMFindingType(str, Enum):
    UNSTRUCTURED_PII = "UNSTRUCTURED_PII"   # 비정형 텍스트 내 PII
    QUASI_IDENTIFIER = "QUASI_IDENTIFIER"   # 준식별자 조합


class LLMFinding(BaseModel):
    finding_type: LLMFindingType
    column: str | None = None
    columns: list[str] = Field(default_factory=list)
    rationale: str
    severity: Severity
    source: str   # "llm:ollama/llama3.2"


class LLMMeta(BaseModel):
    provider: str
    model: str
    endpoint: str | None = None
    mode: str
    tokens_used: int = 0
    latency_ms: int = 0
    errors: list[str] = Field(default_factory=list)


# ── Report ────────────────────────────────────────────────────────────────────

class ComplianceReport(BaseModel):
    dataset_id: str
    law_bundle_version: str
    jurisdiction: list[str]
    status: ReportStatus
    violations: list[Violation] = Field(default_factory=list)
    summary: ReportSummary
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    engine_version: str = "2.0.0"
    llm_findings: list[LLMFinding] = Field(default_factory=list)
    llm_meta: LLMMeta | None = None

    def to_exit_code(self) -> int:
        # 종료 코드는 규칙 엔진 결과(status) 기준. LLM 결과는 미영향.
        if self.status == ReportStatus.PASS:
            return 0
        if self.status == ReportStatus.FAIL:
            return 1
        if self.status == ReportStatus.UNKNOWN:
            return 2
        return 3
