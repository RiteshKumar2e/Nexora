"""24/7 continuous training of the native model on the growing dataset.

Loops forever: reload ALL instruction data (web Dolly set + the growing Groq
distillation), continue-train for a round, save the checkpoint, GENERATE sample
answers, and write everything as JSON into ONE folder (training_data/). It is
crash-proof: any error in a round is logged and the loop keeps going.

    python -m nexora_model.train_all_day
    python -m nexora_model.train_all_day --round-steps 1000

Everything for a training run lives in nexora_model/training_data/:
    groq_data.jsonl   - Groq-distilled examples (grown by generate_groq_data)
    metrics.json      - per-round training metrics
    samples.json      - sample native answers after each round (watch it improve)
Checkpoints go to nexora_model/checkpoints/ckpt_best.pt (+ tokenizer.json).
Set LLM_BACKEND=nano (or hybrid) and restart the backend to serve the latest.
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

SAMPLE_PROMPTS = [
    "What is machine learning?",
    "How do I reverse a string in Python?",
    "Explain photosynthesis in two sentences.",
    "What is the difference between a list and a tuple in Python?",
    "Give me one tip to study more effectively.",
]


def _load_all(paths: list[Path]) -> list[dict]:
    examples: list[dict] = []
    for p in paths:
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ex = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ex.get("user") and ex.get("assistant"):
                    examples.append(ex)
    return examples


def _append_json(path: Path, entry: dict) -> None:
    data = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = []
    data.append(entry)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="24/7 continuous training")
    ap.add_argument("--round-steps", type=int, default=800)
    ap.add_argument("--vocab-size", type=int, default=8000)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--min-examples", type=int, default=300)
    ap.add_argument("--val-fraction", type=float, default=0.05)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    import random

    import torch
    from torch.utils.data import DataLoader

    from nexora_model.config import CPU_SMALL, NexoraModelConfig
    from nexora_model.dataset import InstructionDataset
    from nexora_model.inference import GenerationConfig, NexoraGenerator
    from nexora_model.tokenizer import NexoraTokenizer
    from nexora_model.training import NexoraTrainer
    from nexora_model.transformer import NexoraTransformer

    base = Path(__file__).resolve().parent
    ckpt_dir = base / "checkpoints"
    tdir = base / "training_data"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    tdir.mkdir(parents=True, exist_ok=True)
    tok_path = ckpt_dir / "tokenizer.json"
    ckpt_path = ckpt_dir / "ckpt_best.pt"
    data_files = [base / "datasets" / "web_instruct.jsonl", tdir / "groq_data.jsonl"]

    tokenizer = None
    rnd = 0
    print("24/7 training started. Ctrl-C to stop.", flush=True)

    while True:
        rnd += 1
        try:
            examples = _load_all(data_files)
            if len(examples) < args.min_examples:
                print(f"[round {rnd}] {len(examples)} examples (< {args.min_examples}); waiting...", flush=True)
                time.sleep(60)
                rnd -= 1
                continue

            random.Random(1337).shuffle(examples)
            n_val = max(1, int(len(examples) * args.val_fraction))
            train_ex, val_ex = examples[n_val:], examples[:n_val]

            if tokenizer is None:
                if tok_path.exists():
                    tokenizer = NexoraTokenizer.load(str(tok_path))
                    print(f"[round {rnd}] loaded tokenizer (vocab={tokenizer.vocab_size})", flush=True)
                else:
                    sample = [f"{e['user']} {e['assistant']}" for e in train_ex[:6000]]
                    tokenizer = NexoraTokenizer.train(sample, vocab_size=args.vocab_size)
                    tokenizer.save(str(tok_path))
                    print(f"[round {rnd}] trained tokenizer (vocab={tokenizer.vocab_size})", flush=True)

            if ckpt_path.exists():
                ck = torch.load(ckpt_path, map_location=args.device, weights_only=False)
                config = NexoraModelConfig(**ck.get("config", {}))
                config.vocab_size = tokenizer.vocab_size
                model = NexoraTransformer(config)
                model.load_state_dict(ck["model_state_dict"], strict=False)
            else:
                config = CPU_SMALL
                config.vocab_size = tokenizer.vocab_size
                model = NexoraTransformer(config)

            config.max_steps = args.round_steps
            config.batch_size = args.batch_size
            config.learning_rate = args.lr
            config.warmup_steps = max(10, args.round_steps // 20)

            train_ds = InstructionDataset(train_ex, tokenizer, max_len=config.max_seq_len)
            loader = DataLoader(train_ds, batch_size=config.batch_size, shuffle=True, drop_last=True)
            print(f"[round {rnd}] training {args.round_steps} steps on {len(train_ds):,} examples "
                  f"({len(examples):,} total)...", flush=True)

            trainer = NexoraTrainer(model=model, config=config, train_loader=loader,
                                    device=args.device, output_dir=str(ckpt_dir))
            state = trainer.train()
            trainer.save_checkpoint("best")

            # Generate sample answers so quality is visible over time (stored as JSON).
            gen = NexoraGenerator(model=model, tokenizer=tokenizer, device=args.device)
            gcfg = GenerationConfig(max_new_tokens=60, temperature=0.7, top_k=40)
            samples = []
            for q in SAMPLE_PROMPTS:
                try:
                    ans = "".join(gen.stream_chat([{"role": "user", "content": q}], gcfg))
                except Exception as exc:  # noqa: BLE001
                    ans = f"(generation error: {exc})"
                samples.append({"q": q, "a": ans.strip()[:300]})

            stamp = datetime.now(timezone.utc).isoformat()
            _append_json(tdir / "metrics.json", {
                "round": rnd, "timestamp": stamp,
                "total_examples": len(examples), "train_examples": len(train_ds),
                "steps_this_round": state.step, "vocab_size": tokenizer.vocab_size,
            })
            _append_json(tdir / "samples.json", {"round": rnd, "timestamp": stamp, "samples": samples})
            print(f"[round {rnd}] done. ckpt + JSON saved ({len(examples):,} ex). "
                  f"Sample: {samples[0]['a'][:80]!r}", flush=True)

        except Exception:  # noqa: BLE001 — never let the 24/7 loop die
            print(f"[round {rnd}] ERROR:\n{traceback.format_exc()}", flush=True)
            time.sleep(30)


if __name__ == "__main__":
    main()
