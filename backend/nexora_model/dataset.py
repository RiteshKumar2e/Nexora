"""Dataset utilities for training the Nexora model.

Loads instruction-tuning data, applies tokenization, creates train/val/test
splits, and provides a DataLoader-compatible dataset.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import Dataset

from nexora_model.tokenizer import NexoraTokenizer


@dataclass
class DatasetStats:
    """Statistics about a loaded dataset."""
    total_examples: int
    train_examples: int
    val_examples: int
    test_examples: int
    categories: dict[str, int]
    total_tokens: int
    avg_tokens_per_example: float


class InstructionDataset(Dataset):
    """PyTorch dataset for instruction-tuning data.

    Each item is a dict with 'input_ids', 'labels', and 'loss_mask'.
    Loss is computed only on assistant tokens.
    """

    def __init__(
        self,
        examples: list[dict],
        tokenizer: NexoraTokenizer,
        max_len: int = 256,
        mask_system_user: bool = True,
    ):
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.mask_system_user = mask_system_user
        self.data: list[dict[str, torch.Tensor]] = []

        for ex in examples:
            encoded = self._encode_example(ex)
            if encoded is not None:
                self.data.append(encoded)

    def _encode_example(self, example: dict) -> dict[str, torch.Tensor] | None:
        """Encode a single instruction example with loss masking."""
        messages = []
        if example.get("system"):
            messages.append({"role": "system", "content": example["system"]})
        messages.append({"role": "user", "content": example["user"]})
        messages.append({"role": "assistant", "content": example["assistant"]})

        # Full sequence with BOS + role tokens + content + EOS
        full_ids = self.tokenizer.encode_chat(messages)

        if len(full_ids) > self.max_len:
            full_ids = full_ids[: self.max_len]
        if len(full_ids) < 4:  # too short to be useful
            return None

        # Create loss mask: 1 for assistant tokens, 0 for system/user tokens
        loss_mask = [0] * len(full_ids)

        if self.mask_system_user:
            # Find where assistant content starts
            assistant_token_id = self.tokenizer.special_tokens.get("<|assistant|>", 6)
            in_assistant = False
            for i, tid in enumerate(full_ids):
                if tid == assistant_token_id:
                    in_assistant = True
                    continue
                if in_assistant:
                    loss_mask[i] = 1
        else:
            loss_mask = [1] * len(full_ids)

        # Pad to max_len
        pad_len = self.max_len - len(full_ids)
        pad_id = self.tokenizer.special_tokens.get("<|pad|>", 0)
        full_ids = full_ids + [pad_id] * pad_len
        loss_mask = loss_mask + [0] * pad_len

        return {
            "input_ids": torch.tensor(full_ids, dtype=torch.long),
            "labels": torch.tensor(full_ids, dtype=torch.long),
            "loss_mask": torch.tensor(loss_mask, dtype=torch.float),
        }

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return self.data[idx]


class PretrainingDataset(Dataset):
    """Dataset for general language pretraining (all tokens contribute to loss)."""

    def __init__(
        self,
        texts: list[str],
        tokenizer: NexoraTokenizer,
        max_len: int = 256,
    ):
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.data: list[torch.Tensor] = []

        # Concatenate all text and chunk into fixed-length sequences
        all_ids: list[int] = []
        for text in texts:
            ids = tokenizer.encode(text, add_bos=True, add_eos=True)
            all_ids.extend(ids)

        for i in range(0, len(all_ids) - max_len, max_len):
            chunk = all_ids[i : i + max_len]
            self.data.append(torch.tensor(chunk, dtype=torch.long))

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        ids = self.data[idx]
        return {"input_ids": ids, "labels": ids}


def load_instruction_data(
    path: str | Path,
    *,
    train_ratio: float = 0.85,
    val_ratio: float = 0.10,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict], DatasetStats]:
    """Load instruction data from JSONL and split into train/val/test.

    Each line should be: {"category": "...", "system": "...", "user": "...", "assistant": "..."}
    """
    path = Path(path)
    examples: list[dict] = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    random.seed(seed)
    random.shuffle(examples)

    n = len(examples)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train = examples[:n_train]
    val = examples[n_train : n_train + n_val]
    test = examples[n_train + n_val :]

    # Category statistics
    categories: dict[str, int] = {}
    for ex in examples:
        cat = ex.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    # Token estimate
    total_chars = sum(
        len(ex.get("system", "")) + len(ex.get("user", "")) + len(ex.get("assistant", ""))
        for ex in examples
    )
    est_tokens = total_chars // 4  # rough estimate

    stats = DatasetStats(
        total_examples=n,
        train_examples=len(train),
        val_examples=len(val),
        test_examples=len(test),
        categories=categories,
        total_tokens=est_tokens,
        avg_tokens_per_example=est_tokens / max(n, 1),
    )

    return train, val, test, stats
