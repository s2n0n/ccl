"""LLM adapter base class and factory."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    tokens_used: int = 0
    latency_ms: int = 0


class LLMAdapter:
    """Base class for LLM adapters. Subclasses implement complete()."""

    def complete(self, prompt: str) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError

    def health_check(self) -> bool:  # pragma: no cover
        raise NotImplementedError

    def metadata(self) -> dict:  # pragma: no cover
        raise NotImplementedError


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
