---
law_id: CCPA
jurisdiction: US-CA
version: "2023-01-01"
source_url: https://oag.ca.gov/privacy/ccpa
effective_date: "2020-01-01"
---

# California Consumer Privacy Act (CCPA) — Compliance Reference

The California Consumer Privacy Act of 2018 (CCPA) gives consumers more control over the personal
information that businesses collect about them.

---

## Section 1798.100 — Right to Know About Personal Information Collected

**Summary:** A consumer shall have the right to request that a business that collects a consumer's
personal information disclose the categories and specific pieces of personal information the
business has collected.

**Validation Rule Mapping:**
- rule_id: CCPA-S1798-001
- severity: LOW
- article: CCPA Section 1798.100 (Right to Know)
- description: Dataset contains personal information — consumer disclosure rights apply
- condition: pii_present()
- action: UNKNOWN

---

## Section 1798.100 — Sensitive Personal Information

**Summary:** Sensitive personal information includes social security number, driver's license number,
passport number, financial account information, precise geolocation, racial or ethnic origin,
religious or philosophical beliefs, health information, biometric information.

**Validation Rule Mapping:**
- rule_id: CCPA-S1798-002
- severity: HIGH
- article: CCPA Section 1798.100 (Sensitive Personal Information)
- description: Sensitive personal information is present without masking
- condition: any_column(category='sensitive', masked=False)
- action: FAIL

---

## Section 1798.100 — Unique Identifiers

**Summary:** Personal identifiers such as SSN, driver's license, or passport numbers must be
protected with appropriate security measures including encryption.

**Validation Rule Mapping:**
- rule_id: CCPA-S1798-003
- severity: HIGH
- article: CCPA Section 1798.100 (Unique Identifiers)
- description: Unique identifiers (SSN, passport, license) are not encrypted
- condition: any_column(category='unique_id', encrypted=False)
- action: FAIL
