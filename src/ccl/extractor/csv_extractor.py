from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from ccl.models import ColumnSchema, SampleSchema


class CSVExtractor:
    def extract(self, path: str, sample_rows: int = 500) -> SampleSchema:
        df = self._read_csv(path, sample_rows)
        dataset_id = Path(path).stem
        columns = []
        for col in df.columns:
            sample_values = df[col].dropna().astype(str).tolist()[:sample_rows]
            columns.append(ColumnSchema(name=col, sample_values=sample_values))
        return SampleSchema(
            dataset_id=dataset_id,
            columns=columns,
            row_count=len(df),
            source_path=os.path.abspath(path),
        )

    def _read_csv(self, path: str, sample_rows: int) -> pd.DataFrame:
        encodings = ["utf-8", "cp949", "euc-kr", "latin-1"]
        for enc in encodings:
            try:
                df = pd.read_csv(path, dtype=str, nrows=sample_rows, encoding=enc)
                return df
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise ValueError(f"Could not decode {path} with any supported encoding")
