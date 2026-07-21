"""Append-only JSON store for user feedback / RLHF training data.

Records are written to `data/feedback.jsonl` — one JSON object per line (JSON
Lines), which is append-safe under concurrency and is exactly the format the
native-model trainer (`load_instruction_data`) consumes. Each record carries the
full turn plus the user's data and the rating, so it doubles as a training
example and an audit log.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# backend/data/feedback.jsonl
FEEDBACK_FILE = Path(__file__).resolve().parents[2] / "data" / "feedback.jsonl"
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_feedback(record: dict[str, Any]) -> dict[str, Any]:
    """Append one feedback record; returns it with an id + timestamp attached."""
    full = {
        "id": str(uuid.uuid4()),
        "timestamp": _now(),
        **record,
        "used_for_training": False,
    }
    with _lock:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with FEEDBACK_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(full, ensure_ascii=False) + "\n")
    return full


def read_all() -> list[dict[str, Any]]:
    """Read every feedback record (empty list if the file doesn't exist yet)."""
    if not FEEDBACK_FILE.exists():
        return []
    with _lock, FEEDBACK_FILE.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def stats() -> dict[str, Any]:
    """Aggregate counts used by the /feedback/stats endpoint + the RL trainer."""
    recs = read_all()
    up = sum(1 for r in recs if r.get("rating") == "up")
    down = sum(1 for r in recs if r.get("rating") == "down")
    corrections = sum(1 for r in recs if r.get("correction"))
    backends: dict[str, int] = {}
    for r in recs:
        b = r.get("backend") or "unknown"
        backends[b] = backends.get(b, 0) + 1
    # Examples the RL trainer would actually use: 👍 responses + any correction.
    trainable = sum(1 for r in recs if r.get("rating") == "up" or r.get("correction"))
    return {
        "total": len(recs),
        "up": up,
        "down": down,
        "corrections": corrections,
        "trainable_examples": trainable,
        "by_backend": backends,
        "file": str(FEEDBACK_FILE),
    }
