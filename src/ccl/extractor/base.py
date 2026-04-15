from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ccl.models import SampleSchema


class AbstractExtractor(Protocol):
    def extract(self, path: str, sample_rows: int = 500) -> SampleSchema: ...


def get_extractor(path: str) -> AbstractExtractor:
    """Return the appropriate extractor based on file extension."""
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        from ccl.extractor.csv_extractor import CSVExtractor
        return CSVExtractor()
    if ext in (".parquet", ".pq"):
        from ccl.extractor.parquet_extractor import ParquetExtractor
        return ParquetExtractor()
    raise ValueError(f"Unsupported file format: {ext}. Supported: .csv, .parquet")
