"""Anthropic Claude API 어댑터."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from ccl.llm.adapter import LLMAdapter, LLMResponse

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class ClaudeAdapter(LLMAdapter):
    def __init__(self, model: str, timeout: int = 30) -> None:
        self.model = model
        self._timeout = timeout
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다. "
                "export ANTHROPIC_API_KEY=sk-ant-... 를 실행하세요."
            )
        self._api_key = api_key

    def complete(self, prompt: str) -> LLMResponse:
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            _API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
            },
            method="POST",
        )
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            raise RuntimeError(
                f"Claude API 오류 {e.code}: {body_text}"
            ) from e
        latency = int((time.monotonic() - t0) * 1000)

        content = body["content"][0]["text"]
        usage = body.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return LLMResponse(content=content, tokens_used=tokens, latency_ms=latency)

    def health_check(self) -> bool:
        return bool(self._api_key)

    def metadata(self) -> dict:
        return {"provider": "claude", "model": self.model, "endpoint": None}
