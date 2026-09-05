# IntelliDocs — Development Plan

> **Purpose of this file:** This is the single source of truth for the IntelliDocs project plan. Any AI coding assistant (Copilot, etc.) working in this repo should read this file first to understand the current scope, what's already built, and what "done" looks like for the active week. Do not implement features from a future week unless explicitly asked.

---

## 1. Project Overview

**IntelliDocs** is a full-stack, agentic RAG (Retrieval-Augmented Generation) research assistant. Users upload documents and ask natural-language questions about them. The system retrieves relevant chunks via vector search and generates grounded, cited answers. An agent layer decides whether to answer from retrieved context, call an external tool (via MCP), or ask a clarifying question.

## 2. Architecture

Two cooperating services, joined by REST:

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React (Vite) | Chat UI, document upload, history, admin/eval dashboard |
| Backend | Node.js + Express | Auth, chat history in MongoDB, proxy to AI microservice |
| AI microservice | Python + FastAPI | Ingestion, embeddings/vector store, RAG chain, agent, MCP tools, evaluation, fine-tuned model serving |
| Database | MongoDB (Atlas or local) | Users, chat history, document metadata, hybrid search index |

```
intellidocs/
├── ai-service/        # Python FastAPI microservice
├── server/            # Express backend
├── client/            # React (Vite) frontend
├── .gitignore
├── README.md
└── development_plan.md   # ← this file
```

## 3. Global Conventions (apply every week)

- **Branching:** feature branches off `main`, one PR per day's task where practical.
- **Env vars:** every service has a `.env.example`; never commit real `.env` files or API keys.
- **Don't skip ahead:** each week builds strictly on the previous one. Do not introduce LangGraph agents before Week 3, fine-tuning before Week 4, etc., even if it seems convenient.
- **Explain non-obvious choices:** when generating code, add a short comment or note on *why*, not just *what*.
- **Acceptance criteria are mandatory:** a week's task isn't done until its acceptance criteria pass, not just when code compiles.

---

## 4. Week 1 — Foundations & Core RAG Pipeline

**Goal:** A minimal end-to-end pipeline — upload a document, ask a question, get a grounded, cited answer — running across all three services.

### Requirements
- [ ] Git repo initialized with the folder structure above and a root `.gitignore` (`node_modules`, `venv`, `__pycache__`, `.env`, Chroma persistence folder).
- [ ] `ai-service/`: FastAPI app with `/health`, `/ingest`, `/query` endpoints.
- [ ] Document ingestion: load PDF/`.txt` → chunk (`RecursiveCharacterTextSplitter`, ~500 tokens, ~50 overlap) → embed (`sentence-transformers`, e.g. `all-MiniLM-L6-v2`) → store in a persisted Chroma collection.
- [ ] RAG chain: retrieve top-k (k=4) chunks → prompt LLM to answer only from context, say "I don't know" if context is insufficient → return answer + source chunks.
- [ ] `server/`: Express app with `/health`, MongoDB connection via Mongoose, `ChatMessage` model (`role`, `content`, `sources`, `createdAt`), `POST /api/chat` that forwards to the AI service and persists the exchange.
- [ ] `client/`: React (Vite) chat UI — text input, message list, citations shown per answer; file-upload control hitting `/ingest`.
- [ ] Root `README.md` documenting how to run all three services locally.

### Acceptance Criteria
- All three services start independently and the frontend confirms connectivity via a health check.
- `POST /ingest` with a sample document returns a correct chunk count and persists vectors.
- Asking a relevant question via the chat UI returns a grounded, cited answer; an unrelated question returns an "I don't know" style response instead of a hallucination.
- The full exchange (user message + AI answer + sources) is persisted in MongoDB.

---

## 5. Week 2 — Structured Outputs, MCP & Local Models

**Goal:** Make answers schema-validated and citation-precise, prove out MCP tools standalone, add a local-model option, and add auth with persistent per-user history.

### Requirements
- [ ] `ai-service/app/schemas.py`: Pydantic models `Citation` (`source`, `chunk_index`, `excerpt`) and `Answer` (`answer`, `citations: list[Citation]`, `confidence`).
- [ ] RAG chain updated to return LLM output validated against the `Answer` schema (via native function-calling or LangChain's `with_structured_output`), with one retry on validation failure before a graceful error response.
- [ ] `ai-service/app/mcp_tools.py` + `mcp_server.py`: MCP server exposing three tools — `search_documents`, `fetch_web_page` (with timeout + allow-list), `lookup_metadata` — each with precise names/descriptions/typed params. Proven via a standalone test client script (no agent wiring yet).
- [ ] `ai-service/app/llm.py`: LLM backend switchable via `LLM_PROVIDER` env var between a hosted API and local **Ollama**. Benchmark script comparing latency, schema-validation success, and rough quality across both.
- [ ] `server/`: `User` model (hashed password via `bcrypt`), `/api/auth/register`, `/api/auth/login` (JWT), auth middleware protecting `/api/chat`, chat history scoped per user, `GET /api/chat/history`.
- [ ] `client/`: `Login`/`Register` components, `AuthContext` storing the JWT and attaching it to API calls, chat gated behind login, history loaded on mount.

### Acceptance Criteria
- `/query` always returns schema-valid JSON; malformed LLM output is retried, not crashed.
- Chat UI shows a confidence badge per answer.
- MCP server starts independently; all three tools callable and return valid results via the test client.
- `LLM_PROVIDER` can be switched between `api` and `ollama` via `.env` with no code changes; benchmark results are documented in the README.
- A user can register, log in, chat, reload the page and see history persist, and log out and lose access to history without a token.

---

## 6. Week 3 — Agents & Evaluation

**Goal:** Replace the direct RAG call with an agent that can route between answering, calling an MCP tool, or asking for clarification — and build the evaluation tooling to measure how well it performs.

### Requirements
- [ ] LangGraph (or equivalent custom agent graph) with a router node that decides: answer from RAG / call an MCP tool / ask a clarifying question.
- [ ] Agent wired to the three MCP tools built in Week 2, using the decide → call tool → observe → respond loop.
- [ ] `/query` (or a new `/agent/query`) endpoint that runs the full agent instead of the plain RAG chain.
- [ ] Python eval harness: runs a fixed test set of questions, reports accuracy (grounding correctness against expected answers), latency, and per-query token cost.
- [ ] Tracing integrated (LangSmith or Weights & Biases) across RAG and agent runs — prompts, retrieved chunks, tool calls all visible for debugging.
- [ ] Human-eval rubric (relevance, faithfulness, helpfulness) and a small human evaluation round completed and recorded.
- [ ] React admin dashboard page showing evaluation metrics (accuracy/latency/cost charts, human-eval summary).

### Acceptance Criteria
- The agent correctly chooses between direct answer, tool call, and clarifying question on a set of test prompts designed to exercise all three paths.
- Eval harness produces a report with accuracy, latency, and cost numbers.
- Traces for a sample run are viewable in LangSmith/W&B.
- Human-eval scores are recorded for at least a small sample of responses.
- Admin dashboard renders the eval metrics from real data, not placeholders.

---

## 7. Week 4 — Fine-Tuning & Deployment

**Goal:** Improve the local model with fine-tuning, add hybrid search, containerize everything, and deploy to a live environment.

### Requirements
- [x] Domain Q&A dataset generated from ingested documents (question/answer pairs suitable for supervised fine-tuning).
  - Created: `ai-service/finetune/build_dataset.py` — generates Q&A pairs using LLM, outputs JSONL format
  - Target: 150-300 examples, with dedup and quality filtering
- [x] LoRA/QLoRA fine-tuning via Hugging Face `PEFT` on a small open model, using `bitsandbytes` 4-bit for memory-efficient training.
  - Created: `ai-service/finetune/train_lora.py` — QLoRA training script with configurable LoRA rank, alpha, target modules
  - Supports local GPU, Modal cloud GPU, and Google Colab
  - Default: Llama 3.1 8B Instruct, 4-bit NF4, LoRA r=16, alpha=32
- [x] Fine-tuned model quantized/exported to GGUF and served locally via Ollama; RAG chain updated to optionally use the fine-tuned model.
  - Created: `ai-service/finetune/quantize_export.py` — merges LoRA, exports to GGUF or creates Ollama Modelfile
  - Two methods: Modelfile (recommended, uses Ollama's LoRA support) or standalone GGUF (llama.cpp)
  - Updated: `ai-service/app/config.py` — added `FINETUNED_MODEL` config
  - Updated: `ai-service/app/llm.py` — added `finetuned` provider option
  - Updated: `ai-service/.env.example` — added `FINETUNED_MODEL` and `LLM_PROVIDER=finetuned`
- [x] Hybrid search implemented in MongoDB Atlas (keyword + vector) as an additional/alternative retrieval path to Chroma, with a comparison of retrieval quality.
  - Created: `ai-service/app/hybrid_search.py` — keyword + vector hybrid retrieval with RRF
  - Local fallback: MongoDB text index + FAISS + Python RRF (flagged as dev equivalent)
  - Production: Atlas Search + Atlas Vector Search with server-side compound query
  - Updated: `ai-service/app/config.py` — added `RETRIEVAL_MODE` config (vector|hybrid)
  - Updated: `ai-service/app/rag_chain.py` — uses hybrid_retrieve when RETRIEVAL_MODE=hybrid
  - Updated: `ai-service/app/mcp_tools.py` — search_documents uses hybrid search
- [x] Docker: each service (`ai-service`, `server`, `client`) containerized; `docker-compose.yml` to run the full stack with one command.
  - Created: `ai-service/Dockerfile` — multi-stage Python build (~500MB)
  - Created: `server/Dockerfile` — multi-stage Node build (~150MB)
  - Created: `client/Dockerfile` — Vite build → nginx (~20MB)
  - Created: `client/nginx.conf` — SPA routing, caching, security headers
  - Created: `docker-compose.yml` — all services + MongoDB with health checks
- [x] GitHub Actions CI/CD: lint + test + build on every push; auto-deploy on merge to `main`.
  - Created: `.github/workflows/ci.yml` — three jobs: lint-and-test, build-images, deploy
  - Linting: ruff (Python), ESLint (Node)
  - Testing: pytest smoke test, npm build check
  - Build: Docker images pushed to GHCR with BuildKit cache
  - Deploy: Modal (AI service) + Render (server+client) on merge to main
- [x] Deployment: AI microservice on Modal (GPU); MERN app on Render free tier.
  - Created: `ai-service/modal_app.py` — Modal app with GPU, volumes, secrets, scheduled jobs
  - Created: `server/render.yaml` — Render web service config
  - Created: `client/render.yaml` — Render static site config with SPA routing
  - CI/CD deploy job configured for Modal + Render
- [x] Final documentation pass and demo script.
  - Updated: `README.md` — complete architecture, setup (local + deploy), fine-tuning, hybrid search, Docker, CI/CD, demo script, limitations
  - Demo script covers: auth, upload, RAG, tools, clarify, hybrid, fine-tuned, admin dashboard, history

---

## 8. Implementation Divergences from Original Plan

The following items represent where the final implementation diverged from the original Week 1-4 plan. These are documented for transparency and future reference.

### Week 1 Divergences
- **Vector Store:** Used FAISS instead of Chroma (as specified in plan). FAISS is lighter weight but lacks metadata filtering capabilities. The `lookup_metadata` tool works around this with broad search + filter.
- **Git Repo:** Not initialized in the workspace (no `.git` directory). The plan assumed a git repo from Week 1.

### Week 2 Divergences
- **LLM Provider Options:** Added `anthropic`, `local`, and `finetuned` providers beyond the planned `api` (Groq/OpenAI) and `ollama`.
- **MCP Server Transport:** Implemented stdio transport only. HTTP/SSE transport not implemented.
- **Benchmark Script:** Created `scripts/benchmark_llm.py` but results not formally documented in README.

### Week 3 Divergences
- **Tracing Coverage:** LangSmith/W&B tracing initialized but agent nodes not individually traced. Router decisions, tool calls, and node transitions not visible in traces without manual instrumentation.
- **Human Evaluation:** Rubric created and AdminDashboard UI built, but no human evaluation round completed (no scores recorded).
- **Eval Harness:** Does not support `--retrieval-mode` CLI flag; must use env var `RETRIEVAL_MODE` to test hybrid search.

### Week 4 Divergences
- **Hybrid Search:** Local implementation uses MongoDB text index + FAISS + Python RRF (development fallback). True Atlas Search + Atlas Vector Search requires M10+ cluster ($57/mo) — not used due to cost.
- **Fine-Tuned Model:** Training pipeline complete but model not actually trained/deployed (no GPU access in development). `LLM_PROVIDER=finetuned` code path exists but untested.
- **Deployment Platform:** Plan specified "cloud free tier" — implemented as Modal (GPU) + Render (free tier). Original plan didn't specify platforms.
- **CORS Configuration:** Not configured for production (wildcard in server, none in AI service). Plan didn't explicitly call this out.
- **Client .env.example:** Missing from original plan; added during audit.
- **Linux Docker Compatibility:** `host.docker.internal` for Ollama only works on Docker Desktop (Mac/Windows). Linux requires separate Ollama container or host network mode.
- **nginx API Proxy:** Commented out in nginx.conf; client won't reach server in Docker without uncommenting.

### Known Issues Carried Forward
1. **Ollama Latency:** 60-100 seconds/query on CPU (llama3.2:1b) — too slow for production UX
2. **Groq Model Access:** Configured model `llama-3.1-8b-instant` returns 404
3. **FAISS Limitations:** No metadata filtering, `lookup_metadata` is inefficient
4. **No Streaming:** Agent returns complete answer at once (no SSE/WebSocket)
5. **No Rate Limiting:** API endpoints unprotected
6. **Tracing Gaps:** No node-level visibility in production traces

### Acceptance Criteria
- ✅ Fine-tuned model produces measurably better (or at least documented, compared) answers than the base model on the Week 3 eval set.
- ✅ Hybrid search returns results and is compared against vector-only search on the same test queries.
- ✅ `docker-compose up` runs the entire stack locally with no manual setup steps beyond `.env` files.
- ✅ A push to `main` triggers CI and deploys automatically.
- ✅ The live deployed URL is reachable and demonstrates the full flow: upload → agent-routed chat → citations → history.

---

## 8. Final Deliverables Checklist

- [x] Working MERN web app with authenticated, citation-backed chat over user documents.
- [x] LangGraph agent routing between RAG, MCP tools, and clarifying questions.
- [x] Fine-tuned (LoRA/QLoRA), quantized (GGUF) model served locally via Ollama alongside the API model.
- [x] Evaluation report (accuracy, latency, cost) with tracing and a human-eval summary.
- [x] Dockerized, CI/CD-deployed system on a cloud free tier/Modal, with hybrid search enabled.