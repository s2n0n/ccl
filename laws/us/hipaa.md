---
law_id: HIPAA
jurisdiction: US
version: "2013-01-25"
source_url: https://www.hhs.gov/hipaa/for-professionals/index.html
effective_date: "1996-08-21"
---

# Health Insurance Portability and Accountability Act (HIPAA) — Compliance Reference

HIPAA establishes national standards to protect individuals' medical records and other individually
identifiable health information (PHI — Protected Health Information).

---

## 45 CFR 164.514 — De-identification of Protected Health Information

**Summary:** Health information is not individually identifiable if it does not identify an
individual and if there is no reasonable basis to believe it can be used to identify an individual.
PHI that is not de-identified must be safeguarded. Health-related columns must be masked or
de-identified.

**Validation Rule Mapping:**
- rule_id: HIPAA-164514-001
- severity: HIGH
- article: HIPAA 45 CFR 164.514 (De-identification of PHI)
- description: Protected Health Information (PHI) present without masking or de-identification
- condition: any_column(category='sensitive', masked=False)
- action: FAIL

---

## 45 CFR 164.312 — Technical Safeguards

**Summary:** A covered entity must implement technical security measures to guard against
unauthorized access to electronic PHI. Encryption is required for PHI at rest and in transit.
Unique identifiers associated with health records must be encrypted.

**Validation Rule Mapping:**
- rule_id: HIPAA-164312-001
- severity: HIGH
- article: HIPAA 45 CFR 164.312 (Technical Safeguards)
- description: Unique identifiers linked to health records are not encrypted
- condition: any_column(category='unique_id', encrypted=False)
- action: FAIL
