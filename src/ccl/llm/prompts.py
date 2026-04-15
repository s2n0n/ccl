"""LLM 프롬프트 빌더 — 모드별 구조화된 프롬프트 생성."""
from __future__ import annotations

from ccl.models import ColumnSchema, SampleSchema, Violation

_MAX_VALUE_LEN = 64

_SYSTEM = (
    "You are a data compliance analyst. "
    "Respond ONLY in valid JSON matching the requested format. "
    "Do not include any text outside the JSON block."
)


def _trim_samples(values: list[str], n: int) -> list[str]:
    return [str(v)[:_MAX_VALUE_LEN] for v in values[:n]]


def _format_schema(schema: SampleSchema, max_samples: int, *, include_protection: bool = False) -> str:
    """스키마의 모든 컬럼을 텍스트로 포맷한다.

    include_protection=True 이면 masked/encrypted 필드 포함.
    """
    col_lines = []
    for col in schema.columns:
        samples = _trim_samples(col.sample_values, max_samples)
        if include_protection:
            col_lines.append(
                f"  - {col.name}: category={col.category.value}, "
                f"masked={col.masked}, encrypted={col.encrypted}, "
                f"samples={samples}"
            )
        else:
            col_lines.append(
                f"  - {col.name}: category={col.category.value}, samples={samples}"
            )
    return "\n".join(col_lines) or "  (no columns)"


def build_enrich_prompt(
    violation: Violation,
    schema: SampleSchema,
    max_samples: int,
) -> str:
    """FAIL 위반 항목에 자연어 설명 추가용 프롬프트."""
    col = next((c for c in schema.columns if c.name == violation.column), None)
    sample_section = ""
    if col:
        samples = _trim_samples(col.sample_values, max_samples)
        sample_section = f"\nColumn '{col.name}' sample values: {samples}"

    return (
        f"{_SYSTEM}\n\n"
        f"Law article: {violation.article}\n"
        f"Violation: {violation.description}"
        f"{sample_section}\n\n"
        "Task: Explain in Korean (max 3 sentences) why this data violates "
        "the article above, referencing sample values where relevant.\n"
        'Respond ONLY with: {"explanation": "..."}'
    )


def build_resolve_prompt(
    violation: Violation,
    schema: SampleSchema,
    max_samples: int,
) -> str:
    """UNKNOWN 위반 항목 재평가용 프롬프트."""
    schema_text = _format_schema(schema, max_samples, include_protection=True)
    return (
        f"{_SYSTEM}\n\n"
        f"Law article: {violation.article}\n"
        f"Rule: {violation.description}\n\n"
        f"Dataset columns:\n{schema_text}\n\n"
        "Task: Determine if the data LIKELY violates the law article.\n"
        'Respond ONLY with: {"status": "FAIL" | "PASS" | "UNKNOWN", "rationale": "..."}'
    )


def build_unstructured_pii_prompt(col: ColumnSchema, max_samples: int) -> str:
    """GENERAL 카테고리 컬럼의 비정형 PII 탐지용 프롬프트."""
    samples = _trim_samples(col.sample_values, max_samples)
    return (
        f"{_SYSTEM}\n\n"
        f"Column name: '{col.name}'\n"
        f"Sample values: {samples}\n\n"
        "Task: Identify any personal information (PII) in these free-form text values. "
        "Classify each finding as one of: "
        "name, address, health, financial, contact, government_id, other.\n"
        'Respond ONLY with: {"findings": [{"type": "...", "evidence": "..."}]}'
    )


def build_quasi_id_prompt(schema: SampleSchema, max_samples: int) -> str:
    """전체 컬럼 조합의 준식별자 위험도 분석용 프롬프트."""
    schema_text = _format_schema(schema, max_samples, include_protection=False)
    return (
        f"{_SYSTEM}\n\n"
        f"Dataset columns:\n{schema_text}\n\n"
        "Task: Identify sets of columns that together could re-identify individuals "
        "(quasi-identifiers). Consider combinations like age+zip+gender, "
        "birth_date+region+occupation, etc.\n"
        'Respond ONLY with: '
        '{"quasi_id_sets": [["col1", "col2"]], '
        '"risk": "HIGH" | "MEDIUM" | "LOW" | "NONE"}'
    )
