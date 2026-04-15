"""Tests for PII Scanner."""
from __future__ import annotations

import pytest

from ccl.models import ColumnCategory, ColumnSchema, SampleSchema
from ccl.scanner.pii_scanner import PIIScanner


def _schema_with_column(name: str, values: list[str]) -> SampleSchema:
    return SampleSchema(
        dataset_id="test",
        columns=[ColumnSchema(name=name, sample_values=values)],
    )


def test_detects_email():
    schema = _schema_with_column("contact", ["alice@example.com", "bob@test.org"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.pii_detected is True
    assert col.category == ColumnCategory.DIRECT_IDENTIFIER


def test_detects_jumin():
    schema = _schema_with_column("id_number", ["850101-1234567", "920315-2345678"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.pii_detected is True
    assert col.category == ColumnCategory.UNIQUE_ID


def test_detects_health_keyword_in_values():
    schema = _schema_with_column("status", ["당뇨병", "고혈압", "건강함"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.pii_detected is True
    assert col.category == ColumnCategory.SENSITIVE


def test_masked_column():
    schema = _schema_with_column("email", ["***", "***", "***", "***", "***",
                                            "***", "***", "***", "***", "***"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.masked is True


def test_general_column_no_pii():
    schema = _schema_with_column("product_id", ["P001", "P002", "P003"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.pii_detected is False
    assert col.category == ColumnCategory.GENERAL


def test_column_name_hint_health():
    schema = _schema_with_column("health_status", ["good", "bad", "normal"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.pii_detected is True
    assert col.category == ColumnCategory.SENSITIVE


def test_column_name_hint_email():
    schema = _schema_with_column("user_email", ["value1", "value2"])
    result = PIIScanner().scan(schema)
    col = result.columns[0]
    assert col.pii_detected is True
    assert col.category == ColumnCategory.DIRECT_IDENTIFIER


def test_full_scan_violations_csv(violations_csv):
    from ccl.extractor.base import get_extractor
    extractor = get_extractor(violations_csv)
    schema = extractor.extract(violations_csv)
    scanned = PIIScanner().scan(schema)

    categories = {c.name: c.category for c in scanned.columns}
    assert categories["email"] == ColumnCategory.DIRECT_IDENTIFIER
    assert categories["jumin_number"] == ColumnCategory.UNIQUE_ID
    assert categories["health_status"] == ColumnCategory.SENSITIVE
