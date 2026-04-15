"""Compiled regex patterns for PII detection."""
from __future__ import annotations

import re
from typing import NamedTuple


class PatternGroup(NamedTuple):
    category: str  # maps to ColumnCategory values
    patterns: list[re.Pattern]


# Each group listed in priority order: sensitive > unique_id > direct_identifier
PATTERN_GROUPS: list[PatternGroup] = [
    PatternGroup(
        category="sensitive",
        patterns=[
            # 건강/의료 키워드 (column name hint or value keyword)
            # Note: \b does not work with Korean; use (?i) flag with lookaround-free patterns
            re.compile(r"(?i)(diagnosis|disease|health|medical|patient|prescription|symptom)"),
            re.compile(r"(치료|진단|병명|건강|의료|혈액형|당뇨|고혈압|비만|암|질환|질병)"),
            # 생체정보
            re.compile(r"(?i)(fingerprint|biometric|retina|face_id)"),
            re.compile(r"(지문|홍채|생체)"),
            # 정치적 견해
            re.compile(r"(?i)(political|religion|belief|trade.?union)"),
            re.compile(r"(노동조합|정당|정치|신념|종교)"),
            # 성생활
            re.compile(r"(?i)(sexual|gender_identity|orientation)"),
            re.compile(r"(성생활|성정체성)"),
        ],
    ),
    PatternGroup(
        category="unique_id",
        patterns=[
            # 주민등록번호 (RRRRRRR-XXXXXXX)
            re.compile(r"\b\d{6}-[1-4]\d{6}\b"),
            # 여권번호
            re.compile(r"\b[A-Z]{1,2}\d{7,9}\b"),
            # SSN (US)
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            # 운전면허번호 (KR)
            re.compile(r"\b\d{2}-\d{2}-\d{6}-\d{2}\b"),
        ],
    ),
    PatternGroup(
        category="direct_identifier",
        patterns=[
            # Email
            re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
            # Korean phone
            re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b"),
            # International phone (E.164)
            re.compile(r"\+\d{7,15}\b"),
            # Credit card (basic Luhn pattern)
            re.compile(r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"),
            # IPv4
            re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        ],
    ),
]

# Masking patterns: value is considered masked if it matches one of these
MASK_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\*+$"),
    re.compile(r"^X+$", re.I),
    re.compile(r"^REDACTED$", re.I),
    re.compile(r"^MASKED$", re.I),
    re.compile(r"^\[.*REDACTED.*\]$", re.I),
    re.compile(r"^#+$"),
    re.compile(r"^\*{3,}$"),
]

# Encryption heuristic: SHA256 hex, bcrypt, base64 tokens
ENCRYPT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^[a-f0-9]{64}$"),            # SHA256
    re.compile(r"^[a-f0-9]{40}$"),            # SHA1
    re.compile(r"^\$2[aby]\$\d{2}\$.{53}$"),  # bcrypt
    re.compile(r"^[A-Za-z0-9+/]{43}=$"),      # base64 32-byte
    re.compile(r"^[A-Za-z0-9_\-]{32,}$"),     # generic token (UUID-like)
]
