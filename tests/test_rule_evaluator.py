"""Tests for RuleEvaluator."""
from __future__ import annotations

import pytest

from ccl.models import (
    ColumnCategory,
    ColumnSchema,
    Rule,
    RuleAction,
    SampleSchema,
    Severity,
    ViolationStatus,
)
from ccl.policy.rule_evaluator import RuleEvaluator


def _rule(condition: str, action: RuleAction = RuleAction.FAIL) -> Rule:
    return Rule(
        rule_id="TEST-001",
        law_id="TEST",
        severity=Severity.HIGH,
        article="Test Article",
        description="Test description",
        condition=condition,
        action=action,
    )


def _schema(**kwargs) -> SampleSchema:
    defaults = dict(dataset_id="test", columns=[], row_count=0)
    defaults.update(kwargs)
    return SampleSchema(**defaults)


def _col(name: str, category: ColumnCategory, masked: bool = False, encrypted: bool = False) -> ColumnSchema:
    return ColumnSchema(
        name=name,
        pii_detected=category != ColumnCategory.GENERAL,
        category=category,
        masked=masked,
        encrypted=encrypted,
    )


class TestPiiPresent:
    def test_pii_present_true(self):
        schema = _schema(columns=[_col("email", ColumnCategory.DIRECT_IDENTIFIER)])
        violations = RuleEvaluator().evaluate(schema, [_rule("pii_present()", RuleAction.UNKNOWN)])
        assert violations[0].status == ViolationStatus.UNKNOWN

    def test_pii_present_false(self):
        schema = _schema(columns=[_col("product_id", ColumnCategory.GENERAL)])
        violations = RuleEvaluator().evaluate(schema, [_rule("pii_present()")])
        assert len(violations) == 0


class TestAnyColumn:
    def test_sensitive_not_masked_fail(self):
        schema = _schema(columns=[_col("health", ColumnCategory.SENSITIVE, masked=False)])
        violations = RuleEvaluator().evaluate(schema, [_rule("any_column(category='sensitive', masked=False)")])
        assert violations[0].status == ViolationStatus.FAIL
        assert violations[0].column == "health"

    def test_sensitive_masked_pass(self):
        schema = _schema(columns=[_col("health", ColumnCategory.SENSITIVE, masked=True)])
        violations = RuleEvaluator().evaluate(schema, [_rule("any_column(category='sensitive', masked=False)")])
        assert len(violations) == 0

    def test_unique_id_not_encrypted_fail(self):
        schema = _schema(columns=[_col("jumin", ColumnCategory.UNIQUE_ID, encrypted=False)])
        violations = RuleEvaluator().evaluate(schema, [_rule("any_column(category='unique_id', encrypted=False)")])
        assert violations[0].status == ViolationStatus.FAIL

    def test_unique_id_encrypted_pass(self):
        schema = _schema(columns=[_col("jumin", ColumnCategory.UNIQUE_ID, encrypted=True)])
        violations = RuleEvaluator().evaluate(schema, [_rule("any_column(category='unique_id', encrypted=False)")])
        assert len(violations) == 0


class TestRetentionExceeded:
    def test_exceeds_threshold_fail(self):
        schema = _schema(retention_days=2000)
        violations = RuleEvaluator().evaluate(schema, [_rule("retention_exceeded(days=1825)")])
        assert violations[0].status == ViolationStatus.FAIL

    def test_within_threshold_pass(self):
        schema = _schema(retention_days=365)
        violations = RuleEvaluator().evaluate(schema, [_rule("retention_exceeded(days=1825)")])
        assert len(violations) == 0

    def test_retention_unknown_when_none(self):
        schema = _schema(retention_days=None)
        violations = RuleEvaluator().evaluate(schema, [_rule("retention_exceeded(days=1825)")])
        assert violations[0].status == ViolationStatus.UNKNOWN


class TestConsentMissing:
    def test_consent_missing_fail(self):
        schema = _schema(consent_records_present=False)
        violations = RuleEvaluator().evaluate(schema, [_rule("consent_missing()")])
        assert violations[0].status == ViolationStatus.FAIL

    def test_consent_present_pass(self):
        schema = _schema(consent_records_present=True)
        violations = RuleEvaluator().evaluate(schema, [_rule("consent_missing()")])
        assert len(violations) == 0


class TestPurposeUnspecified:
    def test_purpose_unspecified_unknown(self):
        schema = _schema(purpose_specified=False)
        violations = RuleEvaluator().evaluate(schema, [_rule("purpose_unspecified()", RuleAction.UNKNOWN)])
        assert violations[0].status == ViolationStatus.UNKNOWN

    def test_purpose_specified_pass(self):
        schema = _schema(purpose_specified=True)
        violations = RuleEvaluator().evaluate(schema, [_rule("purpose_unspecified()")])
        assert len(violations) == 0


class TestParseError:
    def test_unknown_condition_becomes_unknown(self):
        schema = _schema()
        violations = RuleEvaluator().evaluate(schema, [_rule("unknown_predicate()")])
        assert violations[0].status == ViolationStatus.UNKNOWN
        assert "PARSE ERROR" in violations[0].description
