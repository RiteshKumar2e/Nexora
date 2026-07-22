"""Application configuration.

Central, typed settings loaded from environment / `.env`. Everything that
varies between environments lives here so no module reads `os.environ`
directly. This is the seam that lets us swap infra (LLM backend, DB, cache)
without touching application logic.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "Nexora"
    environment: str = "development"
    log_level: str = "INFO"
    # NoDecode: skip pydantic-settings' JSON parsing so the validator below can
    # accept a plain comma-separated string from .env (e.g. "a.com,b.com").
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://nexora:nexora@localhost:5432/nexora"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT Auth ---
    jwt_secret_key: str = "dev-only-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- LLM backend selection ---
    # "nano"   -> run OUR OWN from-scratch model (nano-llm) in-process.
    # "ollama" -> use a local Ollama / OpenAI-compatible server instead.
    # "groq"   -> use the hosted Groq API with multi-key + multi-model fallback.
    # "hybrid" -> try the native model first; if its answer fails a quality gate,
    #             auto-switch to Groq so the user always gets a proper answer.
    llm_backend: str = "nano"

    # --- Hybrid quality gate (only used when llm_backend=hybrid) ---
    hybrid_min_chars: int = 24
    hybrid_min_words: int = 5
    hybrid_min_unique_ratio: float = 0.5
    hybrid_max_stopword_ratio: float = 0.6

    # --- Groq (hosted API; only used when llm_backend=groq) ---
    # Multiple keys: when one is rate-limited/exhausted, the client rotates to the
    # next. Set in .env as a comma-separated list: GROQ_API_KEYS=key1,key2
    groq_api_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Optional explicit model fallback order (comma-separated). Empty => the
    # client auto-discovers Groq's available chat models, ranked best-first.
    groq_models: Annotated[list[str], NoDecode] = Field(default_factory=list)
    groq_temperature: float = 0.7
    groq_max_tokens: int = 2048
    groq_request_timeout: int = 120
    # If every Groq key+model fails, fall back to the local nano-llm so the
    # assistant never goes fully down.
    groq_fallback_to_nano: bool = True

    # --- Own model (nano-llm) ---
    # Path to the nano-llm project; empty auto-detects the sibling ../nano-llm.
    nano_llm_dir: str = ""
    # Chat/instruction model from the two-stage upgrade (role-token format).
    nano_llm_checkpoint: str = "artifacts/chat/ckpt_chat.pt"
    nano_llm_tokenizer: str = "artifacts/tokenizer_chat.json"
    # Use the role-based chat format + chat decoding controls at inference.
    nano_llm_chat_format: bool = True
    nano_llm_max_new_tokens: int = 160
    nano_llm_temperature: float = 0.7
    nano_llm_top_k: int = 40

    # --- Ollama / OpenAI-compatible server (only used when llm_backend=ollama) ---
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:8b"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_request_timeout: int = 300

    @field_validator("cors_origins", "groq_api_keys", "groq_models", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Accept a comma-separated string from env as a list of trimmed items."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so config is parsed once per process."""
    return Settings()


settings = get_settings()
