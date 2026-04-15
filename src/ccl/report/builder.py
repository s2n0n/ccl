"""Assemble the final ComplianceReport from violations."""
from __future__ import annotations

from ccl.models import (
    ComplianceReport,
    ReportStatus,
    ReportSummary,
    SampleSchema,
    Violation,
    ViolationStatus,
)


class ReportBuilder:
    def build(
        self,
        schema: SampleSchema,
        violations: list[Violation],
        law_ids: list[str],
        law_bundle_versions: dict[str, str],
    ) -> ComplianceReport:
        # Determine overall status: FAIL > UNKNOWN > PASS
        status = self._compute_status(violations)

        passed = sum(1 for v in violations if v.status == ViolationStatus.PASS)
        failed = sum(1 for v in violations if v.status == ViolationStatus.FAIL)
        unknown = sum(1 for v in violations if v.status == ViolationStatus.UNKNOWN)
        total = len(violations)

        # Build a single version string from all law bundles
        version_str = ", ".join(
            f"{lid}={law_bundle_versions.get(lid, 'unknown')}"
            for lid in law_ids
        )

        return ComplianceReport(
            dataset_id=schema.dataset_id,
            law_bundle_version=version_str,
            jurisdiction=[lid.upper() for lid in law_ids],
            status=status,
            violations=[v for v in violations if v.status != ViolationStatus.PASS],
            summary=ReportSummary(
                total_checks=total,
                passed=passed,
                failed=failed,
                unknown=unknown,
            ),
        )

    def _compute_status(self, violations: list[Violation]) -> ReportStatus:
        statuses = {v.status for v in violations}
        if ViolationStatus.FAIL in statuses:
            return ReportStatus.FAIL
        if ViolationStatus.UNKNOWN in statuses:
            return ReportStatus.UNKNOWN
        return ReportStatus.PASS
