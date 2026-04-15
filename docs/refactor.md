# CCL 리팩터링 컨텍스트

> **목적**: 기능 변경 없이 코드 품질을 개선한다.
> **원칙**: 동작하는 테스트(50개)를 모두 통과시키면서 변경한다.
> **범위**: `src/ccl/` 전체. 테스트 코드는 필요한 경우에만 수정.

---

## 1. 미사용 임포트 / 변수 제거

| 파일 | 항목 | 이유 |
|------|------|------|
| `extractor/csv_extractor.py:4` | `import uuid` | 코드 내 미사용 |
| `extractor/parquet_extractor.py:4` | `import random` | 코드 내 미사용 |
| `extractor/base.py:3` | `import os` | 코드 내 미사용 |
| `llm/adapter.py:5` | `field` (from dataclasses) | `LLMResponse` dataclass에서 미사용 |
| `llm/augmentor.py:7` | `LLMResponse` 임포트 | augmentor.py 내에서 직접 사용 없음 |
| `policy/rule_evaluator.py:5` | `from typing import Any` | 코드 내 미사용 |
| `audit/logger.py:8` | `from typing import TextIO` | 타입 애노테이션에 사용되지 않음 |

---

## 2. 타입 애노테이션 일관성

**파일**: `cli.py`

`validate` 함수와 `_run_validate` 함수 시그니처에서 `Optional[str]`과 `str | None`이 혼재한다.
`from __future__ import annotations`가 선언된 이상 `str | None` 형식으로 통일하고 `from typing import Optional` 임포트를 제거한다.

```python
# 현재 (cli.py:65-74 일부)
metadata_path: Optional[str],
output_path: Optional[str],

# 개선
metadata_path: str | None,
output_path: str | None,
```

---

## 3. 간소화 가능한 로직

### 3-1. `to_exit_code()` — unreachable branch 제거

**파일**: `models.py:129-137`

```python
# 현재: return 3 는 도달 불가 (Enum 3개, 모두 커버됨)
def to_exit_code(self) -> int:
    if self.status == ReportStatus.PASS:    return 0
    if self.status == ReportStatus.FAIL:    return 1
    if self.status == ReportStatus.UNKNOWN: return 2
    return 3  # dead code

# 개선: dict 매핑 (모듈 레벨)
_EXIT_CODES = {ReportStatus.PASS: 0, ReportStatus.FAIL: 1, ReportStatus.UNKNOWN: 2}

def to_exit_code(self) -> int:
    return _EXIT_CODES[self.status]
```

### 3-2. `_PREDICATES` — 사용되지 않는 집합 제거

**파일**: `policy/rule_evaluator.py:27-33`

`_PREDICATES: set` 은 정의만 되어 있고 실제 평가 로직에서 조회하거나 검증에 사용되지 않는다. 주석으로 충분하므로 삭제한다.

### 3-3. `_default_model()` — 호출마다 dict 생성 제거

**파일**: `cli.py:198-203`

```python
# 현재: 호출마다 dict 리터럴 생성
def _default_model(provider: str) -> str:
    return {"ollama": "llama3.2", ...}.get(provider.lower(), "")

# 개선: 모듈 레벨 상수
_DEFAULT_MODELS: dict[str, str] = {
    "ollama": "llama3.2",
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
}

def _default_model(provider: str) -> str:
    return _DEFAULT_MODELS.get(provider.lower(), "")
```

### 3-4. `pandas` 지연 임포트 위치 이동

**파일**: `extractor/parquet_extractor.py:27`

`import pandas as pd`가 `extract()` 메서드 내부 중간에 위치한다. 다른 임포트와 함께 파일 상단으로 이동한다. (`csv_extractor.py`는 이미 파일 상단에 임포트)

### 3-5. `augmentor.py` 세미콜론 스타일

**파일**: `augmentor.py:71, 75, 81, 84`

```python
# 현재: 세미콜론으로 같은 줄에 여러 구문
tokens_total += t; latency_total += l; errors += e

# 개선: 줄 분리
tokens_total += t
latency_total += l
errors += e
```

---

## 4. 중복 로직 제거

### 4-1. 프롬프트 빌더의 스키마 텍스트 생성 중복

**파일**: `llm/prompts.py`

`build_resolve_prompt`(49-55행)와 `build_quasi_id_prompt`(85-90행)가 동일한 컬럼 → 텍스트 변환 루프를 가진다.

```python
# 두 곳에서 반복되는 패턴
col_lines = []
for col in schema.columns:
    samples = _trim_samples(col.sample_values, max_samples)
    col_lines.append(f"  - {col.name}: category={col.category.value}, ...")
schema_text = "\n".join(col_lines) or "  (no columns)"

# 개선: 내부 헬퍼로 추출
def _format_schema(schema: SampleSchema, max_samples: int, *, include_protection: bool = False) -> str:
    ...
```

`include_protection=True`이면 `masked=`, `encrypted=` 필드 포함, `False`이면 생략한다.

### 4-2. Cloud 어댑터의 `__init__` / `health_check` 중복

**파일**: `llm/claude.py`, `llm/openai.py`

두 어댑터가 동일한 패턴을 가진다:
- `__init__`: 환경변수에서 API 키 읽기 + 미설정 시 `RuntimeError`
- `health_check()`: `return bool(self._api_key)`

`LLMAdapter` 베이스에 공통 초기화와 `health_check`를 올린 중간 클래스를 도입한다.

```python
class HttpLLMAdapter(LLMAdapter):
    def __init__(self, model: str, timeout: int, env_var: str, error_msg: str) -> None:
        self.model = model
        self._timeout = timeout
        api_key = os.environ.get(env_var, "")
        if not api_key:
            raise RuntimeError(error_msg)
        self._api_key = api_key

    def health_check(self) -> bool:
        return bool(self._api_key)
```

---

## 5. 응집도 문제

### 5-1. `RuleRegistry` — 파일 읽기 이중화

**파일**: `policy/rule_registry.py`

`_run_validate`에서 같은 law_id에 대해:
1. `registry.get_rules(law_id)` → `parser.parse()` → 파일 읽기 1회
2. `registry.get_law_metadata(law_id)` → `frontmatter.load()` → 파일 읽기 1회

동일 파일을 2회 읽는다.

**개선 방향**: `_load()`에서 프론트매터와 규칙을 함께 파싱하여 `(metadata, rules)` 튜플을 캐시에 저장한다.

```python
# 현재: 단일 캐시
self._cache: dict[str, list[Rule]] = {}

# 개선: 통합 캐시
self._cache: dict[str, tuple[dict, list[Rule]]] = {}
```

### 5-2. `LawParser` — 파일 I/O와 파싱 혼재

**파일**: `policy/law_parser.py:31-33`

`parse(path: str)`가 파일을 직접 읽는다. `RuleRegistry`가 파일 읽기를 담당하도록 하고 `LawParser`는 텍스트만 받아 파싱하도록 분리한다.

```python
# 현재
def parse(self, path: str) -> list[Rule]:
    text = Path(path).read_text(encoding="utf-8")
    ...

# 개선: 핵심 로직을 텍스트 기반으로 분리
def parse(self, path: str) -> list[Rule]:           # 하위호환 래퍼 유지
    text = Path(path).read_text(encoding="utf-8")
    return self.parse_text(text, law_id=Path(path).stem)

def parse_text(self, text: str, law_id: str) -> list[Rule]:   # 테스트 및 재사용 용이
    post = frontmatter.loads(text)
    actual_law_id = post.metadata.get("law_id", law_id)
    ...
```

---

## 6. 결합도 문제

### 6-1. `LLMAdapter` — 런타임 오류 대신 추상 클래스 사용

**파일**: `llm/adapter.py:15-26`

현재 서브클래스가 메서드를 빠뜨려도 인스턴스화 시점이 아닌 호출 시점에야 오류가 발생한다.

```python
# 개선
from abc import ABC, abstractmethod

class LLMAdapter(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> LLMResponse: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    @abstractmethod
    def metadata(self) -> dict: ...
```

### 6-2. `RuleAction` → `ViolationStatus` 문자열 값 의존

**파일**: `policy/rule_evaluator.py:70`

```python
status = ViolationStatus(rule.action.value)  # 두 Enum의 문자열 값이 동일하다는 암묵적 가정
```

명시적 매핑으로 변경한다.

```python
_ACTION_TO_STATUS: dict[RuleAction, ViolationStatus] = {
    RuleAction.FAIL:    ViolationStatus.FAIL,
    RuleAction.PASS:    ViolationStatus.PASS,
    RuleAction.UNKNOWN: ViolationStatus.UNKNOWN,
}

# 사용
status = _ACTION_TO_STATUS[rule.action]
```

---

## 7. 리팩터링 우선순위

| 우선순위 | 항목 | 위험도 |
|----------|------|--------|
| 높음 | 미사용 임포트 제거 (섹션 1) | 없음 |
| 높음 | 타입 애노테이션 일관성 (섹션 2) | 없음 |
| 높음 | `_PREDICATES` 제거 (섹션 3-2) | 없음 |
| 높음 | `pandas` 임포트 위치 이동 (섹션 3-4) | 없음 |
| 높음 | 세미콜론 스타일 (섹션 3-5) | 없음 |
| 중간 | `to_exit_code` dead code 제거 (섹션 3-1) | 낮음 |
| 중간 | `_default_model` 상수화 (섹션 3-3) | 낮음 |
| 중간 | `LLMAdapter` ABC화 (섹션 6-1) | 낮음 |
| 중간 | `RuleAction→ViolationStatus` 명시 매핑 (섹션 6-2) | 낮음 |
| 중간 | 프롬프트 빌더 중복 제거 (섹션 4-1) | 낮음 |
| 낮음 | Cloud 어댑터 공통 베이스 (섹션 4-2) | 중간 |
| 낮음 | `RuleRegistry` 파일 이중 읽기 제거 (섹션 5-1) | 중간 |
| 낮음 | `LawParser` I/O 분리 (섹션 5-2) | 중간 |

---

## 8. 변경 불가 항목 (설계 의도)

- `report.status` / `summary` / `to_exit_code()`는 규칙 엔진 결과만 반영 (LLM 결과 미영향) — 의도된 설계
- `_run_validate`와 `validate`의 파라미터 중복 — Click Runner 없이 `_run_validate`를 직접 테스트하기 위한 분리
- `augmentor.py`의 4-tuple `(result, tokens, latency, errors)` 반환 패턴 — 에러 누산과 메트릭 집계를 위한 의도적 구조
- `PIIScanner._detect_from_name`의 키워드 튜플 — 명시적 도메인 목록으로 의도된 것
- `RuleRegistry.LAW_ID_TO_RELATIVE_PATH` 딕셔너리 — 지원 법률 목록은 코드 변경을 통해 관리하는 설계
