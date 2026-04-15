"""OpenAI API 어댑터."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ccl.llm.adapter import HttpLLMAdapter, LLMResponse

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIAdapter(HttpLLMAdapter):
    def __init__(self, model: str, timeout: int = 30) -> None:
        super().__init__(
            model=model,
            timeout=timeout,
            env_var="OPENAI_API_KEY",
            error_msg=(
                "OPENAI_API_KEY 환경변수가 설정되지 않았습니다. "
                "export OPENAI_API_KEY=sk-... 를 실행하세요."
            ),
        )

    def complete(self, prompt: str) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": 1024,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            _API_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
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
                f"OpenAI API 오류 {e.code}: {body_text}"
            ) from e
        latency = int((time.monotonic() - t0) * 1000)

        content = body["choices"][0]["message"]["content"]
        tokens = body.get("usage", {}).get("total_tokens", 0)
        return LLMResponse(content=content, tokens_used=tokens, latency_ms=latency)

    def metadata(self) -> dict:
        return {"provider": "openai", "model": self.model, "endpoint": None}
