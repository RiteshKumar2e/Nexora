"""Groq backend with multi-key + multi-model fallback (never-stop streaming).

Groq exposes an OpenAI-compatible API. This client makes the assistant resilient:

  * **Multiple API keys** — when a key is rate-limited or out of quota (HTTP 429 /
    quota errors), it rotates to the next key automatically.
  * **Multiple models** — it tries a ranked list of Groq chat models best-first;
    if a model is unavailable/decommissioned/overloaded it falls through to the
    next one. The list is auto-discovered from Groq's `/models` endpoint (ranked
    by a built-in preference order) unless `GROQ_MODELS` overrides it.
  * **Local last resort** — if *every* key+model combination fails and
    `groq_fallback_to_nano` is on, it falls back to our own in-process nano-llm
    so the user still gets a reply.

Fallback happens **before the first token** is streamed: Groq returns 429/4xx/5xx
as an immediate response status, so we can switch combos without having emitted
partial output. Once tokens start flowing, we commit to that stream.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import ChatMessage, StreamChunk, Usage
from app.llm.ollama_client import LLMBackendError

log = get_logger("llm.groq")

# Preference order (best -> smaller/faster) for ranking discovered models. Names
# are matched by substring, so minor id changes still rank sensibly. Anything
# discovered but not listed here is appended after these, still usable.
_PREFERENCE: tuple[str, ...] = (
    "kimi-k2",
    "gpt-oss-120b",
    "llama-3.3-70b",
    "llama-4-maverick",
    "llama-4-scout",
    "deepseek-r1-distill-llama-70b",
    "qwen3-32b",
    "qwen-2.5-32b",
    "gpt-oss-20b",
    "llama3-70b",
    "mistral-saba",
    "gemma2-9b",
    "llama-3.1-8b-instant",
    "llama3-8b",
    "allam-2-7b",
)

# Non-chat models to exclude from the fallback chain (audio, safety, embeddings).
_EXCLUDE = ("whisper", "tts", "guard", "embed", "playai", "distil-whisper")

# Static fallback list used only if /models discovery fails on every key.
_STATIC_MODELS: tuple[str, ...] = (
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "deepseek-r1-distill-llama-70b",
    "gemma2-9b-it",
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
)


def _rank(model_id: str) -> int:
    low = model_id.lower()
    for i, pref in enumerate(_PREFERENCE):
        if pref in low:
            return i
    return len(_PREFERENCE)  # unknown chat models go last, but stay in the chain


def _is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return not any(bad in low for bad in _EXCLUDE)


class GroqClient:
    """Concrete LLMClient for Groq with key + model fallback."""

    def __init__(self) -> None:
        self.base_url = settings.groq_base_url.rstrip("/")
        self.keys: list[str] = [k for k in settings.groq_api_keys if k.strip()]
        self.timeout = settings.groq_request_timeout
        self._models: list[str] | None = list(settings.groq_models) or None
        self._nano = None  # lazily created only if needed as last resort
        if not self.keys:
            log.warning(
                "GROQ_API_KEYS is empty. Set it in .env (comma-separated) to use "
                "the Groq backend."
            )

    # --- model discovery --------------------------------------------------

    async def _discover_models(self) -> list[str]:
        """Return the ranked model fallback chain, discovering from Groq once."""
        if self._models is not None:
            return self._models
        for key in self.keys:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        f"{self.base_url}/models",
                        headers={"Authorization": f"Bearer {key}"},
                    )
                if resp.status_code != 200:
                    continue
                ids = [m["id"] for m in resp.json().get("data", []) if m.get("id")]
                chat = [m for m in ids if _is_chat_model(m)]
                if chat:
                    chat.sort(key=_rank)
                    self._models = chat
                    log.info("Discovered %d Groq chat models: %s",
                             len(chat), ", ".join(chat[:6]) + ("..." if len(chat) > 6 else ""))
                    return self._models
            except httpx.HTTPError as exc:
                log.warning("Groq /models discovery failed on a key: %s", exc)
                continue
        # Discovery failed on every key — use the curated static list.
        self._models = list(_STATIC_MODELS)
        log.warning("Using static Groq model list (discovery unavailable).")
        return self._models

    # --- streaming with fallback -----------------------------------------

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if not self.keys:
            async for chunk in self._nano_fallback(
                messages, temperature, max_tokens,
                reason="no Groq API keys configured",
            ):
                yield chunk
            return

        models = [model] if model else await self._discover_models()
        payload_base = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": (
                temperature if temperature is not None else settings.groq_temperature
            ),
            "max_tokens": max_tokens or settings.groq_max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        url = f"{self.base_url}/chat/completions"
        last_error = "unknown error"

        # Try every (model, key) combination until one starts streaming.
        for mdl in models:
            for ki, key in enumerate(self.keys):
                payload = {**payload_base, "model": mdl}
                headers = {"Authorization": f"Bearer {key}"}
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        async with client.stream(
                            "POST", url, json=payload, headers=headers
                        ) as resp:
                            if resp.status_code != 200:
                                body = (await resp.aread()).decode("utf-8", "replace")
                                last_error = f"{resp.status_code}: {body[:200]}"
                                # 429 => key rate-limited/quota: try next key.
                                # 4xx (model gone/bad) => try next model.
                                # 5xx => overloaded: try next key then model.
                                log.warning(
                                    "Groq %s (model=%s, key #%d) -> trying next",
                                    last_error, mdl, ki + 1,
                                )
                                continue
                            # 200: commit to this stream.
                            log.info("Groq streaming from model=%s (key #%d)", mdl, ki + 1)
                            async for chunk in self._read_stream(resp):
                                yield chunk
                            return
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                    log.warning("Groq request error (model=%s, key #%d): %s",
                                mdl, ki + 1, exc)
                    continue

        # Everything failed — fall back to the local model if allowed.
        async for chunk in self._nano_fallback(
            messages, temperature, max_tokens,
            reason=f"all Groq keys+models failed (last: {last_error})",
        ):
            yield chunk

    async def _read_stream(self, resp: httpx.Response) -> AsyncIterator[StreamChunk]:
        usage: Usage | None = None
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
        yield StreamChunk(done=True, usage=usage)

    # --- local last resort ------------------------------------------------

    async def _nano_fallback(
        self,
        messages: Sequence[ChatMessage],
        temperature: float | None,
        max_tokens: int | None,
        *,
        reason: str,
    ) -> AsyncIterator[StreamChunk]:
        if not settings.groq_fallback_to_nano:
            raise LLMBackendError(f"Groq unavailable and local fallback disabled ({reason}).")
        log.warning("Falling back to local nano-llm: %s", reason)
        if self._nano is None:
            from app.llm.nano_client import NanoLMClient
            self._nano = NanoLMClient()
        async for chunk in self._nano.stream_chat(
            messages, temperature=temperature, max_tokens=max_tokens
        ):
            yield chunk

    # --- interface extras -------------------------------------------------

    async def list_models(self) -> list[str]:
        try:
            return await self._discover_models()
        except Exception:  # noqa: BLE001 - listing must never crash callers
            return list(_STATIC_MODELS)

    async def health(self) -> bool:
        """Reachable if any key can hit /models (or local fallback is on)."""
        for key in self.keys:
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.get(
                        f"{self.base_url}/models",
                        headers={"Authorization": f"Bearer {key}"},
                    )
                if resp.status_code == 200:
                    return True
            except httpx.HTTPError:
                continue
        return settings.groq_fallback_to_nano
