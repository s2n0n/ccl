"""Append-only JSONL audit logger."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from ccl import __version__
from ccl.models import ComplianceReport


class AuditLogger:
    def __init__(self, output_path: str | None = None) -> None:
        """If output_path is None, write to stderr."""
        self._path = output_path

    def log(self, report: ComplianceReport) -> None:
        record = {
            "timestamp": report.timestamp.isoformat() + "Z",
            "dataset_id": report.dataset_id,
            "law_ids": report.jurisdiction,
            "status": report.status.value,
            "violations_count": len(report.violations),
            "failed": report.summary.failed,
            "unknown": report.summary.unknown,
            "engine_version": __version__,
        }
        line = json.dumps(record, ensure_ascii=False)
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            print(line, file=sys.stderr)
