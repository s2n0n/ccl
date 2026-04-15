"""LLM 보강 레이어 테스트 — MockAdapter 사용 (실제 API 호출 없음)."""
from __future__ import annotations

import json
from collections import deque

import pytest
from click.testing import CliRunner

from ccl.cli import main
from ccl.llm.adapter import LLMAdapter, LLMResponse, create_adapter
from ccl.llm.augmentor import LLMAugmentor, _parse_json, _parse_str_field
from ccl.llm.prompts import (
    build_enrich_prompt,
    build_quasi_id_prompt,
    build_resolve_prompt,
    build_unstructured_pii_prompt,
)
from ccl.models import (
    ColumnCategory,
    ColumnSchema,
    ComplianceReport,
    LLMFindingType,
    ReportStatus,
    ReportSummary,
    SampleSchema,
    Severity,
    Violation,
    ViolationStatus,
)

NO_AUDIT = ["--audit-log", "/dev/null"]


@pytest.fixture
def metadata_with_consent(fixtures_dir) -> str:
    return str(fixtures_dir / "metadata_with_consent.json")


@pytest.fixture
def violations_csv(fixtures_dir) -> str:
    return str(fixtures_dir / "sample_violations.csv")


# ── Mock ──────────────────────────────────────────────────────────────────────


class MockAdapter(LLMAdapter):
    """사전 정의된 응답 큐를 순서대로 반환하는 테스트용 어댑터."""

    def __init__(self, responses: list[str]) -> None:
        self._queue: deque[str] = deque(responses)
        self.calls: list[str] = []

    def complete(self, prompt: str) -> LLMResponse:
        self.calls.append(prompt)
        if not self._queue:
            raise RuntimeError("MockAdapter: 응답 큐가 비었습니다.")
        return LLMResponse(content=self._queue.popleft(), tokens_used=10, latency_ms=5)

    def health_check(self) -> bool:
        return True

    def metadata(self) -> dict:
        return {"provider": "mock", "model": "test-model", "endpoint": None}


# ── 픽스처 ────────────────────────────────────────────────────────────────────


def _make_schema(**kwargs) -> SampleSchema:
    defaults = dict(
        dataset_id="test_ds",
        columns=[
            ColumnSchema(
                name="email",
                category=ColumnCategory.DIRECT_IDENTIFIER,
                pii_detected=True,
                sample_values=["alice@example.com", "bob@test.org"],
            ),
            ColumnSchema(
                name="memo",
                category=ColumnCategory.GENERAL,
                sample_values=["홍길동, 010-1234-5678", "일반 메모"],
            ),
        ],
        row_count=100,
    )
    defaults.update(kwargs)
    return SampleSchema(**defaults)


def _make_violation(
    rule_id="TEST-001",
    status=ViolationStatus.FAIL,
    column: str | None = "email",
) -> Violation:
    return Violation(
        rule_id=rule_id,
        article="Test Article",
        description="Test violation description",
        severity=Severity.HIGH,
        status=status,
        column=column,
    )


def _make_report(violations: list[Violation]) -> ComplianceReport:
    failed = sum(1 for v in violations if v.status == ViolationStatus.FAIL)
    unknown = sum(1 for v in violations if v.status == ViolationStatus.UNKNOWN)
    status = (
        ReportStatus.FAIL if failed else
        ReportStatus.UNKNOWN if unknown else
        ReportStatus.PASS
    )
    return ComplianceReport(
        dataset_id="test_ds",
        law_bundle_version="test=1.0",
        jurisdiction=["TEST"],
        status=status,
        violations=violations,
        summary=ReportSummary(
            total_checks=len(violations),
            passed=0,
            failed=failed,
            unknown=unknown,
        ),
    )


# ── _parse_json / _parse_str_field ────────────────────────────────────────────


class TestParseHelpers:
    def test_parse_clean_json(self):
        assert _parse_json('{"key": "value"}') == {"key": "value"}

    def test_parse_json_with_markdown_fence(self):
        text = '```json\n{"status": "FAIL"}\n```'
        assert _parse_json(text) == {"status": "FAIL"}

    def test_parse_json_extracts_braces(self):
        text = 'Here is the response: {"explanation": "설명"} done.'
        assert _parse_json(text) == {"explanation": "설명"}

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_json("not json at all")

    def test_parse_str_field(self):
        assert _parse_str_field('{"explanation": "위반입니다"}', "explanation") == "위반입니다"

    def test_parse_str_field_missing_key(self):
        assert _parse_str_field('{"other": "val"}', "explanation") == ""


# ── 프롬프트 빌더 ─────────────────────────────────────────────────────────────


class TestPromptBuilders:
    def setup_method(self):
        self.schema = _make_schema()
        self.violation = _make_violation()

    def test_enrich_prompt_contains_article(self):
        prompt = build_enrich_prompt(self.violation, self.schema, max_samples=5)
        assert "Test Article" in prompt
        assert "explanation" in prompt

    def test_enrich_prompt_contains_sample_values(self):
        prompt = build_enrich_prompt(self.violation, self.schema, max_samples=5)
        assert "alice@example.com" in prompt

    def test_enrich_prompt_no_column_match(self):
        v = _make_violation(column="nonexistent")
        prompt = build_enrich_prompt(v, self.schema, max_samples=5)
        assert "explanation" in prompt  # 컬럼 없어도 프롬프트 생성됨

    def test_resolve_prompt_contains_schema(self):
        v = _make_violation(status=ViolationStatus.UNKNOWN)
        prompt = build_resolve_prompt(v, self.schema, max_samples=5)
        assert "email" in prompt
        assert "FAIL" in prompt
        assert "PASS" in prompt
        assert "UNKNOWN" in prompt

    def test_unstructured_pii_prompt(self):
        col = self.schema.columns[1]  # memo
        prompt = build_unstructured_pii_prompt(col, max_samples=3)
        assert "memo" in prompt
        assert "findings" in prompt

    def test_quasi_id_prompt(self):
        prompt = build_quasi_id_prompt(self.schema, max_samples=3)
        assert "quasi_id_sets" in prompt
        assert "email" in prompt

    def test_max_samples_limits_values(self):
        schema = _make_schema()
        schema.columns[0].sample_values = [f"val{i}@x.com" for i in range(20)]
        prompt = build_enrich_prompt(self.violation, schema, max_samples=2)
        assert "val0@x.com" in prompt
        assert "val2@x.com" not in prompt

    def test_value_truncated_at_64_chars(self):
        schema = _make_schema()
        long_val = "a" * 100
        schema.columns[0].sample_values = [long_val]
        prompt = build_enrich_prompt(self.violation, schema, max_samples=5)
        assert "a" * 64 in prompt
        assert "a" * 65 not in prompt


# ── LLMAugmentor — enrich 모드 ────────────────────────────────────────────────


class TestAugmentorEnrich:
    def test_enrich_adds_llm_explanation(self):
        adapter = MockAdapter(['{"explanation": "이메일 주소가 마스킹되지 않았습니다."}'])
        aug = LLMAugmentor(adapter, mode="enrich", max_samples=5)
        report = _make_report([_make_violation(status=ViolationStatus.FAIL)])
        result = aug.augment(report, _make_schema())

        assert result.violations[0].llm_explanation == "이메일 주소가 마스킹되지 않았습니다."

    def test_enrich_skips_unknown_violations(self):
        adapter = MockAdapter([])
        aug = LLMAugmentor(adapter, mode="enrich")
        v = _make_violation(status=ViolationStatus.UNKNOWN)
        report = _make_report([v])
        result = aug.augment(report, _make_schema())

        assert len(adapter.calls) == 0  # UNKNOWN은 enrich 대상 아님
        assert result.violations[0].llm_explanation is None

    def test_enrich_error_gracefully_skips(self):
        adapter = MockAdapter([])  # 빈 큐 → RuntimeError
        aug = LLMAugmentor(adapter, mode="enrich")
        report = _make_report([_make_violation(status=ViolationStatus.FAIL)])
        result = aug.augment(report, _make_schema())

        assert result.llm_meta is not None
        assert len(result.llm_meta.errors) == 1
        assert result.violations[0].llm_explanation is None  # 오류 시 None 유지

    def test_enrich_preserves_report_status(self):
        adapter = MockAdapter(['{"explanation": "설명"}'])
        aug = LLMAugmentor(adapter, mode="enrich")
        report = _make_report([_make_violation(status=ViolationStatus.FAIL)])
        result = aug.augment(report, _make_schema())

        assert result.status == ReportStatus.FAIL  # 규칙 엔진 status 불변

    def test_llm_meta_populated(self):
        adapter = MockAdapter(['{"explanation": "설명"}'])
        aug = LLMAugmentor(adapter, mode="enrich")
        report = _make_report([_make_violation()])
        result = aug.augment(report, _make_schema())

        meta = result.llm_meta
        assert meta.provider == "mock"
        assert meta.model == "test-model"
        assert meta.mode == "enrich"
        assert meta.tokens_used == 10
        assert meta.latency_ms == 5


# ── LLMAugmentor — resolve 모드 ───────────────────────────────────────────────


class TestAugmentorResolve:
    def test_resolve_unknown_to_llm_fail(self):
        resp = '{"status": "FAIL", "rationale": "데이터에 위험한 정보가 있습니다."}'
        adapter = MockAdapter([resp])
        aug = LLMAugmentor(adapter, mode="resolve")
        report = _make_report([_make_violation(status=ViolationStatus.UNKNOWN, column=None)])
        result = aug.augment(report, _make_schema())

        v = result.violations[0]
        assert v.status == ViolationStatus.LLM_FAIL
        assert "위험한 정보" in v.llm_explanation

    def test_resolve_unknown_to_llm_pass_removes_violation(self):
        resp = '{"status": "PASS", "rationale": "위반 없음"}'
        adapter = MockAdapter([resp])
        aug = LLMAugmentor(adapter, mode="resolve")
        report = _make_report([_make_violation(status=ViolationStatus.UNKNOWN, column=None)])
        result = aug.augment(report, _make_schema())

        # LLM_PASS는 리포트에서 제거됨
        assert not any(v.status == ViolationStatus.LLM_PASS for v in result.violations)
        assert result.llm_meta.errors  # 제거 사실은 errors에 기록

    def test_resolve_unknown_stays_unknown_on_llm_unknown(self):
        resp = '{"status": "UNKNOWN", "rationale": "판단 불가"}'
        adapter = MockAdapter([resp])
        aug = LLMAugmentor(adapter, mode="resolve")
        report = _make_report([_make_violation(status=ViolationStatus.UNKNOWN, column=None)])
        result = aug.augment(report, _make_schema())

        assert result.violations[0].status == ViolationStatus.UNKNOWN

    def test_resolve_skips_fail_violations(self):
        adapter = MockAdapter([])
        aug = LLMAugmentor(adapter, mode="resolve")
        report = _make_report([_make_violation(status=ViolationStatus.FAIL)])
        result = aug.augment(report, _make_schema())

        assert len(adapter.calls) == 0  # FAIL은 resolve 대상 아님

    def test_report_status_unchanged_after_resolve(self):
        resp = '{"status": "FAIL", "rationale": "위반"}'
        adapter = MockAdapter([resp])
        aug = LLMAugmentor(adapter, mode="resolve")
        # 규칙 엔진은 UNKNOWN이었음
        report = _make_report([_make_violation(status=ViolationStatus.UNKNOWN, column=None)])
        result = aug.augment(report, _make_schema())

        assert result.status == ReportStatus.UNKNOWN  # 규칙 엔진 status 불변


# ── LLMAugmentor — full 모드 ──────────────────────────────────────────────────


class TestAugmentorFull:
    def test_full_mode_produces_llm_findings(self):
        responses = [
            # enrich (FAIL violation 없으면 호출 없음)
            # unstructured PII for 'memo' column
            '{"findings": [{"type": "contact", "evidence": "010-1234-5678"}]}',
            # quasi-id
            '{"quasi_id_sets": [["email", "memo"]], "risk": "MEDIUM"}',
        ]
        adapter = MockAdapter(responses)
        aug = LLMAugmentor(adapter, mode="full")
        report = _make_report([])  # PASS report (no violations)
        result = aug.augment(report, _make_schema())

        assert len(result.llm_findings) >= 1
        types = [f.finding_type for f in result.llm_findings]
        assert LLMFindingType.UNSTRUCTURED_PII in types

    def test_full_mode_quasi_id_finding(self):
        responses = [
            '{"findings": []}',  # unstructured: no findings
            '{"quasi_id_sets": [["email", "memo"]], "risk": "HIGH"}',
        ]
        adapter = MockAdapter(responses)
        aug = LLMAugmentor(adapter, mode="full")
        report = _make_report([])
        result = aug.augment(report, _make_schema())

        quasi = [f for f in result.llm_findings if f.finding_type == LLMFindingType.QUASI_IDENTIFIER]
        assert len(quasi) == 1
        assert quasi[0].severity == Severity.HIGH
        assert "email" in quasi[0].columns

    def test_full_mode_source_tag_set(self):
        responses = [
            '{"findings": [{"type": "name", "evidence": "홍길동"}]}',
            '{"quasi_id_sets": [], "risk": "NONE"}',
        ]
        adapter = MockAdapter(responses)
        aug = LLMAugmentor(adapter, mode="full")
        report = _make_report([])
        result = aug.augment(report, _make_schema())

        for finding in result.llm_findings:
            assert finding.source.startswith("llm:mock/")

    def test_full_mode_skips_quasi_id_with_single_column(self):
        schema = SampleSchema(
            dataset_id="ds",
            columns=[ColumnSchema(name="email", category=ColumnCategory.GENERAL)],
        )
        responses = ['{"findings": []}']
        adapter = MockAdapter(responses)
        aug = LLMAugmentor(adapter, mode="full")
        report = _make_report([])
        result = aug.augment(report, schema)

        # 컬럼 1개 → quasi-id 분석 스킵
        quasi = [f for f in result.llm_findings if f.finding_type == LLMFindingType.QUASI_IDENTIFIER]
        assert len(quasi) == 0


# ── 어댑터 팩토리 ─────────────────────────────────────────────────────────────


class TestAdapterFactory:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_adapter("fakeai", "model-x")

    def test_ollama_adapter_created(self):
        from ccl.llm.ollama import OllamaAdapter
        adapter = create_adapter("ollama", "llama3.2", endpoint="http://localhost:11434")
        assert isinstance(adapter, OllamaAdapter)
        assert adapter.model == "llama3.2"

    def test_claude_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            create_adapter("claude", "claude-sonnet-4-6")

    def test_openai_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            create_adapter("openai", "gpt-4o")


# ── CLI 통합 ─────────────────────────────────────────────────────────────────


class TestCLILLMOptions:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_validate_without_llm_provider_has_no_llm_meta(
        self, runner, violations_csv, metadata_with_consent
    ):
        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "kr-pipa",
            "--metadata", metadata_with_consent,
            *NO_AUDIT,
        ])
        report = json.loads(result.output)
        assert report.get("llm_meta") is None
        assert report.get("llm_findings") == []

    def test_validate_with_invalid_llm_provider_rejected(self, runner, violations_csv):
        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "kr-pipa",
            "--llm-provider", "unknownai",
            *NO_AUDIT,
        ])
        assert result.exit_code != 0

    def test_validate_llm_failure_falls_back_to_rule_engine(
        self, runner, violations_csv, metadata_with_consent, monkeypatch
    ):
        """LLM complete() 오류 시 규칙 엔진 결과가 유지되고 에러가 llm_meta에 기록된다."""
        class ErrorAdapter(LLMAdapter):
            def complete(self, prompt: str) -> LLMResponse:
                raise RuntimeError("모의 API 연결 실패")

            def health_check(self) -> bool:
                return True

            def metadata(self) -> dict:
                return {"provider": "mock", "model": "error-model", "endpoint": None}

        def mock_create(*args, **kwargs):
            return ErrorAdapter()

        monkeypatch.setattr("ccl.llm.adapter.create_adapter", mock_create)

        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "kr-pipa",
            "--metadata", metadata_with_consent,
            "--llm-provider", "ollama",
            "--llm-model", "llama3.2",
            *NO_AUDIT,
        ])
        assert result.exit_code in (0, 1, 2)
        report = json.loads(result.output)
        assert "status" in report
        assert report.get("llm_meta") is not None   # llm_meta 기록됨
        assert report["llm_meta"]["errors"]          # 오류 내역 기록됨

    def test_llm_mode_choices_accepted(self, runner, violations_csv):
        for mode in ("enrich", "resolve", "full"):
            result = runner.invoke(main, [
                "validate", "--help",
            ])
            assert mode in result.output

    def test_validate_help_shows_llm_options(self, runner):
        result = runner.invoke(main, ["validate", "--help"])
        assert "--llm-provider" in result.output
        assert "--llm-model" in result.output
        assert "--llm-endpoint" in result.output
        assert "--llm-mode" in result.output
        assert "--llm-max-samples" in result.output
        assert "--llm-timeout" in result.output


# ── AugmentorMode 유효성 검증 ─────────────────────────────────────────────────


class TestAugmentorValidation:
    def test_invalid_mode_raises(self):
        adapter = MockAdapter([])
        with pytest.raises(ValueError, match="Unknown LLM mode"):
            LLMAugmentor(adapter, mode="bad_mode")

    def test_valid_modes_accepted(self):
        adapter = MockAdapter([])
        for mode in ("enrich", "resolve", "full"):
            aug = LLMAugmentor(adapter, mode=mode)
            assert aug._mode == mode
