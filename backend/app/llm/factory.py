"""LLM client factory / provider selection.

A single place that decides which concrete backend to instantiate. Add a new
backend by branching here; nothing else in the app needs to know.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.llm.base import LLMClient
from app.llm.ollama_client import OllamaClient


@lru_cache
def get_llm_client() -> LLMClient:
    """Select the LLM backend from config.

    Default is our OWN from-scratch model (nano-llm), run in-process with no
    external server. Set `llm_backend=ollama` to use a local OpenAI-compatible
    server instead (covers Ollama / vLLM / SGLang / llama.cpp).
    """
    if settings.llm_backend.lower() == "ollama":
        return OllamaClient()
    # Imported lazily so the app doesn't require torch unless this backend runs.
    from app.llm.nano_client import NanoLMClient

    return NanoLMClient()
