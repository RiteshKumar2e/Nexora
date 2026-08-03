# Nexora

A self-hosted, ChatGPT/Claude-style AI assistant: **FastAPI + async SQLAlchemy** backend,
**Next.js 15 (App Router)** frontend, a **pluggable LLM layer** (own from-scratch model,
local Ollama, or hosted Groq), plus projects, file upload/parsing, lexical RAG, tools,
memories, artifacts, RLHF feedback capture, and an in-repo trainable Transformer.

> **Status (verified 2026-08-03):** the streaming-chat vertical slice works end to end.
> Many later-phase subsystems exist in the backend but are only partly wired to the UI —
> see [Flow status](#flow-status-what-actually-runs) and [Known gaps](#known-gaps--rough-edges)
> before assuming a feature is live.

---

## Contents

- [Architecture](#architecture)
- [Request flow](#request-flow-post-apichat)
- [Flow status](#flow-status-what-actually-runs)
- [Quick start (local dev)](#quick-start-local-dev--the-path-that-is-known-to-work)
- [Configuration](#configuration)
- [Switching the LLM backend](#switching-the-llm-backend)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [The native model (`nexora_model`)](#the-native-model-nexora_model)
- [Tests](#tests)
- [Docker Compose](#docker-compose)
- [Known gaps & rough edges](#known-gaps--rough-edges)
- [Security notes](#security-notes)
- [Roadmap](#roadmap)

---

## Architecture

```mermaid
flowchart LR
  U[Browser · Next.js 15] -- REST + SSE --> B[FastAPI · /api]
  B --> S[services / repositories]
  S --> D[(SQLite dev · Postgres prod)]
  B --> L{LLMClient}
  L -->|groq| G[Groq API · multi-key, multi-model]
  L -->|nano| N[nexora_model · in-process Transformer]
  L -->|ollama| O[Ollama / vLLM / llama.cpp · OpenAI-compatible]
  L -->|hybrid| H[native first, Groq on quality-gate fail]
  B --> F[data/uploads + data/feedback.jsonl]
```

Every model call goes through the `LLMClient` protocol (`backend/app/llm/base.py`), so the
inference engine is a config change, not a code change. SQL lives in `app/services/` and the
route modules stay thin.

---

## Request flow (`POST /api/chat`)

```mermaid
sequenceDiagram
  participant UI as Next.js (lib/api.ts)
  participant API as FastAPI /api/chat
  participant DB as Database
  participant LLM as LLMClient

  UI->>API: POST {message, conversation_id?} (+ Bearer token)
  API->>DB: resolve/create conversation, persist user message
  API->>DB: load history -> build context (system prompt + turns)
  Note over API: if conversation.project_id is set,<br/>inject project instructions + RAG chunks
  API-->>UI: event: meta {conversation_id, title, is_new}
  API-->>UI: event: citations {…}  (only when RAG fired)
  LLM-->>API: token stream
  API-->>UI: event: token {delta}   (repeated)
  API->>DB: persist assistant message + usage
  API-->>UI: event: done {conversation_id, message_id, usage}
```

SSE frames are `meta`, `citations`, `token`, `done`, `error`. The client parses them in
`frontend/lib/api.ts:streamChat` and can cancel via `AbortController`.

---

## Flow status: what actually runs

Verified by booting the backend, exercising the endpoints, running the test suite, and
typechecking the frontend.

| Flow | Status | Notes |
| --- | --- | --- |
| Backend boots, 38 routes mounted | ✅ | SQLite schema auto-created on startup |
| `GET /api/health`, `/api/health/ready` | ✅ | ready reports backend + reachability |
| Streaming chat (SSE) end to end | ✅ | verified live against Groq `openai/gpt-oss-120b` |
| Conversation persistence, list/get/rename/pin/delete | ✅ | anonymous scope |
| Register / login (JWT issue) | ✅ | hand-rolled HS256 JWT + PBKDF2 hashing |
| `GET /api/auth/me` with `Authorization` header | ❌ | header is read as a **query param** — always 401 |
| Per-user data isolation on REST routes | ❌ | 23 endpoints ignore the header (same root cause) |
| Projects CRUD | ✅ (anonymous only) | scoping to a user does not take effect |
| File upload + parse (PDF/DOCX/XLSX/CSV/TXT/code) | ✅ | UI inlines extracted text into the message |
| Lexical RAG retrieval in chat | ⚠️ unreachable | needs `conversation.project_id`, which no API sets |
| Tools: list + execute | ✅ | `calculator` → `23`, `python_runner` → `45` |
| Memories / Artifacts CRUD | ✅ API only | no UI consumer |
| Feedback capture + stats | ✅ | appended to `backend/data/feedback.jsonl` |
| `GET /api/evaluation` | ⚠️ mocked | returns hardcoded metrics, runs no evaluation |
| `POST /api/training/start` | ❌ | `FileNotFoundError` on the dataset path; also wedges state |
| Backend unit tests (`pytest`) | ✅ | 6 passed |
| Frontend typecheck (`tsc --noEmit`) | ✅ | clean |
| Docker Compose quick start | ❌ | expects a root `.env` / `.env.example` that is not in the repo |

---

## Quick start (local dev — the path that is known to work)

Prerequisites: **Python 3.10+**, **Node 20+**. No Docker, Postgres, or GPU required for the
default config (SQLite + a hosted or in-process model).

```bash
# ── backend ────────────────────────────────────────────────
cd backend
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash; use .venv/bin/activate on Unix
pip install -r requirements.txt
# not yet in requirements.txt but imported by the app — install these too:
pip install psutil pypdf python-docx openpyxl

# create backend/.env (see Configuration below), then:
uvicorn app.main:app --reload          # http://localhost:8000
```

```bash
# ── frontend (second terminal) ─────────────────────────────
cd frontend
npm install
npm run dev                            # http://localhost:3000
```

Open **http://localhost:3000**. API docs: **http://localhost:8000/docs**.

### Smoke test

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/ready

curl -N -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Write a haiku about local models"}'

curl -X POST http://localhost:8000/api/tools/execute \
  -H 'Content-Type: application/json' \
  -d '{"name":"calculator","arguments":{"expression":"2+3*7"}}'
```

---

## Configuration

All settings are typed in `backend/app/core/config.py` and read from `backend/.env`.
No module reads `os.environ` directly.

```dotenv
# App
APP_NAME=Nexora
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000          # plain comma-separated list

# Data
DATABASE_URL=sqlite+aiosqlite:///./nexora.db
# DATABASE_URL=postgresql+asyncpg://nexora:nexora@localhost:5432/nexora
REDIS_URL=redis://localhost:6379/0          # reserved; not on the request path yet

# Auth
JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# LLM backend: nano | ollama | groq | hybrid
LLM_BACKEND=groq

# Groq (only when LLM_BACKEND=groq or hybrid)
GROQ_API_KEYS=key1,key2                     # rotated on 429 / quota errors
GROQ_MODELS=                                # empty => auto-discover, ranked best-first
GROQ_TEMPERATURE=0.7
GROQ_MAX_TOKENS=2048
GROQ_REQUEST_TIMEOUT=120
GROQ_FALLBACK_TO_NANO=true                  # last-resort local fallback

# Native model (LLM_BACKEND=nano)
NANO_LLM_MAX_NEW_TOKENS=160
NANO_LLM_TEMPERATURE=0.7
NANO_LLM_TOP_K=40

# Ollama / any OpenAI-compatible server (LLM_BACKEND=ollama)
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen3:8b
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
LLM_REQUEST_TIMEOUT=300
```

Frontend: `frontend/.env` → `NEXT_PUBLIC_API_URL=http://localhost:8000`.
(Three components still hardcode `http://localhost:8000` — see [Known gaps](#known-gaps--rough-edges).)

---

## Switching the LLM backend

Selected in `backend/app/llm/factory.py` from `LLM_BACKEND`:

| Value | Client | Behaviour |
| --- | --- | --- |
| `nano` | `NanoLMClient` | Loads `backend/nexora_model/checkpoints/ckpt_best.pt` (falls back to `ckpt_final.pt`, then to an untrained model) and generates in-process on CPU. No server, no API key. |
| `ollama` | `OllamaClient` | Any OpenAI-compatible `/v1` server — Ollama, vLLM, SGLang, llama.cpp. Point `OLLAMA_BASE_URL` at it. |
| `groq` | `GroqClient` | Hosted Groq API. Rotates across `GROQ_API_KEYS` on rate limits, auto-discovers and ranks chat models, optionally falls back to the native model. |
| `hybrid` / `auto` | `HybridClient` | Native model first; if the answer fails a quality gate (`HYBRID_MIN_*` settings), re-answers with Groq. |

---

## API reference

All routes are mounted under `/api`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health`, `/health/ready` | Liveness / dependency readiness |
| POST | `/auth/register`, `/auth/login` | Returns access + refresh tokens and the user |
| GET | `/auth/me` | Current user *(header auth currently broken)* |
| POST | `/chat` | SSE streaming chat |
| GET/POST | `/conversations` | List / create |
| GET/PATCH/DELETE | `/conversations/{id}` | Detail (with messages) / rename+pin / delete |
| GET/POST | `/projects` | List / create workspaces with custom instructions |
| GET/PATCH/DELETE | `/projects/{id}` | Detail / update / delete |
| POST | `/files/upload` | Multipart upload, ≤10 MB, server-side text extraction |
| GET | `/files` | List (optional `project_id` filter) |
| DELETE | `/files/{id}` | Delete row + file on disk |
| GET/POST | `/artifacts`, `/artifacts/{id}` | Versioned assistant artifacts |
| GET/POST/DELETE | `/memories` | Cross-conversation memory records |
| GET | `/tools` | Tool catalog with JSON input schemas |
| POST | `/tools/execute` | Body: `{"name": "...", "arguments": {...}}` |
| POST | `/training/start`, `/training/stop` | Native-model training control *(start is broken)* |
| GET | `/training/status` | Step/loss/throughput + CPU/RAM |
| GET | `/evaluation` | Per-category scores *(currently hardcoded)* |
| POST | `/feedback` | Thumb rating + optional correction → JSONL |
| GET | `/feedback/stats` | Totals by rating / backend |

---

## Project structure

```
Nexora/
├─ docker-compose.yml            # db (pgvector) · redis · ollama · backend · frontend
├─ docs/CURRENT_SYSTEM_AUDIT.md  # deep audit from 2026-07-21 (partly superseded)
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # app factory, lifespan (init_db), CORS
│  │  ├─ core/                   # config.py (typed settings), logging.py
│  │  ├─ db/                     # declarative base + mixins, async engine/session
│  │  ├─ models/                 # Conversation, Message, Project, UploadedFile, Memory, Artifact
│  │  ├─ schemas/                # pydantic I/O contracts
│  │  ├─ services/               # conversation_service (SQL lives here)
│  │  ├─ auth/                   # User model, PBKDF2 hashing, hand-rolled JWT, routes
│  │  ├─ llm/                    # base protocol, factory, ollama/groq/nano/hybrid clients
│  │  ├─ rag/                    # chunker, LexicalIndex (BM25-ish), retrieval service
│  │  ├─ files/parsers.py        # PDF/DOCX/XLSX/CSV/JSON/text extraction
│  │  ├─ tools/                  # Tool base, registry, calculator, python_runner
│  │  ├─ feedback/               # RLHF capture → data/feedback.jsonl
│  │  └─ api/routes/             # health, chat, conversations, projects, files,
│  │                             # artifacts, tools, memories, training, evaluation
│  ├─ nexora_model/              # the from-scratch model (see below)
│  ├─ tests/test_core.py         # tokenizer, transformer, chunker, lexical search
│  └─ requirements.txt
└─ frontend/
   ├─ app/                       # layout, page.tsx (single-page chat), globals.css
   ├─ components/                # Sidebar, Header, Composer, MessageBubble, Markdown,
   │                             # CodeBlock, Mermaid, ContextPanel, CommandPalette,
   │                             # AuthModal, ThemeToggle, Providers
   └─ lib/                       # api.ts (REST + SSE parser), types.ts
```

---

## The native model (`nexora_model`)

A from-scratch decoder-only Transformer, trainable on CPU, living inside this repo:

- `tokenizer.py` — byte-level BPE with role special tokens (`<|system|>`, `<|user|>`, `<|assistant|>`)
- `transformer.py` — RMSNorm + RoPE + SwiGLU blocks, KV-cached decoding
- `config.py` — `CPU_SMALL` preset: `vocab_size 8000, d_model 256, n_layers 6, n_heads 8, max_seq_len 256`
- `dataset.py`, `training.py`, `inference.py` — instruction dataset, trainer with metrics callback, generator
- `datasets/`, `training_data/` — instruction + web-scraped corpora
- `generate_groq_data.py`, `fetch_web_data.py`, `train_web.py`, `train_all_day.py`, `rl_finetune.py`

Train from the CLI (see `train.txt`):

```bash
cd backend
python -m nexora_model.train_all_day --round-steps 800
python -m nexora_model.generate_groq_data --target 30000
```

Serve it by setting `LLM_BACKEND=nano`. At this size the model is coherent only on
narrow instruction data — `groq` is the default for usable answers, `hybrid` bridges the two.

---

## Tests

```bash
cd backend && python -m pytest tests/ -q     # 6 tests: tokenizer, transformer, RAG chunker, lexical search
cd frontend && npx tsc --noEmit              # strict typecheck
```

---

## Docker Compose

`docker-compose.yml` defines `db` (pgvector), `redis`, `ollama`, `backend`, `frontend`.
It is **not currently runnable as written**: the `backend` service uses `env_file: .env` at the
repo root and no such file (nor a `.env.example`) exists, and the compose wiring assumes the
Postgres + Ollama setup rather than the SQLite + Groq config the app now defaults to.
Use the [local dev path](#quick-start-local-dev--the-path-that-is-known-to-work) until that is fixed.

---

## Known gaps & rough edges

Ordered roughly by impact. Each was reproduced against a running instance.

1. **Auth header is ignored on 23 endpoints.** `get_current_user_optional` declares
   `authorization: str | None = None`; used via `Depends(...)`, FastAPI binds it as a
   **query parameter**, so the `Authorization` header never reaches it. Only `chat.py` and
   `feedback/routes.py` declare `Header(None)` explicitly.
   *Observed:* sign in → send a message (the conversation is stored with your `user_id`) →
   `GET /api/conversations` with the same token returns only anonymous threads, so the new
   chat never appears in the sidebar.
2. **`GET /api/auth/me` always returns 401** for header auth (same cause; it works as
   `?authorization=Bearer%20…`). `app/page.tsx` deletes the stored token when `/me` fails, so
   **a login never survives a page refresh**.
3. **`POST /api/training/start` fails**: `run_training_task` builds paths from
   `"backend/nexora_model"` relative to the process CWD (which is `backend/`), so it raises
   `FileNotFoundError: backend\nexora_model\datasets\instructions.jsonl`. Because the flag is
   set before the `try`, `is_running` stays `True` forever and every later start returns
   `400 Training is already running`.
4. **RAG never fires.** Retrieval is gated on `conversation.project_id`, but neither
   `ChatRequest` nor `ConversationCreate` accepts a `project_id`, and no service sets it.
   Document Q&A works only because the composer inlines extracted text into the message.
5. **Missing runtime dependencies.** `psutil`, `pypdf`, `python-docx`, `openpyxl` are imported
   but absent from `requirements.txt`. `psutil` is a module-level import in
   `api/routes/training.py`, so on a clean install **the whole app fails to import**.
6. **`GET /api/evaluation` is mocked** — fixed accuracy/perplexity numbers and two canned examples.
7. **UI surfaces that are placeholders:** the ContextPanel tabs (Artifacts, Files, Sources,
   Memory, Tools) render static empty states and call no API; its "Model Info" tab hardcodes the
   native model's hyperparameters regardless of the active backend. The sidebar's Projects /
   Library / Plugins / Training items only fire a toast. The header's model dropdown does not
   change the model used.
8. **`/api/health/ready` mislabels the model**: any backend other than `ollama` is reported as
   `"nano-llm (own model)"`, so the header shows the wrong model while Groq is serving.
9. **Hardcoded API URL** in `app/page.tsx`, `components/AuthModal.tsx`, and `components/Header.tsx`
   (`http://localhost:8000`) bypasses `NEXT_PUBLIC_API_URL`.
10. **Dead config**: `nano_llm_dir`, `nano_llm_checkpoint`, `nano_llm_tokenizer`,
    `nano_llm_chat_format` point at a sibling `nano-llm` project, but `NanoLMClient` now resolves
    checkpoints from the embedded `nexora_model` package and ignores them.
11. **No migrations.** Alembic is a dependency but schema is created with `create_all`.
12. `backend/.venv` in this working copy is incomplete (no `Scripts/`); recreate it if `pip`/`python`
    can't be found there.

---

## Security notes

- `backend/.env` contains **live Groq API keys**. It is gitignored, but the keys are on disk and
  were used during development — rotate them and keep an `.env.example` in the repo instead.
- `POST /api/tools/execute` is **unauthenticated**, and `python_runner` executes arbitrary code
  with the server's own interpreter, guarded only by a 5-second timeout. It is not a sandbox —
  do not expose this instance to untrusted users or the public internet.
- JWT signing and password hashing are hand-rolled (HMAC-SHA256 + PBKDF2) rather than a vetted
  library; there is no refresh-token rotation, revocation, rate limiting, or CSRF protection.
- Uploads are capped at 10 MB but the MIME type is not validated, and parsed text is stored
  in full in the database.

---

## Roadmap

| Phase | Focus | State |
| --- | --- | --- |
| 0–1 | Foundation + streaming chat vertical slice | ✅ done |
| 2 | Auth, users, per-user isolation | ⚠️ built, header wiring broken |
| 3 | RAG: upload → parse → chunk → retrieve → cited answers | ⚠️ built, not reachable from chat |
| 4 | Tool calling (calculator, Python runner) | ⚠️ API done; not called by the model, not sandboxed |
| 5 | Multi-agent supervisor + reasoning view | ⬜ not started |
| 6 | Memory system | ⚠️ CRUD only, no retrieval or UI |
| 7 | Knowledge graph (Neo4j) | ⬜ not started |
| 8 | Vision, coding workspace, notebooks, research | ⬜ not started |
| 9 | Hardening: migrations, rate limiting, sandboxing, tests, docs | ⬜ mostly not started |

---

## License

TBD.
