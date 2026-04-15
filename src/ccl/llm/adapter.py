"""LLM adapter base class and factory."""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    tokens_used: int = 0
    latency_ms: int = 0


class LLMAdapter(ABC):
    """Base class for LLM adapters. Subclasses implement complete()."""

    @abstractmethod
    def complete(self, prompt: str) -> LLMResponse: ...

    @abstractmethod
    def health_check(self) -> bool: ...

    @abstractmethod
    def metadata(self) -> dict: ...


class HttpLLMAdapter(LLMAdapter):
    """API 키 기반 HTTP LLM 어댑터의 공통 초기화 및 health_check."""

    def __init__(self, model: str, timeout: int, env_var: str, error_msg: str) -> None:
        self.model = model
        self._timeout = timeout
        api_key = os.environ.get(env_var, "")
        if not api_key:
            raise RuntimeError(error_msg)
        self._api_key = api_key

    def health_check(self) -> bool:
        return bool(self._api_key)


def create_adapter(
    provider: str,
    model: str,
    endpoint: str | None = None,
    timeout: int = 30,
) -> LLMAdapter:
    """Factory: provider 이름으로 적합한 어댑터 인스턴스 반환."""
    p = provider.lower()
    if p == "ollama":
        from ccl.llm.ollama import OllamaAdapter
        return OllamaAdapter(
            model=model,
            endpoint=endpoint or "http://localhost:11434",
            timeout=timeout,
        )
    if p == "claude":
        from ccl.llm.claude import ClaudeAdapter
        return ClaudeAdapter(model=model, timeout=timeout)
    if p == "openai":
        from ccl.llm.openai import OpenAIAdapter
        return OpenAIAdapter(model=model, timeout=timeout)
    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Choose from: ollama, claude, openai"
    )
