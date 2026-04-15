from __future__ import annotations

from ccl.models import ColumnCategory, ColumnSchema, SampleSchema
from ccl.scanner.patterns import ENCRYPT_PATTERNS, MASK_PATTERNS, PATTERN_GROUPS

_MASK_THRESHOLD = 0.9
_ENCRYPT_THRESHOLD = 0.9
_DETECTION_THRESHOLD = 0.05  # 5% of sample values must match to flag a column


class PIIScanner:
    def scan(self, schema: SampleSchema) -> SampleSchema:
        """Annotate each ColumnSchema with PII detection results. Returns mutated copy."""
        updated_columns = [self._scan_column(col) for col in schema.columns]
        return schema.model_copy(update={"columns": updated_columns})

    def _scan_column(self, col: ColumnSchema) -> ColumnSchema:
        values = col.sample_values
        if not values:
            return col

        non_null = [v for v in values if v and v.lower() not in ("nan", "none", "null", "")]

        masked = self._check_ratio(non_null, MASK_PATTERNS) >= _MASK_THRESHOLD
        encrypted = (not masked) and self._check_ratio(non_null, ENCRYPT_PATTERNS) >= _ENCRYPT_THRESHOLD

        category = ColumnCategory.GENERAL
        pii_detected = False

        # Check column name as a hint (lower priority than values)
        name_category = self._detect_from_name(col.name)

        # Check values for PII patterns (higher priority)
        for group in PATTERN_GROUPS:
            hit_ratio = self._check_ratio(non_null, group.patterns)
            if hit_ratio >= _DETECTION_THRESHOLD:
                category = ColumnCategory(group.category)
                pii_detected = True
                break

        # If values didn't trigger, use name hint if present
        if category == ColumnCategory.GENERAL and name_category:
            category = name_category
            pii_detected = True

        return col.model_copy(update={
            "pii_detected": pii_detected,
            "category": category,
            "masked": masked,
            "encrypted": encrypted,
        })

    def _check_ratio(self, values: list[str], patterns: list) -> float:
        if not values:
            return 0.0
        matches = sum(
            1 for v in values if any(p.search(v) for p in patterns)
        )
        return matches / len(values)

    def _detect_from_name(self, name: str) -> ColumnCategory | None:
        """Return a category hint from the column name, or None."""
        name_lower = name.lower()
        sensitive_keywords = (
            "health", "disease", "diagnosis", "medical", "biometric",
            "fingerprint", "religion", "political", "union", "sexual",
            "건강", "진단", "생체", "지문", "종교", "정치", "노동조합",
        )
        unique_id_keywords = (
            "rrn", "ssn", "jumin", "주민", "passport", "여권", "license",
            "resident_id", "national_id",
        )
        direct_id_keywords = (
            "email", "phone", "mobile", "tel", "이메일", "전화", "핸드폰",
            "ip_address", "ip_addr",
        )
        for kw in sensitive_keywords:
            if kw in name_lower:
                return ColumnCategory.SENSITIVE
        for kw in unique_id_keywords:
            if kw in name_lower:
                return ColumnCategory.UNIQUE_ID
        for kw in direct_id_keywords:
            if kw in name_lower:
                return ColumnCategory.DIRECT_IDENTIFIER
        return None
