"""LLM 보강 오케스트레이터 — 규칙 엔진 결과에 LLM 분석을 추가한다."""
from __future__ import annotations

import json
import re

from ccl.llm.adapter import LLMAdapter, LLMResponse
from ccl.llm.prompts import (
    build_enrich_prompt,
    build_quasi_id_prompt,
    build_resolve_prompt,
    build_unstructured_pii_prompt,
)
from ccl.models import (
    ColumnCategory,
    ComplianceReport,
    LLMFinding,
    LLMFindingType,
    LLMMeta,
    SampleSchema,
    Severity,
    Violation,
    ViolationStatus,
)

_VALID_MODES = ("enrich", "resolve", "full")


class LLMAugmentor:
    """ComplianceReport에 LLM 보강 결과를 추가한다.

    - enrich : FAIL 위반 항목에 자연어 설명(llm_explanation) 추가
    - resolve: UNKNOWN 위반 항목을 LLM으로 재평가 + 설명 추가
    - full   : enrich + resolve + 비정형 PII 탐지 + 준식별자 분석
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        mode: str = "enrich",
        max_samples: int = 5,
    ) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Unknown LLM mode: {mode!r}. Choose from: {_VALID_MODES}"
            )
        self._adapter = adapter
        self._mode = mode
        self._max_samples = max_samples

    # ── Public ────────────────────────────────────────────────────────────────

    def augment(
        self, report: ComplianceReport, schema: SampleSchema
    ) -> ComplianceReport:
        """report와 schema를 받아 LLM 보강된 새 ComplianceReport를 반환한다.

        - report.status / summary / to_exit_code() 는 규칙 엔진 값 그대로 유지
        - LLM 오류 발생 시 해당 항목만 스킵하고 나머지는 정상 처리
        """
        tokens_total = 0
        latency_total = 0
        errors: list[str] = []

        violations = list(report.violations)
        llm_findings: list[LLMFinding] = []

        # ── enrich: FAIL 항목에 설명 추가 ─────────────────────────────────────
        if self._mode in ("enrich", "full"):
            violations, t, l, e = self._enrich_fails(violations, schema)
            tokens_total += t; latency_total += l; errors += e

        # ── resolve: UNKNOWN 항목 재평가 ──────────────────────────────────────
        if self._mode in ("resolve", "full"):
            violations, t, l, e = self._resolve_unknowns(violations, schema)
            tokens_total += t; latency_total += l; errors += e

        # ── full: 비정형 PII + 준식별자 분석 ─────────────────────────────────
        if self._mode == "full":
            findings, t, l, e = self._scan_unstructured(schema)
            llm_findings += findings; tokens_total += t; latency_total += l; errors += e

            findings, t, l, e = self._analyze_quasi_id(schema)
            llm_findings += findings; tokens_total += t; latency_total += l; errors += e

        # LLM_PASS 판정 위반은 리포트에서 제거 (audit을 위해 llm_meta에 기록)
        llm_pass_count = sum(1 for v in violations if v.status == ViolationStatus.LLM_PASS)
        if llm_pass_count:
            errors.append(
                f"[resolve] LLM이 UNKNOWN {llm_pass_count}건을 PASS로 판정하여 리포트에서 제거"
            )
        violations = [v for v in violations if v.status != ViolationStatus.LLM_PASS]

        meta_info = self._adapter.metadata()
        source_tag = f"llm:{meta_info['provider']}/{meta_info['model']}"
        for f in llm_findings:
            f.source = source_tag

        llm_meta = LLMMeta(
            provider=meta_info["provider"],
            model=meta_info["model"],
            endpoint=meta_info.get("endpoint"),
            mode=self._mode,
            tokens_used=tokens_total,
            latency_ms=latency_total,
            errors=errors,
        )

        return report.model_copy(update={
            "violations": violations,
            "llm_findings": llm_findings,
            "llm_meta": llm_meta,
        })

    # ── Private: enrich ───────────────────────────────────────────────────────

    def _enrich_fails(
        self, violations: list[Violation], schema: SampleSchema
    ) -> tuple[list[Violation], int, int, list[str]]:
        result, tokens, latency, errors = [], 0, 0, []
        for v in violations:
            if v.status != ViolationStatus.FAIL:
                result.append(v)
                continue
            try:
                prompt = build_enrich_prompt(v, schema, self._max_samples)
                resp = self._adapter.complete(prompt)
                explanation = _parse_str_field(resp.content, "explanation")
                v = v.model_copy(update={"llm_explanation": explanation})
                tokens += resp.tokens_used
                latency += resp.latency_ms
            except Exception as exc:
                errors.append(f"[enrich] {v.rule_id}: {exc}")
            result.append(v)
        return result, tokens, latency, errors

    # ── Private: resolve ──────────────────────────────────────────────────────

    def _resolve_unknowns(
        self, violations: list[Violation], schema: SampleSchema
    ) -> tuple[list[Violation], int, int, list[str]]:
        result, tokens, latency, errors = [], 0, 0, []
        for v in violations:
            if v.status != ViolationStatus.UNKNOWN:
                result.append(v)
                continue
            try:
                prompt = build_resolve_prompt(v, schema, self._max_samples)
                resp = self._adapter.complete(prompt)
                parsed = _parse_json(resp.content)
                llm_status = parsed.get("status", "UNKNOWN").upper()
                rationale = parsed.get("rationale", "")
                new_status = {
                    "FAIL": ViolationStatus.LLM_FAIL,
                    "PASS": ViolationStatus.LLM_PASS,
                }.get(llm_status, ViolationStatus.UNKNOWN)
                v = v.model_copy(update={
                    "status": new_status,
                    "llm_explanation": rationale,
                })
                tokens += resp.tokens_used
                latency += resp.latency_ms
            except Exception as exc:
                errors.append(f"[resolve] {v.rule_id}: {exc}")
            result.append(v)
        return result, tokens, latency, errors

    # ── Private: full — 비정형 PII ────────────────────────────────────────────

    def _scan_unstructured(
        self, schema: SampleSchema
    ) -> tuple[list[LLMFinding], int, int, list[str]]:
        """GENERAL 카테고리 컬럼의 자유형식 텍스트에서 PII를 탐지한다."""
        findings, tokens, latency, errors = [], 0, 0, []
        general_cols = [
            c for c in schema.columns
            if c.category == ColumnCategory.GENERAL and c.sample_values
        ]
        for col in general_cols:
            try:
                prompt = build_unstructured_pii_prompt(col, self._max_samples)
                resp = self._adapter.complete(prompt)
                parsed = _parse_json(resp.content)
                raw_findings = parsed.get("findings", [])
                for item in raw_findings:
                    findings.append(LLMFinding(
                        finding_type=LLMFindingType.UNSTRUCTURED_PII,
                        column=col.name,
                        rationale=f"[{item.get('type', 'unknown')}] {item.get('evidence', '')}",
                        severity=Severity.MEDIUM,
                        source="",  # augment() 에서 채워짐
                    ))
                tokens += resp.tokens_used
                latency += resp.latency_ms
            except Exception as exc:
                errors.append(f"[unstructured_pii] {col.name}: {exc}")
        return findings, tokens, latency, errors

    # ── Private: full — 준식별자 분석 ────────────────────────────────────────

    def _analyze_quasi_id(
        self, schema: SampleSchema
    ) -> tuple[list[LLMFinding], int, int, list[str]]:
        """전체 컬럼 조합에서 준식별자 위험을 분석한다."""
        if len(schema.columns) < 2:
            return [], 0, 0, []
        findings, tokens, latency, errors = [], 0, 0, []
        try:
            prompt = build_quasi_id_prompt(schema, self._max_samples)
            resp = self._adapter.complete(prompt)
            parsed = _parse_json(resp.content)
            risk = parsed.get("risk", "NONE").upper()
            quasi_sets = parsed.get("quasi_id_sets", [])

            sev_map = {"HIGH": Severity.HIGH, "MEDIUM": Severity.MEDIUM, "LOW": Severity.LOW}
            sev = sev_map.get(risk, Severity.LOW)

            for col_set in quasi_sets:
                if not isinstance(col_set, list) or not col_set:
                    continue
                findings.append(LLMFinding(
                    finding_type=LLMFindingType.QUASI_IDENTIFIER,
                    columns=col_set,
                    rationale=(
                        f"컬럼 {col_set} 조합은 개인을 재식별할 수 있는 "
                        f"준식별자 집합입니다. 위험도: {risk}"
                    ),
                    severity=sev,
                    source="",  # augment() 에서 채워짐
                ))
            tokens += resp.tokens_used
            latency += resp.latency_ms
        except Exception as exc:
            errors.append(f"[quasi_id]: {exc}")
        return findings, tokens, latency, errors


# ── JSON 파싱 헬퍼 ────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    """LLM 응답에서 JSON 블록을 파싱한다. 파싱 실패 시 빈 dict 반환."""
    text = text.strip()
    # 코드 블록 마크다운 제거 (```json ... ```)
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 중괄호 범위만 추출 재시도
        brace = re.search(r"\{[\s\S]*\}", text)
        if brace:
            return json.loads(brace.group())
        raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {text[:200]!r}")


def _parse_str_field(text: str, field: str) -> str:
    """JSON에서 단일 문자열 필드를 추출한다."""
    parsed = _parse_json(text)
    value = parsed.get(field, "")
    return str(value) if value else ""
