"""Reinforcement-from-feedback fine-tuning for the native Nexora model.

Reads the feedback captured from the UI (`data/feedback.jsonl`) and fine-tunes
the from-scratch model on the responses the user *preferred*:

  * a 👍 rating   → the assistant reply is a good target (reward = +1),
  * a correction  → the user's rewrite is the preferred target (overrides the
    original reply, whether the rating was 👍 or 👎),
  * a 👎 with no correction → skipped for SFT (kept in the log; usable later as a
    "rejected" sample for pairwise DPO).

This is reward-weighted supervised fine-tuning — the practical, stable form of
RLHF for a tiny CPU model: we train on high-reward samples (rejection sampling /
"RLHF-lite") rather than a full PPO loop. Groq's hosted weights cannot be
fine-tuned, so Groq turns contribute their preferred answers to THIS native
model's training set — never a Groq fine-tune.

    python -m nexora_model.rl_finetune                 # train on all feedback
    python -m nexora_model.rl_finetune --max-steps 150 --min-examples 5

The refreshed weights are saved to checkpoints/ckpt_best.pt, which the in-process
backend (`NanoLMClient`) loads on the next restart.
"""
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_SYSTEM = "You are Nexora, a helpful, honest and concise AI assistant."


def _build_examples(records: list[dict]) -> list[dict]:
    """Turn feedback records into instruction examples (preferred targets only)."""
    examples: list[dict] = []
    for r in records:
        user = (r.get("user") or "").strip()
        correction = (r.get("correction") or "").strip()
        assistant = (r.get("assistant") or "").strip()
        # Preferred target: a correction wins; otherwise only keep 👍 replies.
        target = correction or (assistant if r.get("rating") == "up" else "")
        if not user or not target:
            continue
        examples.append(
            {
                "category": "feedback",
                "system": r.get("system") or DEFAULT_SYSTEM,
                "user": user,
                "assistant": target,
            }
        )
    return examples


def main() -> None:
    ap = argparse.ArgumentParser(description="RL-from-feedback fine-tuning")
    ap.add_argument("--max-steps", type=int, default=0, help="0 = auto from data size")
    ap.add_argument("--min-examples", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    import torch
    from torch.utils.data import DataLoader

    from app.feedback.store import read_all
    from nexora_model.config import CPU_SMALL, NexoraModelConfig
    from nexora_model.dataset import InstructionDataset
    from nexora_model.tokenizer import NexoraTokenizer
    from nexora_model.training import NexoraTrainer
    from nexora_model.transformer import NexoraTransformer

    ckpt_dir = Path(__file__).resolve().parent / "checkpoints"
    tok_path = ckpt_dir / "tokenizer.json"

    records = read_all()
    examples = _build_examples(records)
    print(f"Feedback records: {len(records)} | trainable (preferred) examples: {len(examples)}")
    if len(examples) < args.min_examples:
        raise SystemExit(
            f"Not enough preferred examples ({len(examples)} < {args.min_examples}). "
            f"Collect more 👍/corrections in the UI first."
        )

    # --- tokenizer: reuse the one the backend created, else train from feedback ---
    if tok_path.exists():
        tokenizer = NexoraTokenizer.load(str(tok_path))
        print(f"Loaded tokenizer (vocab={tokenizer.vocab_size})")
    else:
        texts = [f"{e['user']} {e['assistant']}" for e in examples]
        tokenizer = NexoraTokenizer.train(texts, vocab_size=CPU_SMALL.vocab_size)
        tok_path.parent.mkdir(parents=True, exist_ok=True)
        tokenizer.save(str(tok_path))
        print(f"Trained new tokenizer (vocab={tokenizer.vocab_size})")

    # --- model: continue from the current checkpoint if present, else fresh ---
    ckpt_path = ckpt_dir / "ckpt_best.pt"
    if not ckpt_path.exists():
        ckpt_path = ckpt_dir / "ckpt_final.pt"

    if ckpt_path.exists():
        ck = torch.load(ckpt_path, map_location=args.device, weights_only=False)
        config = NexoraModelConfig(**ck.get("config", {}))
        config.vocab_size = tokenizer.vocab_size
        model = NexoraTransformer(config)
        model.load_state_dict(ck["model_state_dict"], strict=False)
        print(f"Continuing from {ckpt_path.name} ({model.num_parameters/1e6:.1f}M params)")
    else:
        config = CPU_SMALL
        config.vocab_size = tokenizer.vocab_size
        model = NexoraTransformer(config)
        print(f"No checkpoint found — training a fresh model ({model.num_parameters/1e6:.1f}M params)")

    # --- training config tuned for a small feedback set ---
    steps = args.max_steps or max(20, min(300, len(examples) * 8 // max(args.batch_size, 1)))
    config.max_steps = steps
    config.batch_size = args.batch_size
    config.learning_rate = args.lr
    config.warmup_steps = max(1, steps // 10)

    dataset = InstructionDataset(examples, tokenizer, max_len=config.max_seq_len)
    loader = DataLoader(dataset, batch_size=config.batch_size, shuffle=True)
    print(f"Fine-tuning for {steps} steps on {len(dataset)} examples (lr={args.lr})...")

    trainer = NexoraTrainer(
        model=model, config=config, train_loader=loader,
        device=args.device, output_dir=str(ckpt_dir),
    )
    state = trainer.train()
    saved = trainer.save_checkpoint("best")  # -> checkpoints/ckpt_best.pt
    print(f"\nDone. Trained {state.step} steps on {len(dataset)} preferred examples.")
    print(f"Saved: {saved}")
    print("Restart the backend to serve the updated native model (LLM_BACKEND=nano).")


if __name__ == "__main__":
    main()
