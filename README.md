# Nexora

A **production-grade, self-hosted AI assistant** — a premium ChatGPT/Claude-style
experience whose core intelligence runs entirely on **local, open-weight models**.
No OpenAI, Anthropic, Gemini, or other paid LLM APIs are used for reasoning.

> **Status:** Phase 1 — a working end-to-end streaming chat vertical slice.
> See the [Roadmap](#roadmap) for what comes next.

---

## What works today (Phase 1)

- 🔒 **100% local inference** via Ollama (OpenAI-compatible API) — swap models freely.
- 💬 **Streaming chat** over Server-Sent Events, token-by-token.
- 🧠 **Persistent conversations** (Postgres) with history, rename, pin, delete.
- ✨ **Premium UI** (Next.js) — glassmorphism, dark mode, smooth streaming.
- 📝 **Rich rendering** — Markdown, code highlighting, tables, **KaTeX** math, **Mermaid** diagrams.
- 🧩 **Swappable model backend** behind one interface (Ollama / vLLM / SGLang / llama.cpp).

---

## Architecture (current slice)

```mermaid
flowchart LR
  U[Browser · Next.js] -- POST /api/chat (SSE) --> B[FastAPI]
  B -- OpenAI-compat /v1 --> O[Ollama · local model]
  B -- SQLAlchemy async --> P[(Postgres + pgvector)]
  B -. cache/queue .-> R[(Redis)]
```

The browser streams tokens straight from FastAPI; FastAPI proxies generation
from a **local** model server and persists every turn. The LLM is reached only
through the `LLMClient` interface (`backend/app/llm/base.py`), so changing the
model or the inference engine is a config change — never a code change.

---

## Prerequisites

- **Docker Desktop** (with the NVIDIA Container Toolkit for GPU) — recommended path, or
- Local **Python 3.12**, **Node 20+**, **Postgres 16 (pgvector)**, and **Ollama**.
- An NVIDIA GPU with **16 GB+** VRAM comfortably runs 7B–14B models.

---

## Quick start (Docker Compose)

```bash
cp .env.example .env

# 1) Start everything (db, redis, ollama, backend, frontend)
docker compose up -d --build

# 2) Pull a model into the running Ollama container (first time only)
docker exec -it nexora-ollama ollama pull qwen3:8b
```

Then open **http://localhost:3000**.
API docs: **http://localhost:8000/docs**.

> Running CPU-only? Remove the `deploy:` block from the `ollama` service in
> `docker-compose.yml` and use a smaller model (e.g. `ollama pull qwen3:1.7b`,
> then set `LLM_MODEL=qwen3:1.7b` in `.env`).

---

## Quick start (local dev, no Docker for app code)

```bash
# --- infra only ---
docker compose up -d db redis ollama
docker exec -it nexora-ollama ollama pull qwen3:8b

# --- backend ---
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
# point at localhost services:
export DATABASE_URL=postgresql+asyncpg://nexora:nexora@localhost:5432/nexora
export OLLAMA_BASE_URL=http://localhost:11434
uvicorn app.main:app --reload

# --- frontend (new terminal) ---
cd frontend
npm install
npm run dev
```

---

## Verifying it works

```bash
# Liveness
curl http://localhost:8000/api/health

# Readiness (checks the local LLM is reachable)
curl http://localhost:8000/api/health/ready

# Stream a chat completion (SSE)
curl -N -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Write a haiku about local models"}'
```

---

## Project structure

```
nexora/
├─ docker-compose.yml         # db (pgvector) · redis · ollama · backend · frontend
├─ .env.example
├─ backend/                   # FastAPI + async SQLAlchemy
│  └─ app/
│     ├─ main.py              # app factory, lifespan, CORS
│     ├─ core/                # config, logging
│     ├─ db/                  # engine, session, base/mixins
│     ├─ models/              # Conversation, Message
│     ├─ schemas/             # pydantic I/O contracts
│     ├─ services/            # business logic (repository pattern)
│     ├─ llm/                 # LLMClient interface + Ollama client + factory
│     └─ api/routes/          # health, conversations, chat (SSE)
└─ frontend/                  # Next.js (App Router)
   ├─ app/                    # layout, page (chat), global styles
   ├─ components/             # Sidebar, MessageBubble, Markdown, Mermaid, Composer
   └─ lib/                    # api client + SSE parser, types
```

---

## Switching models / inference engine

Everything routes through `LLMClient`. To use a different **model**, set
`LLM_MODEL` in `.env` (after `ollama pull <model>`). To use a different
**engine** (vLLM, SGLang, llama.cpp-server), point `OLLAMA_BASE_URL` at that
server's OpenAI-compatible endpoint — no application code changes, because they
all speak `/v1/chat/completions`.

---

## Roadmap

| Phase             | Focus                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------- |
| **0–1 ✅** | Foundation + streaming chat vertical slice (this release)                                       |
| 2                 | Auth (JWT/OAuth), users, workspaces, conversation search/export                                 |
| 3                 | RAG: upload → parse → chunk → embed (pgvector) → hybrid retrieve → rerank → cited answers |
| 4                 | Tool calling (sandboxed Python, calculator, filesystem, vector search)                          |
| 5                 | Multi-agent supervisor + React Flow reasoning view                                              |
| 6                 | Memory system (short/long-term, semantic retrieval, summarization)                              |
| 7                 | Knowledge graph (Neo4j)                                                                         |
| 8                 | Vision AI, coding workspace, AI notebooks, research workspace                                   |
| 9                 | Hardening: rate limiting, audit logs, sandboxing, tests, docs, diagrams                         |

---

## License

TBD.
