"""From-scratch Transformer decoder with RMSNorm, Rotary Embeddings, and SwiGLU.

No pretrained weights. No Hugging Face. Every parameter initialized from random.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from nexora_model.config import NexoraModelConfig


# ── RMSNorm ──────────────────────────────────────────────────

class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization (Zhang & Sennrich, 2019)."""

    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.rsqrt(x.float().pow(2).mean(-1, keepdim=True) + self.eps)
        return (x.float() * rms).type_as(x) * self.weight


# ── Rotary Position Embeddings ───────────────────────────────

def _precompute_freqs(dim: int, max_len: int, theta: float = 10000.0) -> torch.Tensor:
    """Precompute complex exponentials for RoPE."""
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
    t = torch.arange(max_len, dtype=torch.float)
    freqs = torch.outer(t, freqs)
    return torch.polar(torch.ones_like(freqs), freqs)  # complex64


def _apply_rotary(x: torch.Tensor, freqs: torch.Tensor, start_pos: int = 0) -> torch.Tensor:
    """Apply rotary embeddings to a query/key tensor at absolute positions.

    x: (B, n_heads, T, d_head). Positions run [start_pos, start_pos + T) — the
    offset matters during KV-cached decoding, where each new token must be
    rotated by its true position in the sequence (not 0). Positions past the
    precomputed table defensively reuse the last row so we never size-mismatch.
    """
    T = x.size(2)
    x_complex = torch.view_as_complex(x.float().reshape(*x.shape[:-1], -1, 2))
    # Absolute positions [start_pos, start_pos + T), clamped into the table so
    # anything beyond the precomputed range reuses the last position instead of
    # producing an empty/mismatched slice.
    pos = torch.arange(start_pos, start_pos + T, device=freqs.device).clamp_(max=freqs.size(0) - 1)
    sl = freqs[pos].unsqueeze(0).unsqueeze(0)  # (1, 1, T, d_head/2)
    out = torch.view_as_real(x_complex * sl).flatten(-2)
    return out.type_as(x)


# ── Multi-Head Causal Self-Attention ─────────────────────────

class CausalSelfAttention(nn.Module):
    def __init__(self, config: NexoraModelConfig):
        super().__init__()
        self.n_heads = config.n_heads
        self.d_head = config.d_head
        self.d_model = config.d_model

        self.q_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.k_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.v_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.o_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.attn_drop = nn.Dropout(config.dropout)

        # Precompute RoPE frequencies
        self.register_buffer(
            "rope_freqs",
            _precompute_freqs(config.d_head, config.max_seq_len * 2, config.rope_theta),
            persistent=False,
        )

    def forward(
        self,
        x: torch.Tensor,
        mask: torch.Tensor | None = None,
        kv_cache: tuple[torch.Tensor, torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        B, T, C = x.shape

        q = self.q_proj(x).view(B, T, self.n_heads, self.d_head).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.n_heads, self.d_head).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.n_heads, self.d_head).transpose(1, 2)

        # Apply RoPE at the correct absolute positions. During cached decoding
        # the new token sits at position = number of cached timesteps.
        start_pos = kv_cache[0].size(2) if kv_cache is not None else 0
        q = _apply_rotary(q, self.rope_freqs, start_pos)
        k = _apply_rotary(k, self.rope_freqs, start_pos)

        # KV cache for efficient inference
        if kv_cache is not None:
            k = torch.cat([kv_cache[0], k], dim=2)
            v = torch.cat([kv_cache[1], v], dim=2)
        new_cache = (k, v)

        # Scaled dot-product attention
        scale = 1.0 / math.sqrt(self.d_head)
        attn = torch.matmul(q, k.transpose(-2, -1)) * scale

        if mask is not None:
            attn = attn.masked_fill(mask == 0, float("-inf"))

        attn = F.softmax(attn, dim=-1)
        attn = self.attn_drop(attn)

        out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(B, T, C)
        out = self.o_proj(out)
        return out, new_cache


# ── SwiGLU Feed-Forward ─────────────────────────────────────

class SwiGLUFFN(nn.Module):
    """SwiGLU activation function (Shazeer, 2020)."""

    def __init__(self, config: NexoraModelConfig):
        super().__init__()
        self.gate = nn.Linear(config.d_model, config.d_ff, bias=False)
        self.up = nn.Linear(config.d_model, config.d_ff, bias=False)
        self.down = nn.Linear(config.d_ff, config.d_model, bias=False)
        self.drop = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.drop(self.down(F.silu(self.gate(x)) * self.up(x)))


# ── Transformer Block ───────────────────────────────────────

class TransformerBlock(nn.Module):
    def __init__(self, config: NexoraModelConfig):
        super().__init__()
        self.attn_norm = RMSNorm(config.d_model)
        self.attn = CausalSelfAttention(config)
        self.ffn_norm = RMSNorm(config.d_model)
        self.ffn = SwiGLUFFN(config)

    def forward(
        self,
        x: torch.Tensor,
        mask: torch.Tensor | None = None,
        kv_cache: tuple[torch.Tensor, torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        h, cache = self.attn(self.attn_norm(x), mask=mask, kv_cache=kv_cache)
        x = x + h
        x = x + self.ffn(self.ffn_norm(x))
        return x, cache


# ── Full Model ───────────────────────────────────────────────

class NexoraTransformer(nn.Module):
    """From-scratch causal language model.

    Architecture:
    - Token embeddings (no learned position — RoPE handles position)
    - N × TransformerBlock (RMSNorm → Attn → RMSNorm → SwiGLU)
    - Final RMSNorm
    - Language model head (tied with embeddings)
    """

    def __init__(self, config: NexoraModelConfig):
        super().__init__()
        self.config = config

        self.token_emb = nn.Embedding(config.vocab_size, config.d_model, padding_idx=config.pad_token_id)
        self.drop = nn.Dropout(config.dropout)
        self.layers = nn.ModuleList([TransformerBlock(config) for _ in range(config.n_layers)])
        self.norm = RMSNorm(config.d_model)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)

        # Weight tying
        self.lm_head.weight = self.token_emb.weight

        # Initialize weights
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.padding_idx is not None:
                module.weight.data[module.padding_idx].zero_()

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: torch.Tensor | None = None,
        loss_mask: torch.Tensor | None = None,
        kv_caches: list[tuple[torch.Tensor, torch.Tensor]] | None = None,
    ) -> dict[str, torch.Tensor]:
        """
        Args:
            input_ids: (B, T) token IDs
            labels: (B, T) target IDs for loss computation
            loss_mask: (B, T) binary mask — 1 = compute loss, 0 = ignore
            kv_caches: list of (K, V) per layer for cached inference

        Returns:
            dict with 'logits' and optionally 'loss'
        """
        B, T = input_ids.shape
        device = input_ids.device

        x = self.drop(self.token_emb(input_ids))

        # Causal mask
        if kv_caches is not None and kv_caches[0] is not None:
            # During cached generation, only the new token(s) attend to all past
            mask = None
        else:
            mask = torch.tril(torch.ones(T, T, device=device, dtype=torch.bool))
            mask = mask.unsqueeze(0).unsqueeze(0)  # (1, 1, T, T)

        new_caches: list[tuple[torch.Tensor, torch.Tensor]] = []
        for i, layer in enumerate(self.layers):
            cache = kv_caches[i] if kv_caches is not None else None
            x, new_cache = layer(x, mask=mask, kv_cache=cache)
            new_caches.append(new_cache)

        x = self.norm(x)
        logits = self.lm_head(x)

        result: dict[str, torch.Tensor] = {"logits": logits, "kv_caches": new_caches}

        if labels is not None:
            # Shift so token i predicts token i+1
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = labels[:, 1:].contiguous()

            loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=self.config.pad_token_id,
                reduction="none",
            )

            if loss_mask is not None:
                shift_mask = loss_mask[:, 1:].contiguous().view(-1)
                loss = (loss * shift_mask).sum() / shift_mask.sum().clamp(min=1)
            else:
                valid = shift_labels.view(-1) != self.config.pad_token_id
                loss = loss[valid].mean()

            result["loss"] = loss

        return result

    @property
    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())

    @property
    def num_trainable_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
