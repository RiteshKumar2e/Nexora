"""Inference engine for the Nexora Transformer.

Supports temperature, top-k, top-p, repetition penalty, stop tokens,
and streaming token-by-token generation with KV-cache.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import torch
import torch.nn.functional as F

from nexora_model.config import NexoraModelConfig
from nexora_model.tokenizer import NexoraTokenizer
from nexora_model.transformer import NexoraTransformer


@dataclass
class GenerationConfig:
    """Parameters controlling text generation."""
    max_new_tokens: int = 256
    temperature: float = 0.75
    top_k: int = 40
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    min_new_tokens: int = 1
    no_repeat_ngram_size: int = 3
    stop_token_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_model_config(cls, cfg: NexoraModelConfig) -> "GenerationConfig":
        return cls(
            max_new_tokens=cfg.max_new_tokens,
            temperature=cfg.temperature,
            top_k=cfg.top_k,
            top_p=cfg.top_p,
            repetition_penalty=cfg.repetition_penalty,
            stop_token_ids=[cfg.eos_token_id],
        )


def _apply_repetition_penalty(
    logits: torch.Tensor,
    generated_ids: list[int],
    penalty: float,
) -> torch.Tensor:
    """Penalize tokens that have already appeared."""
    if penalty == 1.0 or not generated_ids:
        return logits
    unique_ids = set(generated_ids)
    for token_id in unique_ids:
        if logits[token_id] > 0:
            logits[token_id] /= penalty
        else:
            logits[token_id] *= penalty
    return logits


def _apply_no_repeat_ngram(
    logits: torch.Tensor,
    generated_ids: list[int],
    ngram_size: int,
) -> torch.Tensor:
    """Block n-grams that have already appeared."""
    if ngram_size < 1 or len(generated_ids) < ngram_size:
        return logits
    # Check what next token would complete an already-seen n-gram
    for i in range(len(generated_ids) - ngram_size + 1):
        ngram = tuple(generated_ids[i : i + ngram_size - 1])
        tail = tuple(generated_ids[-(ngram_size - 1) :])
        if ngram == tail:
            banned_id = generated_ids[i + ngram_size - 1]
            logits[banned_id] = float("-inf")
    return logits


def _top_k_top_p_filter(
    logits: torch.Tensor,
    top_k: int,
    top_p: float,
) -> torch.Tensor:
    """Apply top-k and top-p (nucleus) filtering."""
    if top_k > 0:
        top_k = min(top_k, logits.size(-1))
        values, _ = torch.topk(logits, top_k)
        min_val = values[-1]
        logits = logits.masked_fill(logits < min_val, float("-inf"))

    if top_p < 1.0:
        sorted_logits, sorted_indices = torch.sort(logits, descending=True)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
        sorted_mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) >= top_p
        sorted_logits[sorted_mask] = float("-inf")
        logits = sorted_logits.scatter(0, sorted_indices, sorted_logits)

    return logits


class NexoraGenerator:
    """Manages model loading and text generation."""

    def __init__(
        self,
        model: NexoraTransformer,
        tokenizer: NexoraTokenizer,
        device: str = "cpu",
    ):
        self.model = model.to(device).eval()
        self.tokenizer = tokenizer
        self.device = device

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str,
        tokenizer_path: str,
        device: str = "cpu",
    ) -> "NexoraGenerator":
        """Load a trained model from checkpoint."""
        tokenizer = NexoraTokenizer.load(tokenizer_path)

        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        config_data = checkpoint.get("config", {})
        config = NexoraModelConfig(**config_data)
        config.vocab_size = tokenizer.vocab_size

        model = NexoraTransformer(config)
        model.load_state_dict(checkpoint["model_state_dict"], strict=False)

        return cls(model=model, tokenizer=tokenizer, device=device)

    @torch.no_grad()
    def generate(
        self,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> str:
        """Generate text from a prompt (non-streaming)."""
        tokens = list(self.stream(prompt, config))
        return "".join(tokens)

    @torch.no_grad()
    def stream(
        self,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> Iterator[str]:
        """Stream generated tokens one at a time."""
        if config is None:
            config = GenerationConfig.from_model_config(self.model.config)

        input_ids = self.tokenizer.encode(prompt, add_bos=True)
        # Keep within the model's positional capacity (RoPE table). Drop the
        # oldest tokens if the prompt is longer than the context window.
        input_ids = input_ids[-self.model.config.max_seq_len:]
        ids = torch.tensor([input_ids], dtype=torch.long, device=self.device)
        generated: list[int] = []

        # Initialize KV caches
        kv_caches: list[tuple[torch.Tensor, torch.Tensor] | None] = [None] * len(self.model.layers)

        # First forward pass with full context
        result = self.model(ids, kv_caches=kv_caches)
        logits = result["logits"][:, -1, :]
        kv_caches = result["kv_caches"]

        for step in range(config.max_new_tokens):
            logits_flat = logits.squeeze(0)

            # Apply repetition penalty
            logits_flat = _apply_repetition_penalty(
                logits_flat, input_ids + generated, config.repetition_penalty
            )

            # Apply no-repeat n-gram blocking
            logits_flat = _apply_no_repeat_ngram(
                logits_flat, generated, config.no_repeat_ngram_size
            )

            # Temperature
            if config.temperature > 0:
                logits_flat = logits_flat / config.temperature
            else:
                # Greedy
                next_id = logits_flat.argmax().item()
                generated.append(next_id)
                if next_id in config.stop_token_ids and step >= config.min_new_tokens:
                    break
                token_text = self.tokenizer.decode([next_id], skip_special=True)
                if token_text:
                    yield token_text
                ids = torch.tensor([[next_id]], dtype=torch.long, device=self.device)
                result = self.model(ids, kv_caches=kv_caches)
                logits = result["logits"][:, -1, :]
                kv_caches = result["kv_caches"]
                continue

            # Top-k / top-p filtering
            logits_flat = _top_k_top_p_filter(logits_flat, config.top_k, config.top_p)

            # Sample
            probs = F.softmax(logits_flat, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1).item()
            generated.append(next_id)

            # Stop conditions
            if next_id in config.stop_token_ids and step >= config.min_new_tokens:
                break

            # Yield decoded token
            token_text = self.tokenizer.decode([next_id], skip_special=True)
            if token_text:
                yield token_text

            # Next step with KV cache
            ids = torch.tensor([[next_id]], dtype=torch.long, device=self.device)
            result = self.model(ids, kv_caches=kv_caches)
            logits = result["logits"][:, -1, :]
            kv_caches = result["kv_caches"]

    @torch.no_grad()
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        config: GenerationConfig | None = None,
    ) -> Iterator[str]:
        """Stream chat completion from a list of messages."""
        if config is None:
            config = GenerationConfig.from_model_config(self.model.config)

        input_ids = self.tokenizer.encode_chat(messages, add_generation_prompt=True)
        # Keep within the model's positional capacity (RoPE table). Drop the
        # oldest tokens if the chat context exceeds the window.
        input_ids = input_ids[-self.model.config.max_seq_len:]
        ids = torch.tensor([input_ids], dtype=torch.long, device=self.device)
        generated: list[int] = []

        kv_caches: list[tuple[torch.Tensor, torch.Tensor] | None] = [None] * len(self.model.layers)

        result = self.model(ids, kv_caches=kv_caches)
        logits = result["logits"][:, -1, :]
        kv_caches = result["kv_caches"]

        for step in range(config.max_new_tokens):
            logits_flat = logits.squeeze(0)
            logits_flat = _apply_repetition_penalty(
                logits_flat, input_ids + generated, config.repetition_penalty
            )
            logits_flat = _apply_no_repeat_ngram(
                logits_flat, generated, config.no_repeat_ngram_size
            )

            if config.temperature > 0:
                logits_flat = logits_flat / config.temperature
                logits_flat = _top_k_top_p_filter(logits_flat, config.top_k, config.top_p)
                probs = F.softmax(logits_flat, dim=-1)
                next_id = torch.multinomial(probs, num_samples=1).item()
            else:
                next_id = logits_flat.argmax().item()

            generated.append(next_id)

            # Check for stop tokens (EOS, or other role tokens indicating model should stop)
            stop_ids = set(config.stop_token_ids)
            stop_ids.add(self.tokenizer.special_tokens.get("<|eos|>", 2))
            stop_ids.add(self.tokenizer.special_tokens.get("<|user|>", 5))

            if next_id in stop_ids and step >= config.min_new_tokens:
                break

            token_text = self.tokenizer.decode([next_id], skip_special=True)
            if token_text:
                yield token_text

            ids = torch.tensor([[next_id]], dtype=torch.long, device=self.device)
            result = self.model(ids, kv_caches=kv_caches)
            logits = result["logits"][:, -1, :]
            kv_caches = result["kv_caches"]

    def model_info(self) -> dict:
        """Return model metadata."""
        return {
            "name": "nexora-native",
            "parameters": self.num_parameters_str,
            "vocab_size": self.tokenizer.vocab_size,
            "d_model": self.model.config.d_model,
            "n_layers": self.model.config.n_layers,
            "n_heads": self.model.config.n_heads,
            "max_seq_len": self.model.config.max_seq_len,
            "device": str(self.device),
        }

    @property
    def num_parameters_str(self) -> str:
        n = self.model.num_parameters
        if n >= 1e9:
            return f"{n / 1e9:.1f}B"
        if n >= 1e6:
            return f"{n / 1e6:.1f}M"
        if n >= 1e3:
            return f"{n / 1e3:.1f}K"
        return str(n)
