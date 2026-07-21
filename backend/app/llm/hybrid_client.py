"""Hybrid backend: try the native nano-llm first, fall back to Groq on low quality.

Flow per turn:
  1. If the native model is loaded AND trained, generate its answer in full.
  2. Run a lightweight quality gate on that answer (length, repetition, no role-
     token leakage, enough distinct words).
  3. If it passes -> stream the native answer (Nexora's own model answered).
     If it fails (or the native model is untrained/unavailable) -> stream from
     Groq instead, so the user always gets a proper answer.

Honest limits: the gate checks *coherence/quality signals*, not factual
correctness — a tiny model can't be verified for truth cheaply. In practice an
untrained/weak native model rarely passes, so the user gets Groq's answer while
the native model is still attempted first (and improves via training + feedback).
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import ChatMessage, StreamChunk

log = get_logger("llm.hybrid")

_LEAK = ("<|", "|>")


def looks_proper(text: str) -> bool:
    """Heuristic quality gate for a native-model answer."""
    t = (text or "").strip()
    if len(t) < settings.hybrid_min_chars:
        return False
    words = t.split()
    if len(words) < settings.hybrid_min_words:
        return False
    # Too repetitive (few distinct words) => low quality.
    uniq_ratio = len(set(w.lower() for w in words)) / len(words)
    if uniq_ratio < settings.hybrid_min_unique_ratio:
        return False
    # Role/special tokens must never leak into a shown answer.
    if any(m in t for m in _LEAK):
        return False
    # A single token dominating the output => degenerate loop.
    from collections import Counter
    most = Counter(w.lower() for w in words).most_common(1)[0][1]
    if most / len(words) > 0.4:
        return False
    return True


def _word_chunks(text: str):
    """Re-emit a completed native answer as small deltas for a streaming feel."""
    buf = ""
    for word in text.split(" "):
        buf = word if not buf else f"{buf} {word}"
        if len(buf) >= 24:
            yield buf + " "
            buf = ""
    if buf:
        yield buf


class HybridClient:
    """Native-first, Groq-fallback LLM client. Satisfies LLMClient."""

    def __init__(self) -> None:
        from app.llm.groq_client import GroqClient
        from app.llm.nano_client import NanoLMClient

        self.nano = NanoLMClient()
        self.groq = GroqClient()

    def _nano_ready(self) -> bool:
        info = self.nano.get_model_info() if hasattr(self.nano, "get_model_info") else {}
        return self.nano._generator is not None and bool(info.get("trained"))

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        # 1. Try the native model (only if it's actually trained).
        if self._nano_ready():
            native_text = ""
            try:
                async for ch in self.nano.stream_chat(
                    messages, temperature=temperature, max_tokens=max_tokens
                ):
                    if ch.delta:
                        native_text += ch.delta
            except Exception as exc:  # noqa: BLE001 — never let native errors kill the turn
                log.warning("native model failed, using Groq: %s", exc)
                native_text = ""

            if looks_proper(native_text):
                log.info("hybrid: native model answered (%d chars)", len(native_text))
                for delta in _word_chunks(native_text):
                    yield StreamChunk(delta=delta)
                yield StreamChunk(done=True, usage=None)
                return
            log.info("hybrid: native answer rejected -> falling back to Groq")

        # 2. Fall back to Groq for a proper answer.
        async for ch in self.groq.stream_chat(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        ):
            yield ch

    async def list_models(self) -> list[str]:
        return ["nexora-native", *(await self.groq.list_models())]

    async def health(self) -> bool:
        return (await self.groq.health()) or (self.nano._generator is not None)
