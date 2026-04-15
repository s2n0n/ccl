---
law_id: JP-APPI
jurisdiction: JP
version: "2022-04-01"
source_url: https://www.ppc.go.jp/en/legal/
effective_date: "2022-04-01"
---

# Act on the Protection of Personal Information (APPI) — Compliance Reference

The Act on the Protection of Personal Information (個人情報の保護に関する法律) is Japan's primary
data protection legislation. The 2022 amendment significantly strengthened protections.

---

## Article 2 — Definition of Personal Information

**Summary:** "Personal information" means information about a living individual which can identify
the specific individual by name, date of birth, or other description contained in such information,
including information that can be easily collated with other information to identify the individual.

**Validation Rule Mapping:**
- rule_id: JP-APPI-ART2-001
- severity: LOW
- article: APPI Article 2 (Personal Information Definition)
- description: Dataset contains personal information — handling rules under APPI apply
- condition: pii_present()
- action: UNKNOWN

---

## Article 20 — Restrictions on Handling of Special Care-Required Personal Information

**Summary:** A personal information handling business operator must not acquire special care-required
personal information without prior consent from the individual, except in certain specified cases.
Special care-required information includes race, creed, social status, medical history, criminal
record, and other information that may cause social discrimination.

**Validation Rule Mapping:**
- rule_id: JP-APPI-ART20-001
- severity: HIGH
- article: APPI Article 20 (Special Care-Required Personal Information)
- description: Special care-required personal information found without masking
- condition: any_column(category='sensitive', masked=False)
- action: FAIL

---

## Article 22 — Security Control Measures

**Summary:** A personal information handling business operator must take necessary and appropriate
actions for the prevention of leakage, loss, or damage of personal information and other security
management of personal information. This includes encryption of identifying information.

**Validation Rule Mapping:**
- rule_id: JP-APPI-ART22-001
- severity: HIGH
- article: APPI Article 22 (Security Control Measures)
- description: Identifying information is not encrypted — security control measures insufficient
- condition: any_column(category='unique_id', encrypted=False)
- action: FAIL
