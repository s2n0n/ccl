"""Tests for ReportBuilder status precedence and output format."""
from __future__ import annotations

import pytest

from ccl.models import (
    ColumnCategory,
    ColumnSchema,
    ReportStatus,
    SampleSchema,
    Severity,
    Violation,
    ViolationStatus,
)
from ccl.report.builder import ReportBuilder


def _schema() -> SampleSchema:
    return SampleSchema(dataset_id="test_ds", columns=[], row_count=10)


def _v(status: ViolationStatus) -> Violation:
    return Violation(
        rule_id="R001",
        article="Art 1",
        description="desc",
        severity=Severity.HIGH,
        status=status,
    )


class TestStatusPrecedence:
    def test_all_pass(self):
        report = ReportBuilder().build(_schema(), [], ["kr-pipa"], {"kr-pipa": "2023-09-15"})
        assert report.status == ReportStatus.PASS

    def test_fail_dominates(self):
        violations = [_v(ViolationStatus.FAIL), _v(ViolationStatus.UNKNOWN)]
        report = ReportBuilder().build(_schema(), violations, ["kr-pipa"], {})
        assert report.status == ReportStatus.FAIL

    def test_unknown_without_fail(self):
        violations = [_v(ViolationStatus.UNKNOWN)]
        report = ReportBuilder().build(_schema(), violations, ["kr-pipa"], {})
        assert report.status == ReportStatus.UNKNOWN

    def test_single_fail(self):
        violations = [_v(ViolationStatus.FAIL)]
        report = ReportBuilder().build(_schema(), violations, ["gdpr"], {})
        assert report.status == ReportStatus.FAIL


class TestReportSummary:
    def test_summary_counts(self):
        violations = [
            _v(ViolationStatus.FAIL),
            _v(ViolationStatus.FAIL),
            _v(ViolationStatus.UNKNOWN),
        ]
        report = ReportBuilder().build(_schema(), violations, ["kr-pipa"], {})
        assert report.summary.failed == 2
        assert report.summary.unknown == 1
        assert report.summary.passed == 0
        assert report.summary.total_checks == 3


class TestReportOutput:
    def test_violations_filtered(self):
        """PASS violations should not appear in the violations list."""
        violations = [_v(ViolationStatus.FAIL), _v(ViolationStatus.UNKNOWN)]
        report = ReportBuilder().build(_schema(), violations, ["gdpr"], {})
        assert len(report.violations) == 2

    def test_exit_code_pass(self):
        report = ReportBuilder().build(_schema(), [], ["kr-pipa"], {})
        assert report.to_exit_code() == 0

    def test_exit_code_fail(self):
        violations = [_v(ViolationStatus.FAIL)]
        report = ReportBuilder().build(_schema(), violations, ["gdpr"], {})
        assert report.to_exit_code() == 1

    def test_exit_code_unknown(self):
        violations = [_v(ViolationStatus.UNKNOWN)]
        report = ReportBuilder().build(_schema(), violations, ["kr-pipa"], {})
        assert report.to_exit_code() == 2

    def test_json_serialization(self):
        report = ReportBuilder().build(_schema(), [], ["kr-pipa"], {"kr-pipa": "2023-09-15"})
        json_str = report.model_dump_json()
        assert "dataset_id" in json_str
        assert "status" in json_str
        assert "PASS" in json_str
