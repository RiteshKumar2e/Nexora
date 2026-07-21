# Nexora — Current System Audit

> **Audit date:** 2026-07-21  
> **Auditor:** Automated deep-inspection of every file in the repository

---

## 1. Project Structure

```
nexora/
├── docker-compose.yml          # Postgres (pgvector), Redis, Ollama, backend, frontend
├── .gitignore
├── README.md
├── backend/
│   ├── .env                    # ⚠ Contains live Groq API keys (SECURITY)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── nexora.db               # SQLite dev database (gitignored but present)
│   └── app/
│       ├── __init__.py         # Version 0.1.0
│       ├── main.py             # FastAPI app factory + lifespan
│       ├── core/
│       │   ├── config.py       # Pydantic-settings: all env vars
│       │   └── logging.py      # Structured logging
│       ├── db/
│       │   ├── base.py         # Declarative base + UUID/Timestamp mixins
│       │   └── session.py      # Async engine, session factory, init_db
│       ├── models/
│       │   ├── conversation.py # Conversation ORM model
│       │   └── message.py      # Message ORM model
│       ├── schemas/
│       │   ├── chat.py         # ChatRequest Pydantic model
│       │   └── conversation.py # ConversationRead/Detail/Create/Update
│       ├── services/
│       │   └── conversation_service.py  # Repository pattern CRUD + context builder
│       ├── llm/
│       │   ├── base.py         # LLMClient Protocol + ChatMessage/StreamChunk
│       │   ├── factory.py      # Backend selector (nano/ollama/groq)
│       │   ├── ollama_client.py  # OpenAI-compatible streaming client
│       │   ├── groq_client.py    # Multi-key + multi-model fallback
│       │   └── nano_client.py    # In-process nano-llm loader
│       └── api/
│           ├── router.py       # Aggregates all route modules
│           └── routes/
│               ├── health.py   # /health, /health/ready
│               ├── conversations.py  # CRUD REST endpoints
│               └── chat.py     # SSE streaming chat
└── frontend/
    ├── .env                    # NEXT_PUBLIC_API_URL
    ├── Dockerfile              # Multi-stage Next.js build
    ├── package.json            # Next 15, React 19, markdown/katex/mermaid/sonner
    ├── tsconfig.json           # Strict mode ON
    ├── next.config.mjs         # Standalone output
    ├── public/                 # Empty (.gitkeep only)
    ├── app/
    │   ├── layout.tsx          # Root layout + KaTeX/highlight.js CSS
    │   ├── page.tsx            # Main chat page (single page app)
    │   └── globals.css         # 862-line design system (light + dark)
    ├── components/
    │   ├── Sidebar.tsx         # Conversations list + nav
    │   ├── Header.tsx          # Top bar
    │   ├── Composer.tsx        # Auto-growing input + send/stop
    │   ├── MessageBubble.tsx   # User/assistant message rendering
    │   ├── Markdown.tsx        # react-markdown + GFM + KaTeX + highlight.js
    │   ├── CodeBlock.tsx       # Fenced code with lang label + copy
    │   ├── Mermaid.tsx         # Mermaid diagram renderer
    │   ├── ThemeToggle.tsx     # Light/dark switch
    │   └── Providers.tsx       # ThemeProvider + Toaster
    └── lib/
        ├── api.ts              # REST + SSE client
        └── types.ts            # TypeScript interfaces
```

---

## 2. Working Features ✅

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI backend | ✅ Working | Clean app factory, lifespan, CORS |
| Pydantic settings | ✅ Working | Typed config from .env |
| Async SQLAlchemy (SQLite + Postgres) | ✅ Working | Dual-dialect, UUID columns |
| Conversation CRUD | ✅ Working | Create, list, get, update (rename/pin), delete |
| SSE streaming chat | ✅ Working | Token-by-token with meta/token/done/error events |
| LLMClient abstraction | ✅ Working | Protocol-based, 3 backends |
| Ollama backend | ✅ Working | OpenAI-compatible streaming |
| Groq backend | ✅ Working | Multi-key + multi-model fallback, nano fallback |
| Nano-LLM backend | ⚠ Partially | Loads sibling `nano-llm` project if present |
| Next.js 15 frontend | ✅ Working | App Router, React 19 |
| Dark / Light theme | ✅ Working | next-themes, CSS variables |
| Markdown rendering | ✅ Working | GFM, headings, lists, tables, blockquotes |
| Syntax highlighting | ✅ Working | highlight.js with dark mode overrides |
| KaTeX math | ✅ Working | Inline `$...$` and display `$$...$$` |
| Mermaid diagrams | ✅ Working | Client-side rendering |
| Code block copy | ✅ Working | Language label + copy button |
| Conversation sidebar | ✅ Working | Pinned/recents, search, new chat |
| Auto-scroll | ✅ Working | Smooth scroll on new messages |
| Streaming cursor | ✅ Working | Blinking cursor during generation |
| Stop generation | ✅ Working | AbortController cancellation |
| Toast notifications | ✅ Working | sonner |
| Mobile responsive | ✅ Working | Overlay sidebar on <760px |
| Docker Compose | ✅ Working | Full stack deployment |

---

## 3. Broken / Incomplete Features ⚠

| Issue | Severity | Details |
|-------|----------|---------|
| **API keys committed to .env** | 🔴 Critical | `backend/.env` contains live `GROQ_API_KEYS` — must be rotated and removed |
| **No `.env.example`** | 🟡 Medium | New users have no template for required env vars |
| **No authentication** | 🔴 Critical | All conversations are public, no user isolation |
| **No file upload** | 🟡 Major | No document handling at all |
| **No RAG** | 🟡 Major | No embedding, chunking, or retrieval pipeline |
| **No projects/workspaces** | 🟡 Medium | Single flat conversation list |
| **No artifacts** | 🟡 Medium | No artifact creation or preview panel |
| **No memory system** | 🟡 Medium | No cross-conversation memory |
| **No tool calling** | 🟡 Medium | No calculator, code runner, or other tools |
| **No training dashboard** | 🟡 Medium | No visibility into model training |
| **No evaluation** | 🟡 Medium | No model benchmarking |
| **No custom tokenizer in repo** | 🟡 Major | Depends on external `nano-llm` sibling project |
| **No custom model in repo** | 🟡 Major | Model code lives in separate `nano-llm` project |
| **No tests** | 🔴 Critical | Zero unit/integration/e2e tests |
| **No migration system** | 🟡 Medium | Uses `create_all` instead of Alembic |
| **Sidebar nav items are stubs** | 🟠 Minor | Library, Projects, Scheduled, etc. show "coming soon" toast |
| **No conversation rename in UI** | 🟠 Minor | API exists but no UI input for it |
| **No delete confirmation** | 🟠 Minor | Immediate deletion without confirm dialog |
| **No export** | 🟠 Minor | No Markdown/JSON conversation export |
| **No model badge in UI** | 🟠 Minor | User can't see which model generated a response |
| **No regenerate** | 🟠 Minor | Can't regenerate an assistant response |
| **No edit user message** | 🟠 Minor | Can't edit/retry a previous user turn |
| **No command palette** | 🟠 Minor | No global search or keyboard shortcuts (Ctrl+K) |
| **No rate limiting** | 🟡 Medium | Backend has no request throttling |
| **No CSRF protection** | 🟡 Medium | CORS is set but no CSRF tokens |
| **No input sanitization** | 🟡 Medium | XSS risk in user content rendering |

---

## 4. Model Architecture Assessment

### Current State
- The Nexora model (`nano-llm`) is a **separate repository** — not embedded in this project
- The `NanoLMClient` attempts to load from a sibling `../nano-llm` directory
- Chat format uses role tokens: `<|bos|>`, `<|system|>`, `<|user|>`, `<|assistant|>`, `<|eos|>`
- Single-turn only: uses latest user message, ignores conversation history
- Architecture details are in the external project (not audited here)

### Gaps
- No tokenizer code in this repository
- No Transformer model code in this repository
- No training scripts in this repository
- No datasets in this repository
- No model checkpoints in this repository
- Cannot train, evaluate, or inspect the model from within Nexora

---

## 5. UI Assessment

### Strengths
- Clean, warm color palette (Claude-inspired)
- Well-structured CSS with custom properties
- Proper dark mode with thoughtful color choices
- Good message layout with avatars
- Auto-growing composer with proper keyboard handling
- Smooth animations (rise effect, cursor blink)
- Professional code blocks with language labels

### Weaknesses
- **No right panel** — missing artifact/context panel
- **No model selector** in top bar or composer
- **No file attachment** button in composer
- **Single-page app** — no routing for projects, settings, training
- **No empty state improvements** — only 3 suggestions, no Nexora branding/logo
- **No skeleton loaders** — no loading states
- **No error boundaries** — uncaught errors crash the page
- **Font stack is generic** — no Google Fonts loaded (Inter, JetBrains Mono)
- **Mermaid hardcoded to dark theme** — doesn't respect light mode

---

## 6. Backend Assessment

### Strengths
- Clean layered architecture (routes → services → models)
- Protocol-based LLM abstraction — excellent extensibility
- Robust Groq client with multi-key/multi-model fallback
- Proper async throughout (engine, sessions, streaming)
- Good SSE implementation with meta/token/done/error events
- Conversation history context building

### Weaknesses
- **No authentication at all** — everyone shares the same data
- **No middleware** for logging, rate limiting, or security headers
- **No Alembic migrations** — schema changes require dropping the DB
- **No background tasks** — no Celery/RQ for training, file processing
- **Session management in chat route is manual** — fragile pattern
- **`LLMBackendError` defined in `ollama_client`** — should be in `base.py`
- **`get_llm_client` is `lru_cache`d** — can't switch providers at runtime

---

## 7. Security Issues

| Issue | Risk | Fix |
|-------|------|-----|
| Live API keys in committed `.env` | 🔴 Critical | Rotate keys, add `.env` to `.gitignore` (already done but file exists) |
| No authentication | 🔴 Critical | Add JWT/session auth |
| No input validation beyond Pydantic | 🟡 Medium | Add content length limits, sanitization |
| No rate limiting | 🟡 Medium | Add per-IP or per-user throttling |
| No CSRF tokens | 🟡 Medium | Add for state-changing requests |
| XSS potential in Markdown | 🟡 Medium | Sanitize HTML in rendered markdown |
| No security headers | 🟡 Medium | Add CSP, X-Frame-Options, etc. |
| CORS allows all methods/headers | 🟠 Minor | Restrict to needed methods |

---

## 8. Performance Considerations

| Area | Current | Recommendation |
|------|---------|----------------|
| DB queries | No indexes beyond PK | Add indexes on `conversation_id`, `created_at` |
| Message loading | `selectin` loads all messages | Add pagination for long conversations |
| Frontend rendering | All messages re-render | Add virtualized list for 100+ messages |
| Model loading | Per-request via `lru_cache` | Good (singleton), but can't reload |
| SSE streaming | Direct proxy | Good pattern, no buffering issues |

---

## 9. Proposed Upgrade Plan

### Phase 1: Foundation (Core Infrastructure)
1. Embed tokenizer, model, training, and dataset code in this repository
2. Create `.env.example`, remove committed secrets
3. Set up Alembic migrations
4. Add comprehensive design token system
5. Load professional fonts (Inter, JetBrains Mono)

### Phase 2: Authentication & Data Isolation
6. Add user registration, login, logout
7. Password hashing (bcrypt), JWT tokens
8. Per-user conversation/project isolation
9. Session management

### Phase 3: UI Redesign
10. Three-panel layout (sidebar + main + context panel)
11. Enhanced composer with attachments, model selector
12. Model badge on responses
13. Command palette (Ctrl+K)
14. Conversation rename, delete confirmation, export
15. Message actions: regenerate, edit, branch

### Phase 4: Projects & Files
16. Project CRUD with instructions
17. File upload with type validation
18. Document parsing (PDF, DOCX, TXT, CSV, etc.)
19. File preview in context panel

### Phase 5: RAG Pipeline
20. Text chunking engine
21. BM25/TF-IDF lexical search (scratch mode)
22. Optional local embeddings
23. Hybrid retrieval with source citations
24. Project-scoped document isolation

### Phase 6: Artifacts & Tools
25. Artifact panel with create/preview/version
26. Code artifact editor
27. Tool calling framework
28. Built-in tools: calculator, Python runner, search

### Phase 7: Memory System
29. Conversation memory (context window)
30. Project memory (instructions + knowledge)
31. User preference memory
32. Memory CRUD UI

### Phase 8: Model Training & Evaluation
33. Embed Transformer model code
34. Embed tokenizer training
35. Create balanced multi-domain dataset
36. Training dashboard with real metrics
37. Evaluation dashboard with category scoring

### Phase 9: Provider System
38. Unified provider interface
39. Optional Groq (already exists, refine)
40. Optional Ollama (already exists, refine)
41. Model router with provider badges

### Phase 10: Quality & Deployment
42. Unit tests (tokenizer, model, auth, RAG)
43. Integration tests (API endpoints, streaming)
44. Frontend tests (components, interactions)
45. Security hardening
46. Documentation suite
47. Production deployment guide
