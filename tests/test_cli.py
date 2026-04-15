"""End-to-end CLI tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ccl.cli import main

NO_AUDIT = ["--audit-log", "/dev/null"]


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def metadata_with_consent(fixtures_dir) -> str:
    return str(fixtures_dir / "metadata_with_consent.json")


@pytest.fixture
def metadata_no_consent(fixtures_dir) -> str:
    return str(fixtures_dir / "metadata_no_consent.json")


class TestValidateCleanData:
    def test_clean_csv_with_consent_passes(self, runner, clean_csv, metadata_with_consent):
        result = runner.invoke(main, [
            "validate",
            "--input", clean_csv,
            "--law", "kr-pipa",
            "--metadata", metadata_with_consent,
            *NO_AUDIT,
        ])
        assert result.exit_code == 0, result.output
        report = json.loads(result.output)
        assert report["status"] == "PASS"

    def test_clean_csv_no_metadata_unknown(self, runner, clean_csv):
        """Without metadata, retention/consent checks return UNKNOWN."""
        result = runner.invoke(main, [
            "validate",
            "--input", clean_csv,
            "--law", "kr-pipa",
            *NO_AUDIT,
        ])
        # UNKNOWN = exit code 2, or PASS if no PII triggers any rules
        assert result.exit_code in (0, 2)


class TestValidateViolations:
    def test_violations_csv_fails(self, runner, violations_csv, metadata_with_consent):
        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "kr-pipa",
            "--metadata", metadata_with_consent,
            *NO_AUDIT,
        ])
        assert result.exit_code == 1, result.output
        report = json.loads(result.output)
        assert report["status"] == "FAIL"
        assert len(report["violations"]) > 0

    def test_violations_include_rule_ids(self, runner, violations_csv, metadata_with_consent):
        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "kr-pipa",
            "--metadata", metadata_with_consent,
            *NO_AUDIT,
        ])
        report = json.loads(result.output)
        rule_ids = [v["rule_id"] for v in report["violations"]]
        # jumin_number and health_status should trigger violations
        assert any("ART23" in rid or "ART24" in rid or "ART29" in rid for rid in rule_ids)

    def test_gdpr_consent_missing_fails(self, runner, violations_csv, metadata_no_consent):
        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "gdpr",
            "--metadata", metadata_no_consent,
            *NO_AUDIT,
        ])
        assert result.exit_code == 1
        report = json.loads(result.output)
        rule_ids = [v["rule_id"] for v in report["violations"]]
        assert "GDPR-ART7-001" in rule_ids


class TestMultiLaw:
    def test_multi_law_validation(self, runner, violations_csv, metadata_with_consent):
        result = runner.invoke(main, [
            "validate",
            "--input", violations_csv,
            "--law", "kr-pipa",
            "--law", "gdpr",
            "--metadata", metadata_with_consent,
            *NO_AUDIT,
        ])
        assert result.exit_code == 1
        report = json.loads(result.output)
        rule_ids = [v["rule_id"] for v in report["violations"]]
        has_kr = any(r.startswith("KR-PIPA") for r in rule_ids)
        has_eu = any(r.startswith("GDPR") for r in rule_ids)
        assert has_kr
        assert has_eu


class TestOutputFile:
    def test_output_to_file(self, runner, clean_csv, metadata_with_consent, tmp_path):
        out_file = tmp_path / "report.json"
        result = runner.invoke(main, [
            "validate",
            "--input", clean_csv,
            "--law", "kr-pipa",
            "--metadata", metadata_with_consent,
            "--output", str(out_file),
            *NO_AUDIT,
        ])
        assert out_file.exists()
        report = json.loads(out_file.read_text())
        assert "status" in report


class TestExitCodes:
    def test_error_on_bad_law(self, runner, clean_csv):
        result = runner.invoke(main, [
            "validate",
            "--input", clean_csv,
            "--law", "nonexistent-law-xyz",
            *NO_AUDIT,
        ])
        assert result.exit_code == 3

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "2.0.0" in result.output
