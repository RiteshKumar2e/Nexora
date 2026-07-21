"""Fetch an openly-licensed instruction dataset from the web and save it as JSON.

Source: Databricks **Dolly-15k** — ~15,000 human-written instruction/response
pairs, licensed **CC BY-SA 3.0** (open, permissively usable). This is a
legitimately published dataset, not a silent scrape of copyrighted pages.

The records are converted into our training format
`{category, system, user, assistant}` and written to a single JSON-Lines file
that the trainer (`train_web.py` / `load_instruction_data`) consumes directly.

    python -m nexora_model.fetch_web_data
    python -m nexora_model.fetch_web_data --out nexora_model/datasets/web_instruct.jsonl --min 10000
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

DEFAULT_SYSTEM = "You are Nexora, a helpful, honest and concise AI assistant."

DOLLY_URL = (
    "https://huggingface.co/datasets/databricks/databricks-dolly-15k/"
    "resolve/main/databricks-dolly-15k.jsonl"
)
DOLLY_LICENSE = "CC BY-SA 3.0 (Databricks Dolly-15k)"


def _convert(obj: dict) -> dict | None:
    """Dolly record -> our instruction format. Folds any context into the user turn."""
    instr = (obj.get("instruction") or "").strip()
    context = (obj.get("context") or "").strip()
    resp = (obj.get("response") or "").strip()
    if not instr or not resp:
        return None
    user = instr if not context else f"{instr}\n\nContext:\n{context}"
    return {
        "category": obj.get("category", "general"),
        "system": DEFAULT_SYSTEM,
        "user": user,
        "assistant": resp,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch open web instruction data")
    ap.add_argument("--out", default="nexora_model/datasets/web_instruct.jsonl")
    ap.add_argument("--min", type=int, default=10000, help="minimum required examples")
    ap.add_argument("--max-chars", type=int, default=4000, help="drop overly long examples")
    args = ap.parse_args()

    print(f"Downloading {DOLLY_LICENSE}\n  {DOLLY_URL}")
    req = urllib.request.Request(DOLLY_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode("utf-8", "replace")

    seen: set[str] = set()
    examples: list[dict] = []
    categories: dict[str, int] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        ex = _convert(obj)
        if ex is None:
            continue
        if len(ex["user"]) + len(ex["assistant"]) > args.max_chars:
            continue
        key = ex["user"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        examples.append(ex)
        categories[ex["category"]] = categories.get(ex["category"], 0) + 1

    if len(examples) < args.min:
        raise SystemExit(
            f"Only {len(examples)} usable examples (< {args.min}). "
            f"Network issue or source changed."
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")

    total_chars = sum(len(e["user"]) + len(e["assistant"]) for e in examples)
    print(f"\nSaved {len(examples):,} examples to {out}")
    print(f"  ~{total_chars // 4:,} tokens (rough), license: {DOLLY_LICENSE}")
    print("  categories:")
    for cat, n in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {cat:<24} {n:>6}")


if __name__ == "__main__":
    main()
