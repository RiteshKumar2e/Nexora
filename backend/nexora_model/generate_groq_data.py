"""Knowledge distillation: use Groq to generate a large instruction dataset.

Groq writes diverse questions + high-quality answers across many domains; each is
saved as {category, system, user, assistant} to a JSON-Lines file in the single
training folder. Training the native model on this teaches it to imitate Groq.

    python -m nexora_model.generate_groq_data --target 30000

Output: nexora_model/training_data/groq_data.jsonl (append-safe / resumable).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import time
from pathlib import Path

DEFAULT_SYSTEM = "You are Nexora, a helpful, honest and concise AI assistant."

TOPICS = [
    "Python programming", "JavaScript and web development", "data structures",
    "algorithms and complexity", "machine learning", "deep learning and neural networks",
    "artificial intelligence concepts", "databases and SQL", "computer networks",
    "operating systems", "software engineering practices", "version control with Git",
    "REST APIs and backend development", "front-end development and CSS",
    "cloud computing basics", "cybersecurity basics", "mathematics and arithmetic",
    "algebra and equations", "geometry", "probability and statistics", "calculus basics",
    "physics", "chemistry", "biology", "astronomy and space", "earth science",
    "world history", "geography", "economics basics", "finance and budgeting",
    "health and nutrition basics", "productivity and study tips", "career advice",
    "writing and grammar", "summarizing text", "rewriting and rephrasing",
    "explaining concepts simply", "step-by-step reasoning", "comparisons between things",
    "everyday how-to questions", "cooking basics", "general knowledge trivia",
    "definitions of common terms", "logic puzzles", "email and message drafting",
    "interview preparation", "debugging code", "data analysis with Python",
    "object-oriented programming", "recursion and iteration",
]

GEN_TEMPLATE = (
    "Generate {n} diverse, realistic user questions about {topic}, each with a clear, "
    "accurate, well-formatted answer. Vary difficulty and phrasing. "
    "Return ONLY a JSON array; each item an object with exactly two string keys: "
    '"question" and "answer". No markdown, no commentary, just the JSON array.'
)


def _extract_json_array(text: str) -> list[dict]:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = t.find("["), t.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(t[start : end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for it in data if isinstance(data, list) else []:
        if isinstance(it, dict) and it.get("question") and it.get("answer"):
            out.append({"question": str(it["question"]), "answer": str(it["answer"])})
    return out


async def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a Groq-distilled dataset")
    ap.add_argument("--out", default="nexora_model/training_data/groq_data.jsonl")
    ap.add_argument("--target", type=int, default=30000)
    ap.add_argument("--per-call", type=int, default=8)
    ap.add_argument("--sleep", type=float, default=1.5)
    args = ap.parse_args()

    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.llm.base import ChatMessage
    from app.llm.groq_client import GroqClient

    client = GroqClient()
    if not client.keys:
        raise SystemExit("No GROQ_API_KEYS set in .env — needed to generate data.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    count = 0
    if out.exists():
        with out.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        seen.add(json.loads(line)["user"].strip().lower())
                        count += 1
                    except Exception:
                        pass
    print(f"Starting at {count} examples; target {args.target}. Output: {out}", flush=True)

    fails = 0
    while count < args.target:
        topic = random.choice(TOPICS)
        reply = ""
        try:
            async for ch in client.stream_chat(
                [ChatMessage(role="user", content=GEN_TEMPLATE.format(n=args.per_call, topic=topic))],
                max_tokens=2048, temperature=0.9,
            ):
                if ch.delta:
                    reply += ch.delta
        except Exception as exc:  # noqa: BLE001
            fails += 1
            print(f"  call failed ({exc}); backing off", flush=True)
            time.sleep(min(30, 2 ** min(fails, 5)))
            continue

        pairs = _extract_json_array(reply)
        if not pairs:
            fails += 1
            time.sleep(args.sleep)
            continue
        fails = 0

        added = 0
        with out.open("a", encoding="utf-8") as fh:
            for qa in pairs:
                key = qa["question"].strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                fh.write(json.dumps({
                    "category": topic, "system": DEFAULT_SYSTEM,
                    "user": qa["question"].strip(), "assistant": qa["answer"].strip(),
                }, ensure_ascii=False) + "\n")
                added += 1
                count += 1
        if added:
            print(f"  +{added} ({topic}) -> {count}/{args.target}", flush=True)
        time.sleep(args.sleep)

    print(f"Done. {count} examples in {out}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
