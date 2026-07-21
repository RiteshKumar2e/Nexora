"""Ollama backend, driven through its OpenAI-compatible `/v1` API.

Only used when `llm_backend=ollama`. Because Ollama, vLLM, SGLang and
llama.cpp-server all expose the same OpenAI chat-completions contract, this
client works against any of them by pointing `base_url` elsewhere.

The default Nexora backend is our OWN in-process model (see `nano_client.py`);
this file also defines `LLMBackendError`, the shared "LLM failed" exception.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import ChatMessage, StreamChunk, Usage

log = get_logger("llm.ollama")


class LLMBackendError(RuntimeError):
    """Raised when an LLM backend fails (unreachable, bad status, etc.)."""


class OllamaClient:
    """Concrete LLMClient. Satisfies the LLMClient Protocol structurally."""

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.llm_model
        self.timeout = timeout or settings.llm_request_timeout

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        payload = {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": (
                temperature if temperature is not None else settings.llm_temperature
            ),
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        url = f"{self.base_url}/v1/chat/completions"
        usage: Usage | None = None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "replace")
                        log.error("LLM error %s: %s", resp.status_code, body[:500])
                        raise LLMBackendError(
                            f"LLM backend returned {resp.status_code}: {body[:300]}"
                        )

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        if event.get("usage"):
                            u = event["usage"]
                            usage = Usage(
                                prompt_tokens=u.get("prompt_tokens"),
                                completion_tokens=u.get("completion_tokens"),
                            )

                        for choice in event.get("choices", []):
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                yield StreamChunk(delta=delta)
        except httpx.ConnectError as exc:
            log.warning("LLM server unreachable at %s: %s", self.base_url, exc)
            raise LLMBackendError(
                f"Can't reach a local LLM at {self.base_url}. Start one and try "
                f"again - e.g. run `ollama serve` and `ollama pull "
                f"{self.default_model}`."
            ) from exc
        except httpx.HTTPError as exc:
            log.warning("LLM request failed: %s", exc)
            raise LLMBackendError(f"LLM request failed: {exc}") from exc

        yield StreamChunk(done=True, usage=usage)

    async def list_models(self) -> list[str]:
        url = f"{self.base_url}/v1/models"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        return [m["id"] for m in data.get("data", [])]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/v1/models")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
