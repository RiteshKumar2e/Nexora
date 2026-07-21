"""Application configuration.

Central, typed settings loaded from environment / `.env`. Everything that
varies between environments lives here so no module reads `os.environ`
directly. This is the seam that lets us swap infra (LLM backend, DB, cache)
without touching application logic.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Database ---
    database_url: str = "postgresql+asyncpg://nexora:nexora@localhost:5432/nexora"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM backend selection ---
    # "nano"   -> run OUR OWN from-scratch model (nano-llm) in-process. No
    #             external server, no third-party API. This is the default.
    # "ollama" -> use a local Ollama / OpenAI-compatible server instead.
    llm_backend: str = "nano"

    # --- Own model (nano-llm) ---
    # Path to the nano-llm project; empty auto-detects the sibling ../nano-llm.
    nano_llm_dir: str = ""
    nano_llm_checkpoint: str = "artifacts/checkpoints_sft/ckpt_best.pt"
    nano_llm_tokenizer: str = "artifacts/tokenizer_stories.json"
    nano_llm_max_new_tokens: int = 160
    nano_llm_temperature: float = 0.8
    nano_llm_top_k: int = 40

    # --- Ollama / OpenAI-compatible server (only used when llm_backend=ollama) ---
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen3:8b"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_request_timeout: int = 300

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        """Accept a comma-separated string from env as a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so config is parsed once per process."""
    return Settings()


settings = get_settings()
