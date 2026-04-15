"""Ollama 로컬 LLM 어댑터 (오프라인 실행 가능)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ccl.llm.adapter import LLMAdapter, LLMResponse


class OllamaAdapter(LLMAdapter):
    def __init__(
        self,
        model: str,
        endpoint: str = "http://localhost:11434",
        timeout: int = 30,
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self._timeout = timeout

    def complete(self, prompt: str) -> LLMResponse:
        url = f"{self.endpoint}/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            body = json.loads(resp.read().decode())
        latency = int((time.monotonic() - t0) * 1000)

        content = body.get("message", {}).get("content", "")
        tokens = body.get("eval_count", 0) + body.get("prompt_eval_count", 0)
        return LLMResponse(content=content, tokens_used=tokens, latency_ms=latency)

    def health_check(self) -> bool:
        try:
            url = f"{self.endpoint}/api/tags"
            with urllib.request.urlopen(url, timeout=5):
                return True
        except Exception:
            return False

    def metadata(self) -> dict:
        return {
            "provider": "ollama",
            "model": self.model,
            "endpoint": self.endpoint,
        }
