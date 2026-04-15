---
law_id: GDPR
jurisdiction: EU
version: "2018-05-25"
source_url: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679-20160504
effective_date: "2018-05-25"
---

# General Data Protection Regulation (GDPR) — Compliance Reference

The General Data Protection Regulation (EU) 2016/679 is a regulation in EU law on data protection
and privacy in the European Union and the European Economic Area.

---

## Article 4 — Definitions (Personal Data)

**Summary:** "Personal data" means any information relating to an identified or identifiable natural
person ("data subject"); an identifiable natural person is one who can be identified, directly or
indirectly, in particular by reference to an identifier such as a name, identification number,
location data, an online identifier.

**Validation Rule Mapping:**
- rule_id: GDPR-ART4-001
- severity: LOW
- article: GDPR Article 4 (Personal Data Definition)
- description: Dataset contains personal data (PII) — processing lawful basis review required
- condition: pii_present()
- action: UNKNOWN

---

## Article 7 — Conditions for Consent

**Summary:** Where processing is based on consent, the controller shall be able to demonstrate that
the data subject has consented to processing of his or her personal data. Consent must be freely
given, specific, informed and unambiguous.

**Validation Rule Mapping:**
- rule_id: GDPR-ART7-001
- severity: HIGH
- article: GDPR Article 7 (Conditions for Consent)
- description: Consent records are absent — processing without demonstrable consent violates GDPR Art.7
- condition: consent_missing()
- action: FAIL

---

## Article 9 — Processing of Special Categories of Personal Data

**Summary:** Processing of personal data revealing racial or ethnic origin, political opinions,
religious or philosophical beliefs, trade union membership, genetic data, biometric data for
uniquely identifying a natural person, health data, data concerning sex life or sexual orientation
is prohibited unless specific conditions are met (explicit consent, etc.).

**Validation Rule Mapping:**
- rule_id: GDPR-ART9-001
- severity: HIGH
- article: GDPR Article 9 (Special Categories of Personal Data)
- description: Special category data (health, biometric, political) found without masking
- condition: any_column(category='sensitive', masked=False)
- action: FAIL

---

## Article 25 — Data Protection by Design and by Default

**Summary:** The controller shall implement appropriate technical and organisational measures for
ensuring that, by default, only personal data which are necessary for each specific purpose are
processed. Direct identifiers should be pseudonymised or masked when not necessary.

**Validation Rule Mapping:**
- rule_id: GDPR-ART25-001
- severity: MEDIUM
- article: GDPR Article 25 (Data Protection by Design and by Default)
- description: Direct identifiers (email, phone, IP) are not masked — violates data minimisation principle
- condition: any_column(category='direct_identifier', masked=False)
- action: FAIL

---

## Article 5 — Principles Relating to Processing of Personal Data (Storage Limitation)

**Summary:** Personal data shall be kept in a form which permits identification of data subjects
for no longer than is necessary for the purposes for which the personal data are processed.
A common baseline for storage limitation is 3 years (1095 days) for general business data.

**Validation Rule Mapping:**
- rule_id: GDPR-ART5-001
- severity: HIGH
- article: GDPR Article 5(1)(e) (Storage Limitation)
- description: Data retention period exceeds GDPR storage limitation baseline (1095 days / 3 years)
- condition: retention_exceeded(days=1095)
- action: FAIL
