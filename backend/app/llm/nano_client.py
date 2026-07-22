"""In-process LLM backend powered by Nexora's own from-scratch model.

No external server, no third-party API — loads the Transformer model we
trained ourselves and generates tokens directly with KV-cached inference.
Satisfies the same LLMClient interface as Ollama/Groq.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import ChatMessage, StreamChunk
from app.llm.ollama_client import LLMBackendError

log = get_logger("llm.nano")

_STOP = object()


class NanoLMClient:
    """Runs Nexora's self-trained model in-process. Satisfies LLMClient."""

    def __init__(self) -> None:
        self._generator = None
        self._load_error: str | None = None
        self._model_info: dict = {}
        try:
            self._load()
        except Exception as exc:
            self._load_error = str(exc)
            log.warning("Nexora native model not loaded: %s", exc)

    def _load(self) -> None:
        import torch
        from nexora_model.config import NexoraModelConfig, CPU_SMALL
        from nexora_model.tokenizer import NexoraTokenizer
        from nexora_model.transformer import NexoraTransformer
        from nexora_model.inference import NexoraGenerator

        # Look for checkpoint in the nexora_model directory
        # Resolve the checkpoints dir from the nexora_model package itself, so it
        # works no matter where this client lives (was wrongly app/nexora_model).
        import nexora_model
        model_dir = Path(nexora_model.__file__).resolve().parent
        ckpt_path = model_dir / "checkpoints" / "ckpt_best.pt"
        tok_path = model_dir / "checkpoints" / "tokenizer.json"

        # Also try alternative locations
        if not ckpt_path.exists():
            ckpt_path = model_dir / "checkpoints" / "ckpt_final.pt"

        if not ckpt_path.exists() or not tok_path.exists():
            # No trained model yet — create an untrained one for demo
            log.info("No trained checkpoint found. Creating untrained model for demonstration.")
            config = CPU_SMALL

            # Try to load tokenizer if it exists
            if tok_path.exists():
                tokenizer = NexoraTokenizer.load(str(tok_path))
                config.vocab_size = tokenizer.vocab_size
            else:
                # Create a minimal tokenizer
                log.info("No tokenizer found. Creating minimal tokenizer.")
                sample_texts = [
                    "Hello! I am Nexora, a helpful AI assistant.",
                    "Machine learning is a branch of artificial intelligence.",
                    "Python is a popular programming language.",
                    "The internet connects computers worldwide.",
                ]
                tokenizer = NexoraTokenizer.train(sample_texts, vocab_size=config.vocab_size)
                tok_path.parent.mkdir(parents=True, exist_ok=True)
                tokenizer.save(str(tok_path))
                config.vocab_size = tokenizer.vocab_size

            model = NexoraTransformer(config)
            self._generator = NexoraGenerator(model=model, tokenizer=tokenizer, device="cpu")
            self._model_info = self._generator.model_info()
            self._model_info["trained"] = False
            log.info(
                "Loaded UNTRAINED Nexora model (%s params). "
                "Train the model for better responses: python -m nexora_model.scripts.train",
                self._generator.num_parameters_str,
            )
            return

        # Load trained model
        self._generator = NexoraGenerator.from_checkpoint(
            checkpoint_path=str(ckpt_path),
            tokenizer_path=str(tok_path),
            device="cpu",
        )
        self._model_info = self._generator.model_info()
        self._model_info["trained"] = True
        log.info("Loaded trained Nexora model: %s", self._model_info)

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if self._generator is None:
            raise LLMBackendError(
                f"The Nexora native model isn't loaded ({self._load_error}). "
                f"Check the nexora_model directory and restart."
            )

        from nexora_model.inference import GenerationConfig

        config = GenerationConfig(
            max_new_tokens=max_tokens or settings.nano_llm_max_new_tokens,
            temperature=temperature if temperature is not None else settings.nano_llm_temperature,
            top_k=settings.nano_llm_top_k,
        )

        # Convert ChatMessage objects to dicts
        msg_dicts = [{"role": m.role, "content": m.content} for m in messages]

        # Run the sync generator in a thread to avoid blocking the event loop
        gen = self._generator.stream_chat(msg_dicts, config)

        def _next():
            try:
                return next(gen)
            except StopIteration:
                return _STOP

        while True:
            delta = await asyncio.to_thread(_next)
            if delta is _STOP:
                break
            yield StreamChunk(delta=delta)

        yield StreamChunk(done=True, usage=None)

    async def list_models(self) -> list[str]:
        return ["nexora-native"]

    async def health(self) -> bool:
        return self._generator is not None

    def get_model_info(self) -> dict:
        return self._model_info
