from __future__ import annotations

import os
import random
from pathlib import Path

import pyarrow.parquet as pq

from ccl.models import ColumnSchema, SampleSchema


class ParquetExtractor:
    def extract(self, path: str, sample_rows: int = 500) -> SampleSchema:
        pf = pq.ParquetFile(path)
        total_rows = pf.metadata.num_rows
        num_groups = pf.metadata.num_row_groups

        # Reservoir sample across row groups
        rows_per_group = max(1, sample_rows // max(1, num_groups))
        frames = []
        for i in range(num_groups):
            rg = pf.read_row_group(i)
            df = rg.to_pandas().astype(str)
            frames.append(df.head(rows_per_group))

        import pandas as pd
        df = pd.concat(frames, ignore_index=True).head(sample_rows) if frames else pd.DataFrame()

        dataset_id = Path(path).stem
        columns = []
        for col in df.columns:
            sample_values = df[col].dropna().tolist()
            columns.append(ColumnSchema(name=col, sample_values=sample_values))

        return SampleSchema(
            dataset_id=dataset_id,
            columns=columns,
            row_count=total_rows,
            source_path=os.path.abspath(path),
        )
