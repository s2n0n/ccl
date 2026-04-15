"""Tests for data extractors."""
from __future__ import annotations

from ccl.extractor.base import get_extractor
from ccl.models import SampleSchema


def test_csv_extractor_clean(clean_csv):
    extractor = get_extractor(clean_csv)
    schema = extractor.extract(clean_csv)

    assert isinstance(schema, SampleSchema)
    assert schema.row_count == 5
    assert len(schema.columns) == 5
    col_names = [c.name for c in schema.columns]
    assert "user_id" in col_names
    assert "email" not in col_names


def test_csv_extractor_columns_have_sample_values(violations_csv):
    extractor = get_extractor(violations_csv)
    schema = extractor.extract(violations_csv)

    email_col = next(c for c in schema.columns if c.name == "email")
    assert len(email_col.sample_values) > 0
    assert "alice@example.com" in email_col.sample_values


def test_csv_extractor_sample_rows_limit(violations_csv):
    extractor = get_extractor(violations_csv)
    schema = extractor.extract(violations_csv, sample_rows=2)
    email_col = next(c for c in schema.columns if c.name == "email")
    assert len(email_col.sample_values) <= 2


def test_unsupported_format():
    import pytest
    with pytest.raises(ValueError, match="Unsupported file format"):
        get_extractor("data.xlsx")
