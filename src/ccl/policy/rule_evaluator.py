"""Evaluate rules against a SampleSchema using a fixed-vocabulary condition DSL."""
from __future__ import annotations

import re

from ccl.models import (
    ColumnCategory,
    Rule,
    RuleAction,
    SampleSchema,
    Severity,
    Violation,
    ViolationStatus,
)

# ── Condition grammar ─────────────────────────────────────────────────────────
# Supported predicates:
#   pii_present()
#   any_column(category='X', masked=False)
#   any_column(category='X', encrypted=False)
#   retention_exceeded(days=N)
#   purpose_unspecified()
#   consent_missing()
# ─────────────────────────────────────────────────────────────────────────────

_ACTION_TO_STATUS: dict[RuleAction, ViolationStatus] = {
    RuleAction.FAIL:    ViolationStatus.FAIL,
    RuleAction.PASS:    ViolationStatus.PASS,
    RuleAction.UNKNOWN: ViolationStatus.UNKNOWN,
}

_ANY_COLUMN_RE = re.compile(
    r"any_column\(category=['\"](?P<category>[^'\"]+)['\"]"
    r"(?:,\s*(?P<field>masked|encrypted)=(?P<val>True|False))?\)"
)
_RETENTION_RE = re.compile(r"retention_exceeded\(days=(?P<days>\d+)\)")


class RuleEvaluator:
    def evaluate(self, schema: SampleSchema, rules: list[Rule]) -> list[Violation]:
        violations = []
        for rule in rules:
            try:
                result, affected_column = self._eval_condition(rule.condition, schema)
            except ParseError as e:
                # Unknown condition = UNKNOWN, not silent pass
                violations.append(Violation(
                    rule_id=rule.rule_id,
                    article=rule.article,
                    description=f"[PARSE ERROR] {e}",
                    severity=rule.severity,
                    status=ViolationStatus.UNKNOWN,
                ))
                continue

            if result is None:
                # Condition returned UNKNOWN (missing data)
                violations.append(Violation(
                    rule_id=rule.rule_id,
                    article=rule.article,
                    description=rule.description,
                    severity=rule.severity,
                    status=ViolationStatus.UNKNOWN,
                    column=affected_column,
                ))
            elif result is True:
                status = _ACTION_TO_STATUS[rule.action]
                violations.append(Violation(
                    rule_id=rule.rule_id,
                    article=rule.article,
                    description=rule.description,
                    severity=rule.severity,
                    status=status,
                    column=affected_column,
                ))
            # result is False → PASS, no violation recorded

        return violations

    def _eval_condition(
        self, condition: str, schema: SampleSchema
    ) -> tuple[bool | None, str | None]:
        """Return (result, affected_column_name).
        result: True=violated, False=ok, None=unknown/missing-data.
        """
        cond = condition.strip()

        if cond == "pii_present()":
            result = any(c.pii_detected for c in schema.columns)
            col = next((c.name for c in schema.columns if c.pii_detected), None)
            return result, col

        if cond == "purpose_unspecified()":
            if schema.purpose_specified is False:
                return None, None  # UNKNOWN — we don't know if it's truly unspecified
            return False, None

        if cond == "consent_missing()":
            if not schema.consent_records_present:
                return True, None
            return False, None

        m = _ANY_COLUMN_RE.match(cond)
        if m:
            return self._eval_any_column(m, schema)

        m = _RETENTION_RE.match(cond)
        if m:
            return self._eval_retention(int(m.group("days")), schema)

        raise ParseError(f"Unrecognized condition: {cond!r}")

    def _eval_any_column(
        self, m: re.Match, schema: SampleSchema
    ) -> tuple[bool | None, str | None]:
        category_str = m.group("category")
        try:
            category = ColumnCategory(category_str)
        except ValueError:
            raise ParseError(f"Unknown category: {category_str!r}")

        field = m.group("field")    # "masked" or "encrypted" or None
        val_str = m.group("val")    # "True" or "False" or None

        for col in schema.columns:
            if col.category != category:
                continue
            if field is None:
                return True, col.name
            expected = val_str == "True"
            actual = getattr(col, field)
            if actual == expected:
                return True, col.name

        return False, None

    def _eval_retention(
        self, threshold_days: int, schema: SampleSchema
    ) -> tuple[bool | None, str | None]:
        if schema.retention_days is None:
            return None, None  # UNKNOWN
        return schema.retention_days > threshold_days, None


class ParseError(ValueError):
    pass
