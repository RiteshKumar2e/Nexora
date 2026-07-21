"""Train the native Nexora model on the web instruction data (from scratch).

Pipeline: load the openly-licensed JSON dataset -> train a byte-level BPE
tokenizer on it -> instruction-tune the from-scratch Transformer (assistant-only
loss) -> save checkpoints the backend loads (checkpoints/ckpt_best.pt +
tokenizer.json).

    python -m nexora_model.train_web                        # defaults
    python -m nexora_model.train_web --max-steps 3000 --batch-size 8

Honest note: this is a ~6.3M-parameter model trained on CPU. It will learn the
*format* and common patterns of instruction following, not broad factual
knowledge. For strong answers keep LLM_BACKEND=groq; this trains your own model.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Train native model on web data")
    ap.add_argument("--data", default="nexora_model/datasets/web_instruct.jsonl")
    ap.add_argument("--vocab-size", type=int, default=8000)
    ap.add_argument("--max-steps", type=int, default=2500)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--tokenizer-sample", type=int, default=6000,
                    help="examples used to train the tokenizer (BPE needs a sample, not all)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--resume", action="store_true",
                    help="continue from checkpoints/ckpt_best.pt (reuses its tokenizer) "
                         "and train --max-steps MORE steps, accumulating over runs")
    args = ap.parse_args()

    import torch
    from torch.utils.data import DataLoader

    from nexora_model.config import CPU_SMALL
    from nexora_model.dataset import InstructionDataset, load_instruction_data
    from nexora_model.tokenizer import NexoraTokenizer
    from nexora_model.training import NexoraTrainer
    from nexora_model.transformer import NexoraTransformer

    ckpt_dir = Path(__file__).resolve().parent / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = ckpt_dir / "ckpt_best.pt"
    tok_path = ckpt_dir / "tokenizer.json"

    # --- data ---
    train, val, _test, stats = load_instruction_data(args.data)
    print(f"Loaded {stats.total_examples:,} examples "
          f"(train={len(train):,}, val={len(val):,}) across {len(stats.categories)} categories")

    resuming = args.resume and ckpt_path.exists() and tok_path.exists()

    if resuming:
        # Reuse the existing tokenizer + weights and keep training.
        tokenizer = NexoraTokenizer.load(str(tok_path))
        ck = torch.load(ckpt_path, map_location=args.device, weights_only=False)
        from nexora_model.config import NexoraModelConfig
        config = NexoraModelConfig(**ck.get("config", {}))
        config.vocab_size = tokenizer.vocab_size
        model = NexoraTransformer(config)
        model.load_state_dict(ck["model_state_dict"], strict=False)
        print(f"Resuming from {ckpt_path.name} (tokenizer vocab={tokenizer.vocab_size})")
    else:
        # Fresh: train a new tokenizer on a sample, then a new model.
        print(f"Training tokenizer (vocab={args.vocab_size})...")
        sample = train[: args.tokenizer_sample]
        texts = [f"{e['user']} {e['assistant']}" for e in sample]
        tokenizer = NexoraTokenizer.train(texts, vocab_size=args.vocab_size)
        tokenizer.save(str(tok_path))
        print(f"  saved tokenizer (vocab={tokenizer.vocab_size}) -> {tok_path}")
        config = CPU_SMALL
        config.vocab_size = tokenizer.vocab_size

    config.max_steps = args.max_steps
    config.batch_size = args.batch_size
    config.learning_rate = args.lr
    config.warmup_steps = max(20, args.max_steps // 20)
    model = model if resuming else NexoraTransformer(config)
    print(f"Model: {model.num_parameters/1e6:.1f}M params "
          f"(d={config.d_model}, L={config.n_layers}, ctx={config.max_seq_len})")

    # --- datasets / loaders ---
    train_ds = InstructionDataset(train, tokenizer, max_len=config.max_seq_len)
    val_ds = InstructionDataset(val, tokenizer, max_len=config.max_seq_len)
    train_loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=config.batch_size)
    print(f"Encoded {len(train_ds):,} train / {len(val_ds):,} val examples")

    # --- train ---
    print(f"Training for {config.max_steps} steps (batch={config.batch_size}, lr={args.lr})...")
    trainer = NexoraTrainer(
        model=model, config=config,
        train_loader=train_loader, val_loader=val_loader,
        device=args.device, output_dir=str(ckpt_dir),
    )
    state = trainer.train()
    saved = trainer.save_checkpoint("best")
    print(f"\nDone. Trained {state.step} steps.")
    print(f"Saved: {saved}")
    print("Set LLM_BACKEND=nano in .env and restart the backend to serve this model.")


if __name__ == "__main__":
    main()
