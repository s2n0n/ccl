"""Tests for LawParser."""
from __future__ import annotations

import pytest

from ccl.models import RuleAction, Severity
from ccl.policy.law_parser import LawParser
from ccl.policy.rule_registry import RuleRegistry


def test_parse_kr_pipa(tmp_path):
    registry = RuleRegistry()
    rules = registry.get_rules("kr-pipa")

    assert len(rules) >= 4
    rule_ids = [r.rule_id for r in rules]
    assert "KR-PIPA-ART23-001" in rule_ids
    assert "KR-PIPA-ART24-001" in rule_ids
    assert "KR-PIPA-ART21-001" in rule_ids


def test_parse_gdpr():
    registry = RuleRegistry()
    rules = registry.get_rules("gdpr")

    rule_ids = [r.rule_id for r in rules]
    assert "GDPR-ART9-001" in rule_ids
    assert "GDPR-ART7-001" in rule_ids


def test_rule_fields():
    registry = RuleRegistry()
    rules = registry.get_rules("kr-pipa")
    art23 = next(r for r in rules if r.rule_id == "KR-PIPA-ART23-001")

    assert art23.severity == Severity.HIGH
    assert art23.action == RuleAction.FAIL
    assert "any_column" in art23.condition
    assert "sensitive" in art23.condition


def test_unknown_law_raises():
    registry = RuleRegistry()
    with pytest.raises(ValueError, match="Unknown law_id"):
        registry.get_rules("nonexistent-law")


def test_rule_law_id_set():
    registry = RuleRegistry()
    rules = registry.get_rules("kr-pipa")
    assert all(r.law_id == "KR-PIPA" for r in rules)


def test_parse_iso27001():
    registry = RuleRegistry()
    rules = registry.get_rules("iso27001")

    assert len(rules) >= 6
    rule_ids = [r.rule_id for r in rules]
    assert "ISO27001-A5.12-001" in rule_ids
    assert "ISO27001-A5.33-001" in rule_ids
    assert "ISO27001-A5.34-001" in rule_ids
    assert "ISO27001-A8.11-001" in rule_ids
    assert "ISO27001-A8.12-001" in rule_ids
    assert "ISO27001-A8.10-001" in rule_ids


def test_iso27001_rule_fields():
    registry = RuleRegistry()
    rules = registry.get_rules("iso27001")

    # A5.12 — PII classification check (UNKNOWN action)
    a512 = next(r for r in rules if r.rule_id == "ISO27001-A5.12-001")
    assert a512.severity == Severity.LOW
    assert a512.action == RuleAction.UNKNOWN
    assert "pii_present" in a512.condition

    # A8.12 — Unique ID encryption (FAIL action, HIGH severity)
    a812 = next(r for r in rules if r.rule_id == "ISO27001-A8.12-001")
    assert a812.severity == Severity.HIGH
    assert a812.action == RuleAction.FAIL
    assert "unique_id" in a812.condition
    assert "encrypted" in a812.condition

    assert all(r.law_id == "ISO27001" for r in rules)
