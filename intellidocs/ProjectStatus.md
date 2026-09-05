# IntelliDocs — Project Status

> Last updated: 2026-08-30

## Overall Status

**Week 1 — COMPLETE ✅**

The core end-to-end system is functional: document ingestion, retrieval-augmented
generation, chat UI, and chat-history persistence all work together.

---

## What Is Done

### AI Service (`ai-service/`) — Port 8000
- [x] FastAPI app with `/health`, `/ingest`, `/query` endpoints
- [x] Document ingestion pipeline (load → split → embed → store)
- [x] FAISS vector store (persisted to `faiss_index/`)
- [x] RAG chain (retrieve top-k chunks + generate grounded answer)
- [x] LLM provider wrapper (Groq / OpenAI / Anthropic / local)
- [x] Centralized config (`config.py` + `.env`)

### Express Backend (`server/`) — Port 5000
- [x] Express app with `/api/health`, `/api/chat`, `/api/ingest`
- [x] MongoDB connection + `ChatMessage` model
- [x] Chat flow: save user msg → forward to AI → save assistant msg
- [x] File-upload proxy to AI service (avoids CORS)
- [x] Source-format transformation (AI → MongoDB schema)

### React Frontend (`client/`) — Port 5173
- [x] Chat UI with message bubbles
- [x] File upload button
- [x] Citations display under assistant messages
- [x] Centralized API client (`chatApi.js`)

### Verified Working
- [x] Document ingestion (79 chunks from a PDF)
- [x] Question answering with citations
- [x] Chat history persisted in MongoDB
- [x] Full flow: React → Express → AI Service → FAISS → Groq LLM

---

## What Is Broken / Known Issues

### Active Issues
- **None blocking.** The system runs end-to-end.

### Known Limitations (not bugs, but gaps)
1. **Single-user** — no authentication or user separation.
2. **No conversation memory** — each query is independent; no multi-turn context.
3. **Local FAISS store** — not shared across multiple AI-service instances.
4. **Groq model churn** — model names change frequently; must verify via
   `client.models.list()` before hardcoding.
5. **Slow first startup** — embedding model (`all-MiniLM-L6-v2`) downloads on
   first run.
6. **Chunk text not returned** — AI service returns `{source, page}` but not the
   actual chunk text, so the `text` field in MongoDB sources is empty.

---

## Current Configuration

### `ai-service/.env`
```env
GROQ_API_KEY=<set>
GROQ_MODEL=openai/gpt-oss-20b
LLM_PROVIDER=groq
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### `server/.env`
```env
MONGODB_URI=mongodb://localhost:27017/intellidocs
AI_SERVICE_URL=http://localhost:8000
PORT=5000
```

---

## How to Run

```bash
# Terminal 1: AI Service
cd ai-service && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

# Terminal 2: Express Backend
cd server && npm run dev

# Terminal 3: React Frontend
cd client && npm run dev
```

**Prerequisite:** MongoDB running on `localhost:27017`.

---
