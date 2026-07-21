"""Model configuration with presets for CPU and GPU training."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NexoraModelConfig:
    """All hyperparameters for the Nexora Transformer."""

    # Vocabulary
    vocab_size: int = 8000
    pad_token_id: int = 0
    bos_token_id: int = 1
    eos_token_id: int = 2

    # Architecture
    d_model: int = 256
    n_layers: int = 6
    n_heads: int = 8
    d_ff: int = 1024          # SwiGLU intermediate size
    max_seq_len: int = 256
    dropout: float = 0.1
    rope_theta: float = 10000.0

    # Training
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    warmup_steps: int = 200
    max_steps: int = 5000
    batch_size: int = 16
    grad_accum_steps: int = 1
    eval_interval: int = 250
    save_interval: int = 500
    max_grad_norm: float = 1.0

    # Generation defaults
    temperature: float = 0.75
    top_k: int = 40
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    max_new_tokens: int = 256

    @property
    def d_head(self) -> int:
        return self.d_model // self.n_heads

    @property
    def param_count_millions(self) -> float:
        """Rough parameter count estimate (millions)."""
        embed = self.vocab_size * self.d_model
        attn = self.n_layers * (4 * self.d_model * self.d_model)  # Q,K,V,O
        ffn = self.n_layers * (3 * self.d_model * self.d_ff)      # SwiGLU: gate, up, down
        norm = self.n_layers * 2 * self.d_model                   # 2 norms per layer
        head = self.d_model * self.vocab_size                     # lm_head
        return (embed + attn + ffn + norm + head) / 1e6


# ── Presets ──────────────────────────────────────────────────

CPU_SMALL = NexoraModelConfig(
    vocab_size=8000,
    d_model=256,
    n_layers=6,
    n_heads=8,
    d_ff=1024,
    max_seq_len=256,
    batch_size=8,
    max_steps=5000,
)

GPU_MEDIUM = NexoraModelConfig(
    vocab_size=16000,
    d_model=512,
    n_layers=12,
    n_heads=8,
    d_ff=2048,
    max_seq_len=1024,
    batch_size=32,
    max_steps=20000,
    learning_rate=2e-4,
)

PRESETS = {
    "cpu_small": CPU_SMALL,
    "gpu_medium": GPU_MEDIUM,
}
