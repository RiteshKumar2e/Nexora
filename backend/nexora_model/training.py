"""Training loops for the Nexora model.

Supports:
- General pretraining
- Instruction tuning with assistant-only loss masking
- Checkpointing and resume
- Metrics logging (loss, learning rate, tokens/sec)
- Validation evaluation
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from nexora_model.config import NexoraModelConfig
from nexora_model.transformer import NexoraTransformer


@dataclass
class TrainingMetrics:
    """A single training step's metrics."""
    step: int
    epoch: float
    train_loss: float
    val_loss: float | None = None
    learning_rate: float = 0.0
    tokens_per_sec: float = 0.0
    steps_per_sec: float = 0.0
    total_tokens: int = 0
    elapsed_sec: float = 0.0


@dataclass
class TrainingState:
    """Full state for save/resume."""
    step: int = 0
    epoch: int = 0
    best_val_loss: float = float("inf")
    metrics_history: list[dict] = field(default_factory=list)


def get_lr(step: int, config: NexoraModelConfig) -> float:
    """Linear warmup + cosine decay learning rate schedule."""
    if step < config.warmup_steps:
        return config.learning_rate * (step + 1) / config.warmup_steps
    progress = (step - config.warmup_steps) / max(1, config.max_steps - config.warmup_steps)
    return config.learning_rate * 0.5 * (1.0 + math.cos(math.pi * progress))


class NexoraTrainer:
    """Handles the full training lifecycle."""

    def __init__(
        self,
        model: NexoraTransformer,
        config: NexoraModelConfig,
        train_loader: DataLoader,
        val_loader: DataLoader | None = None,
        device: str = "cpu",
        output_dir: str = "checkpoints",
        log_callback=None,
    ):
        self.model = model.to(device)
        self.config = config
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_callback = log_callback

        self.optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay,
            betas=(0.9, 0.95),
        )
        self.state = TrainingState()
        self._stop_requested = False

    def train(self) -> TrainingState:
        """Run the full training loop."""
        self.model.train()
        step = self.state.step
        total_tokens = 0
        start_time = time.time()
        running_loss = 0.0
        loss_count = 0

        data_iter = iter(self.train_loader)

        while step < self.config.max_steps and not self._stop_requested:
            # Get next batch (cycle through epochs)
            try:
                batch = next(data_iter)
            except StopIteration:
                self.state.epoch += 1
                data_iter = iter(self.train_loader)
                batch = next(data_iter)

            # Learning rate scheduling
            lr = get_lr(step, self.config)
            for pg in self.optimizer.param_groups:
                pg["lr"] = lr

            # Forward pass
            input_ids = batch["input_ids"].to(self.device)
            labels = batch["labels"].to(self.device)
            loss_mask = batch.get("loss_mask")
            if loss_mask is not None:
                loss_mask = loss_mask.to(self.device)

            result = self.model(input_ids, labels=labels, loss_mask=loss_mask)
            loss = result["loss"]

            # Backward pass
            loss.backward()

            # Gradient clipping
            nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)

            self.optimizer.step()
            self.optimizer.zero_grad()

            # Track metrics
            batch_tokens = input_ids.numel()
            total_tokens += batch_tokens
            running_loss += loss.item()
            loss_count += 1
            step += 1
            self.state.step = step

            elapsed = time.time() - start_time

            # Logging
            if step % 10 == 0 or step == 1:
                avg_loss = running_loss / loss_count
                metrics = TrainingMetrics(
                    step=step,
                    epoch=self.state.epoch + (step % len(self.train_loader)) / len(self.train_loader),
                    train_loss=avg_loss,
                    learning_rate=lr,
                    tokens_per_sec=total_tokens / max(elapsed, 1),
                    steps_per_sec=step / max(elapsed, 1),
                    total_tokens=total_tokens,
                    elapsed_sec=elapsed,
                )

                if self.log_callback:
                    self.log_callback(metrics)
                else:
                    self._default_log(metrics)

                running_loss = 0.0
                loss_count = 0

            # Validation
            if step % self.config.eval_interval == 0 and self.val_loader is not None:
                val_loss = self.evaluate()
                metrics = TrainingMetrics(
                    step=step,
                    epoch=self.state.epoch,
                    train_loss=loss.item(),
                    val_loss=val_loss,
                    learning_rate=lr,
                    total_tokens=total_tokens,
                    elapsed_sec=elapsed,
                )
                self.state.metrics_history.append(asdict(metrics))

                if val_loss < self.state.best_val_loss:
                    self.state.best_val_loss = val_loss
                    self.save_checkpoint("best")

                if self.log_callback:
                    self.log_callback(metrics)

            # Checkpointing
            if step % self.config.save_interval == 0:
                self.save_checkpoint(f"step_{step}")

        # Final save
        self.save_checkpoint("final")
        self._save_metrics()
        return self.state

    @torch.no_grad()
    def evaluate(self) -> float:
        """Compute average validation loss."""
        self.model.eval()
        total_loss = 0.0
        count = 0

        for batch in self.val_loader:
            input_ids = batch["input_ids"].to(self.device)
            labels = batch["labels"].to(self.device)
            loss_mask = batch.get("loss_mask")
            if loss_mask is not None:
                loss_mask = loss_mask.to(self.device)

            result = self.model(input_ids, labels=labels, loss_mask=loss_mask)
            total_loss += result["loss"].item()
            count += 1

        self.model.train()
        return total_loss / max(count, 1)

    def save_checkpoint(self, name: str) -> Path:
        """Save model checkpoint with config and training state."""
        path = self.output_dir / f"ckpt_{name}.pt"
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "config": {
                    k: v for k, v in asdict(self.config).items()
                    if not callable(v)
                },
                "training_state": asdict(self.state),
            },
            path,
        )
        return path

    def load_checkpoint(self, path: str | Path) -> None:
        """Resume training from a checkpoint."""
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        if "optimizer_state_dict" in checkpoint:
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        if "training_state" in checkpoint:
            state_data = checkpoint["training_state"]
            self.state = TrainingState(**state_data)

    def stop(self) -> None:
        """Request training to stop after the current step."""
        self._stop_requested = True

    def _save_metrics(self) -> None:
        """Save metrics history to JSON."""
        path = self.output_dir / "metrics.json"
        with open(path, "w") as f:
            json.dump(self.state.metrics_history, f, indent=2)

    def _default_log(self, m: TrainingMetrics) -> None:
        parts = [f"step {m.step}/{self.config.max_steps}"]
        parts.append(f"loss={m.train_loss:.4f}")
        if m.val_loss is not None:
            parts.append(f"val_loss={m.val_loss:.4f}")
        parts.append(f"lr={m.learning_rate:.2e}")
        parts.append(f"tok/s={m.tokens_per_sec:.0f}")
        print(" | ".join(parts))
