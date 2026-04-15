"""CCL CLI entry point."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from ccl import __version__


@click.group()
@click.version_option(__version__, prog_name="ccl")
def main() -> None:
    """CCL — Compliance Checker Legalized.

    Offline data compliance validation engine.
    """


@main.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, readable=True),
              help="Input data file (CSV or Parquet).")
@click.option("--law", "law_ids", required=True, multiple=True,
              help="Law ID(s) to validate against (e.g. kr-pipa, gdpr). Repeatable.")
@click.option("--metadata", "metadata_path", default=None, type=click.Path(exists=True, readable=True),
              help="Optional JSON sidecar with retention_days, purpose_specified, consent_records_present.")
@click.option("--output", "output_path", default=None, type=click.Path(writable=True),
              help="Write JSON report to file (default: stdout).")
@click.option("--audit-log", "audit_log_path", default=None, type=click.Path(writable=True),
              help="Audit JSONL output path (default: stderr).")
@click.option("--fail-on-violation", is_flag=True, default=False,
              help="Exit 1 on any FAIL (for CI/CD pipelines).")
@click.option("--sample-rows", default=500, show_default=True, type=int,
              help="Number of rows to sample for PII scanning.")
# ── LLM 옵션 ──────────────────────────────────────────────────────────────────
@click.option("--llm-provider",
              type=click.Choice(["ollama", "claude", "openai"], case_sensitive=False),
              default=None,
              help="LLM provider for augmented analysis. Omit to disable LLM features.")
@click.option("--llm-model", default=None,
              help="Model name (e.g. llama3.2, claude-sonnet-4-6, gpt-4o). "
                   "Defaults: ollama=llama3.2, claude=claude-sonnet-4-6, openai=gpt-4o-mini.")
@click.option("--llm-endpoint", default=None,
              help="Ollama server URL (default: http://localhost:11434). Ignored for cloud providers.")
@click.option("--llm-mode",
              type=click.Choice(["enrich", "resolve", "full"], case_sensitive=False),
              default="enrich", show_default=True,
              help=(
                  "LLM augmentation mode: "
                  "enrich=add Korean explanations to FAIL violations, "
                  "resolve=re-evaluate UNKNOWN violations, "
                  "full=enrich+resolve+unstructured PII+quasi-identifier analysis."
              ))
@click.option("--llm-max-samples", default=5, show_default=True, type=int,
              help="Max sample values sent to LLM per column (data minimisation).")
@click.option("--llm-timeout", default=30, show_default=True, type=int,
              help="LLM API call timeout in seconds.")
def validate(
    input_path: str,
    law_ids: tuple[str, ...],
    metadata_path: Optional[str],
    output_path: Optional[str],
    audit_log_path: Optional[str],
    fail_on_violation: bool,
    sample_rows: int,
    llm_provider: Optional[str],
    llm_model: Optional[str],
    llm_endpoint: Optional[str],
    llm_mode: str,
    llm_max_samples: int,
    llm_timeout: int,
) -> None:
    """Validate a dataset for compliance against one or more laws."""
    exit_code = _run_validate(
        input_path=input_path,
        law_ids=list(law_ids),
        metadata_path=metadata_path,
        output_path=output_path,
        audit_log_path=audit_log_path,
        fail_on_violation=fail_on_violation,
        sample_rows=sample_rows,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_endpoint=llm_endpoint,
        llm_mode=llm_mode,
        llm_max_samples=llm_max_samples,
        llm_timeout=llm_timeout,
    )
    sys.exit(exit_code)


def _run_validate(
    input_path: str,
    law_ids: list[str],
    metadata_path: Optional[str],
    output_path: Optional[str],
    audit_log_path: Optional[str],
    fail_on_violation: bool,
    sample_rows: int,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_endpoint: Optional[str] = None,
    llm_mode: str = "enrich",
    llm_max_samples: int = 5,
    llm_timeout: int = 30,
) -> int:
    try:
        from ccl.extractor.base import get_extractor
        from ccl.scanner.pii_scanner import PIIScanner
        from ccl.policy.rule_registry import RuleRegistry
        from ccl.policy.rule_evaluator import RuleEvaluator
        from ccl.report.builder import ReportBuilder
        from ccl.audit.logger import AuditLogger

        # 1. Extract
        extractor = get_extractor(input_path)
        schema = extractor.extract(input_path, sample_rows=sample_rows)

        # 2. Apply metadata sidecar if provided
        if metadata_path:
            schema = _apply_metadata(schema, metadata_path)

        # 3. PII Scan
        scanner = PIIScanner()
        schema = scanner.scan(schema)

        # 4. Load rules and evaluate
        registry = RuleRegistry()
        evaluator = RuleEvaluator()
        all_violations = []
        law_versions: dict[str, str] = {}

        for law_id in law_ids:
            rules = registry.get_rules(law_id)
            meta = registry.get_law_metadata(law_id)
            law_versions[law_id] = meta.get("version", "unknown")
            violations = evaluator.evaluate(schema, rules)
            all_violations.extend(violations)

        # 5. Build report (규칙 엔진 결과 확정 — status/summary/exit_code 기준값)
        builder = ReportBuilder()
        report = builder.build(schema, all_violations, law_ids, law_versions)

        # 6. LLM 보강 (--llm-provider 미지정 시 스킵)
        if llm_provider:
            report = _run_llm_augment(
                report=report,
                schema=schema,
                provider=llm_provider,
                model=llm_model or _default_model(llm_provider),
                endpoint=llm_endpoint,
                mode=llm_mode,
                max_samples=llm_max_samples,
                timeout=llm_timeout,
            )

        # 7. Output report
        report_json = report.model_dump_json(indent=2)
        if output_path:
            Path(output_path).write_text(report_json, encoding="utf-8")
        else:
            click.echo(report_json)

        # 8. Audit log
        AuditLogger(audit_log_path).log(report)

        # 9. Exit code (규칙 엔진 status 기준 — LLM 결과 미영향)
        return report.to_exit_code()

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        return 3


def _run_llm_augment(report, schema, provider, model, endpoint, mode, max_samples, timeout):
    """LLM 어댑터를 생성하고 보강을 실행한다. 실패 시 원본 report 반환."""
    try:
        from ccl.llm.adapter import create_adapter
        from ccl.llm.augmentor import LLMAugmentor

        if provider != "ollama":
            click.echo(
                f"[LLM] {provider.upper()} API 연결 중 (--network none 옵션 사용 불가).",
                err=True,
            )

        adapter = create_adapter(provider, model, endpoint, timeout)
        augmentor = LLMAugmentor(adapter, mode=mode, max_samples=max_samples)
        return augmentor.augment(report, schema)
    except Exception as exc:
        click.echo(f"[LLM] 보강 실패, 규칙 엔진 결과만 반환합니다: {exc}", err=True)
        return report


def _default_model(provider: str) -> str:
    return {
        "ollama": "llama3.2",
        "claude": "claude-sonnet-4-6",
        "openai": "gpt-4o-mini",
    }.get(provider.lower(), "")


def _apply_metadata(schema, metadata_path: str):
    with open(metadata_path, encoding="utf-8") as f:
        meta = json.load(f)
    updates = {}
    if "retention_days" in meta:
        updates["retention_days"] = int(meta["retention_days"])
    if "purpose_specified" in meta:
        updates["purpose_specified"] = bool(meta["purpose_specified"])
    if "consent_records_present" in meta:
        updates["consent_records_present"] = bool(meta["consent_records_present"])
    return schema.model_copy(update=updates)


if __name__ == "__main__":
    main()
