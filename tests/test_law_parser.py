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
