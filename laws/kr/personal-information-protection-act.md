---
law_id: KR-PIPA
jurisdiction: KR
version: "2023-09-15"
source_url: https://www.law.go.kr/법령/개인정보보호법
effective_date: "2023-09-15"
---

# 개인정보 보호법 (컴플라이언스 참조본)

개인정보 보호법은 개인정보의 처리 및 보호에 관한 사항을 정함으로써 개인의 자유와 권리를 보호하고
나아가 개인의 존엄과 가치를 구현함을 목적으로 한다.

---

## Article 2 — 정의 (개인정보 해당 여부)

**원문 요약:** "개인정보"란 살아 있는 개인에 관한 정보로서 성명, 주민등록번호, 영상 등을 통하여
개인을 알아볼 수 있는 정보 또는 해당 정보만으로는 알아볼 수 없더라도 다른 정보와 쉽게 결합하여
개인을 알아볼 수 있는 정보를 말한다.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART2-001
- severity: LOW
- article: 개인정보보호법 제2조 (개인정보 정의)
- description: 데이터셋에 개인정보(PII)가 포함되어 있음 — 처리 목적 및 근거 검토 필요
- condition: pii_present()
- action: UNKNOWN

---

## Article 18 — 개인정보의 목적 외 이용·제공 제한

**원문 요약:** 개인정보처리자는 개인정보를 수집 목적 이외의 용도로 이용하거나 제3자에게 제공하여서는
아니 된다. 단, 정보주체의 별도 동의, 법률 규정 등의 예외가 있다.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART18-001
- severity: MEDIUM
- article: 개인정보보호법 제18조 (목적 외 이용·제공 제한)
- description: 데이터 처리 목적이 명시되지 않음 — 목적 외 이용 가능성 존재
- condition: purpose_unspecified()
- action: UNKNOWN

---

## Article 21 — 개인정보의 파기

**원문 요약:** 개인정보처리자는 보유기간의 경과, 개인정보의 처리 목적 달성 등 그 개인정보가 불필요하게
되었을 때에는 지체 없이 그 개인정보를 파기하여야 한다.
일반적인 법정 보유기간은 최대 5년(1825일)을 기준으로 한다.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART21-001
- severity: HIGH
- article: 개인정보보호법 제21조 (개인정보의 파기)
- description: 데이터 보유기간이 법정 한도(1825일, 5년)를 초과함
- condition: retention_exceeded(days=1825)
- action: FAIL

---

## Article 23 — 민감정보 처리 제한

**원문 요약:** 사상·신념, 노동조합·정당 가입/탈퇴, 정치적 견해, 건강, 성생활, 유전정보, 범죄경력,
생체인식정보는 원칙적으로 처리 금지. 단, 정보주체의 명시적 동의가 있거나 법령에서 허용한 경우 예외.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART23-001
- severity: HIGH
- article: 개인정보보호법 제23조 (민감정보 처리 제한)
- description: 민감정보(건강, 생체, 정치적 견해 등)가 마스킹되지 않음
- condition: any_column(category='sensitive', masked=False)
- action: FAIL

---

## Article 24 — 고유식별정보 처리 제한

**원문 요약:** 주민등록번호, 여권번호, 운전면허번호, 외국인등록번호 등 고유식별정보는 별도 동의 또는
법령에서 허용한 경우에만 처리 가능하며, 암호화 등 안전성 확보 조치가 필요하다.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART24-001
- severity: HIGH
- article: 개인정보보호법 제24조 (고유식별정보 처리 제한)
- description: 고유식별정보(주민등록번호, 여권번호 등)가 암호화되지 않음
- condition: any_column(category='unique_id', encrypted=False)
- action: FAIL

---

## Article 29 — 안전조치의무

**원문 요약:** 개인정보처리자는 개인정보가 분실·도난·유출·위조·변조 또는 훼손되지 아니하도록
내부 관리계획 수립, 접속기록 보관 및 점검, 암호화 조치 등 대통령령으로 정하는 바에 따라
안전성 확보에 필요한 기술적·관리적·물리적 조치를 하여야 한다.

**검증 룰 매핑:**
- rule_id: KR-PIPA-ART29-001
- severity: HIGH
- article: 개인정보보호법 제29조 (안전조치의무)
- description: 직접 식별자(이메일, 전화번호 등)가 마스킹되지 않음
- condition: any_column(category='direct_identifier', masked=False)
- action: FAIL
