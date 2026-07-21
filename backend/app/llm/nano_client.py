"""In-process LLM backend powered by OUR OWN from-scratch model (nano-llm).

No external server, no third-party API — Nexora loads the model weights we
trained ourselves (the nano-llm project) and generates tokens directly in
Python via nano-llm's KV-cached inference engine. This satisfies the same
`LLMClient` interface as the Ollama backend, so routes/services are unchanged.

Heavy imports (torch + the nano-llm packages) are done lazily inside `_load`, so
importing this module never requires torch to be installed until the model is
actually used.
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import ChatMessage, StreamChunk
from app.llm.ollama_client import LLMBackendError

log = get_logger("llm.nano")

_STOP = object()  # sentinel marking the end of the sync generator


class NanoLMClient:
    """Runs the self-trained nano-llm model in-process. Satisfies LLMClient."""

    def __init__(self) -> None:
        self._service = None
        self._GenParams = None
        self._load_error: str | None = None
        try:
            self._load()
        except Exception as exc:  # keep the app up; report via health()/stream
            self._load_error = str(exc)
            log.warning("nano-llm model not loaded: %s", exc)

    # --- loading -----------------------------------------------------------

    def _resolve_dir(self) -> Path:
        if settings.nano_llm_dir:
            return Path(settings.nano_llm_dir)
        # Sibling of the Nexora repo root, e.g. .../Desktop/nano-llm
        return Path(__file__).resolve().parents[3].parent / "nano-llm"

    def _load(self) -> None:
        nano_dir = self._resolve_dir()
        if not nano_dir.exists():
            raise FileNotFoundError(f"nano-llm project not found at {nano_dir}")
        if str(nano_dir) not in sys.path:
            sys.path.insert(0, str(nano_dir))

        # Lazy: pulls torch + nano-llm packages only now.
        from serving.model_service import GenParams, ModelService

        self._GenParams = GenParams
        ckpt = nano_dir / settings.nano_llm_checkpoint
        tok = nano_dir / settings.nano_llm_tokenizer
        if not ckpt.exists() or not tok.exists():
            raise FileNotFoundError(
                f"nano-llm artifacts missing (checkpoint exists={ckpt.exists()}, "
                f"tokenizer exists={tok.exists()}). Train the model first — see "
                f"nano-llm/README (make all)."
            )

        self._service = ModelService.from_config(
            {
                "checkpoint": str(ckpt),
                "tokenizer": str(tok),
                "device": "cpu",
                "instruction_format": True,
            }
        )
        log.info("Loaded own nano-llm model: %s", self._service.info())

    # --- LLMClient interface ----------------------------------------------

    def _params(self, temperature: float | None, max_tokens: int | None):
        return self._GenParams(
            max_new_tokens=max_tokens or settings.nano_llm_max_new_tokens,
            temperature=(
                temperature if temperature is not None else settings.nano_llm_temperature
            ),
            top_k=settings.nano_llm_top_k,
        )

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if self._service is None:
            raise LLMBackendError(
                f"The local nano-llm model isn't loaded ({self._load_error}). "
                f"Train it in the nano-llm project, then restart."
            )

        # The tiny model is single-turn/instruction-tuned; use the latest user
        # message as the instruction (system/history are ignored by design).
        user_msg = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        if not user_msg.strip() and messages:
            user_msg = messages[-1].content

        gen = self._service.stream(user_msg, self._params(temperature, max_tokens))

        def _next():
            try:
                return next(gen)
            except StopIteration:
                return _STOP

        # Drive the (blocking) sync generator one token at a time off the event
        # loop, so streaming stays responsive.
        while True:
            delta = await asyncio.to_thread(_next)
            if delta is _STOP:
                break
            yield StreamChunk(delta=delta)
        yield StreamChunk(done=True, usage=None)

    async def list_models(self) -> list[str]:
        return ["nano-llm"]

    async def health(self) -> bool:
        return self._service is not None
