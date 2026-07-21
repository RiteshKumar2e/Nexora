"""LLM provider interface.

Every model backend (Ollama, vLLM, SGLang, llama.cpp-server) implements this
Protocol. Application code depends ONLY on this abstraction, never on a
concrete client — that is what lets a user switch models/backends without any
change to routes, agents, or the RAG pipeline.

All supported backends speak the OpenAI chat-completions schema, so the
interface mirrors it closely while staying provider-neutral.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(slots=True)
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(slots=True)
class StreamChunk:
    """A single streamed event.

    `delta` carries incremental text. When `done` is True the stream is
    complete and `usage` may be populated.
    """
    delta: str = ""
    done: bool = False
    usage: Usage | None = None


@runtime_checkable
class LLMClient(Protocol):
    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunks as the model generates. Must end with done=True."""
        ...

    async def list_models(self) -> list[str]:
        """Return locally available model identifiers."""
        ...

    async def health(self) -> bool:
        """True if the backend is reachable and ready to serve."""
        ...
