"""Byte-Pair Encoding tokenizer trained from scratch.

No Hugging Face, SentencePiece, or tiktoken — built entirely in Python.
Supports special role tokens for the chat format.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Sequence


# ── Special Tokens ───────────────────────────────────────────

SPECIAL_TOKENS = {
    "<|pad|>": 0,
    "<|bos|>": 1,
    "<|eos|>": 2,
    "<|unk|>": 3,
    "<|system|>": 4,
    "<|user|>": 5,
    "<|assistant|>": 6,
}

# Pre-tokenization regex: split on whitespace boundaries, punctuation, digits
_SPLIT_RE = re.compile(
    r"""'s|'t|'re|'ve|'m|'ll|'d"""
    r"""| ?\w+"""
    r"""| ?\d+"""
    r"""| ?[^\s\w]+"""
    r"""|\s+""",
    re.UNICODE,
)


class NexoraTokenizer:
    """Minimal BPE tokenizer built from scratch."""

    def __init__(
        self,
        merges: list[tuple[str, str]] | None = None,
        vocab: dict[str, int] | None = None,
    ):
        self.special_tokens = dict(SPECIAL_TOKENS)
        self.merges: list[tuple[str, str]] = merges or []
        self.vocab: dict[str, int] = vocab or {}
        self.id_to_token: dict[int, str] = {}
        if self.vocab:
            self.id_to_token = {v: k for k, v in self.vocab.items()}
        self._merge_ranks: dict[tuple[str, str], int] = {}
        if self.merges:
            self._merge_ranks = {m: i for i, m in enumerate(self.merges)}

    # ── Training ─────────────────────────────────────────────

    @classmethod
    def train(cls, texts: Sequence[str], vocab_size: int = 8000) -> "NexoraTokenizer":
        """Train a BPE tokenizer from a list of text strings."""
        # Start with byte-level base vocabulary
        base_vocab_size = 256 + len(SPECIAL_TOKENS)
        num_merges = max(0, vocab_size - base_vocab_size)

        # Collect word frequencies via pre-tokenization
        word_freqs: Counter[tuple[str, ...]] = Counter()
        for text in texts:
            tokens = _SPLIT_RE.findall(text)
            for token in tokens:
                # Represent each character as its own unit
                chars = tuple(token)
                if chars:
                    word_freqs[chars] += 1

        # Iteratively merge the most frequent pair
        merges: list[tuple[str, str]] = []
        for _step in range(num_merges):
            pair_counts: Counter[tuple[str, str]] = Counter()
            for word, freq in word_freqs.items():
                for i in range(len(word) - 1):
                    pair_counts[(word[i], word[i + 1])] += freq
            if not pair_counts:
                break
            best = pair_counts.most_common(1)[0][0]
            merges.append(best)

            # Apply the merge to all words
            new_word_freqs: Counter[tuple[str, ...]] = Counter()
            merged = best[0] + best[1]
            for word, freq in word_freqs.items():
                new_word: list[str] = []
                i = 0
                while i < len(word):
                    if (
                        i < len(word) - 1
                        and word[i] == best[0]
                        and word[i + 1] == best[1]
                    ):
                        new_word.append(merged)
                        i += 2
                    else:
                        new_word.append(word[i])
                        i += 1
                new_word_freqs[tuple(new_word)] += freq
            word_freqs = new_word_freqs

        # Build vocabulary: special tokens + single chars + merges
        vocab: dict[str, int] = dict(SPECIAL_TOKENS)
        idx = len(SPECIAL_TOKENS)

        # Add single-character tokens
        chars_seen: set[str] = set()
        for text in texts:
            chars_seen.update(text)
        for ch in sorted(chars_seen):
            if ch not in vocab:
                vocab[ch] = idx
                idx += 1

        # Add merged tokens
        for a, b in merges:
            merged = a + b
            if merged not in vocab:
                vocab[merged] = idx
                idx += 1

        tokenizer = cls(merges=merges, vocab=vocab)
        return tokenizer

    # ── Encoding ─────────────────────────────────────────────

    def _apply_merges(self, chars: list[str]) -> list[str]:
        """Apply learned BPE merges to a sequence of characters."""
        while len(chars) >= 2:
            best_pair = None
            best_rank = float("inf")
            for i in range(len(chars) - 1):
                pair = (chars[i], chars[i + 1])
                rank = self._merge_ranks.get(pair)
                if rank is not None and rank < best_rank:
                    best_rank = rank
                    best_pair = pair
            if best_pair is None:
                break
            merged = best_pair[0] + best_pair[1]
            new_chars: list[str] = []
            i = 0
            while i < len(chars):
                if (
                    i < len(chars) - 1
                    and chars[i] == best_pair[0]
                    and chars[i + 1] == best_pair[1]
                ):
                    new_chars.append(merged)
                    i += 2
                else:
                    new_chars.append(chars[i])
                    i += 1
            chars = new_chars
        return chars

    def encode(
        self,
        text: str,
        *,
        add_bos: bool = False,
        add_eos: bool = False,
    ) -> list[int]:
        """Encode text to token IDs."""
        ids: list[int] = []
        if add_bos:
            ids.append(self.special_tokens["<|bos|>"])

        # Handle special token sequences in text
        parts = self._split_special(text)
        for part, is_special in parts:
            if is_special:
                ids.append(self.special_tokens[part])
            else:
                # Pre-tokenize then BPE
                raw_tokens = _SPLIT_RE.findall(part)
                for raw in raw_tokens:
                    chars = list(raw)
                    bpe_tokens = self._apply_merges(chars)
                    for tok in bpe_tokens:
                        ids.append(
                            self.vocab.get(tok, self.special_tokens.get("<|unk|>", 3))
                        )

        if add_eos:
            ids.append(self.special_tokens["<|eos|>"])
        return ids

    def _split_special(self, text: str) -> list[tuple[str, bool]]:
        """Split text into (substring, is_special) parts."""
        if not self.special_tokens:
            return [(text, False)]
        pattern = "(" + "|".join(re.escape(k) for k in self.special_tokens) + ")"
        parts = re.split(pattern, text)
        result: list[tuple[str, bool]] = []
        for p in parts:
            if not p:
                continue
            result.append((p, p in self.special_tokens))
        return result

    def decode(self, ids: list[int], *, skip_special: bool = True) -> str:
        """Decode token IDs back to text."""
        special_ids = set(self.special_tokens.values()) if skip_special else set()
        tokens: list[str] = []
        for i in ids:
            if i in special_ids:
                continue
            tok = self.id_to_token.get(i, "")
            tokens.append(tok)
        return "".join(tokens)

    # ── Chat Format ──────────────────────────────────────────

    def encode_chat(
        self,
        messages: list[dict[str, str]],
        *,
        add_generation_prompt: bool = False,
    ) -> list[int]:
        """Encode a list of chat messages in Nexora chat format.

        Each message dict has 'role' and 'content' keys.
        Format: <|bos|><|role|>content<|role|>content...<|eos|>
        """
        role_tokens = {"system": "<|system|>", "user": "<|user|>", "assistant": "<|assistant|>"}
        ids: list[int] = [self.special_tokens["<|bos|>"]]

        for msg in messages:
            role_tok = role_tokens.get(msg["role"])
            if role_tok:
                ids.append(self.special_tokens[role_tok])
            ids.extend(self.encode(msg["content"]))

        if add_generation_prompt:
            ids.append(self.special_tokens["<|assistant|>"])
        else:
            ids.append(self.special_tokens["<|eos|>"])

        return ids

    # ── Persistence ──────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save tokenizer to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "merges": [list(m) for m in self.merges],
            "vocab": self.vocab,
            "special_tokens": self.special_tokens,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "NexoraTokenizer":
        """Load tokenizer from a JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        merges = [tuple(m) for m in data["merges"]]
        vocab = data["vocab"]
        tokenizer = cls(merges=merges, vocab=vocab)
        if "special_tokens" in data:
            tokenizer.special_tokens = data["special_tokens"]
        return tokenizer

    @property
    def vocab_size(self) -> int:
        return len(self.vocab)

    def __len__(self) -> int:
        return self.vocab_size
