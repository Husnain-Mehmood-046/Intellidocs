# IntelliDocs — Architecture

> Last updated: 2026-08-30

## High-Level Overview

IntelliDocs is an **agentic RAG (Retrieval-Augmented Generation) research
assistant** built as three independent services that communicate over HTTP.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React UI      │────▶│  Express API    │────▶│  FastAPI AI     │
│  (Port 5173)    │     │  (Port 5000)    │     │  (Port 8000)    │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   MongoDB       │     │   FAISS Vector  │
                        │  (Chat History) │     │   Store         │
                        └─────────────────┘     └─────────────────┘
```

| Service      | Tech                          | Port | Purpose                              |
| ------------ | ----------------------------- | ---- | ------------------------------------ |
| `ai-service` | Python 3.11 + FastAPI + FAISS | 8000 | Ingestion, embeddings, RAG chain     |
| `server`     | Node.js + Express + Mongoose  | 5000 | API, chat history, AI proxy          |
| `client`     | React + Vite                  | 5173 | Chat UI                              |

---

## Service Details

### 1. React Frontend (`client/`) — Port 5173

**Files:**
- `src/App.jsx` — root component, renders `ChatWindow`
- `src/components/ChatWindow.jsx` — chat UI (upload, input, messages, citations)
- `src/api/chatApi.js` — centralized API client

**Responsibilities:**
- User interaction (upload documents, ask questions)
- Display answers with expandable citations
- Single API base URL (`/api`) — no CORS issues

**Outbound calls:**
- `POST /api/chat` → Express backend
- `POST /api/ingest` → Express backend

---

### 2. Express Backend (`server/`) — Port 5000

**Files:**
- `src/index.js` — entry point, middleware, DB connect, route mounting
- `src/config/db.js` — Mongoose connection to MongoDB
- `src/models/ChatMessage.js` — chat message schema
- `src/routes/chat.js` — `/api/chat` and `/api/ingest` handlers

**Endpoints:**
| Method | Path          | Purpose                                   |
| ------ | ------------- | ----------------------------------------- |
| GET    | `/api/health` | Health check                              |
| POST   | `/api/chat`   | Chat flow (save + forward + save + reply) |
| POST   | `/api/ingest` | Proxy file upload to AI service           |

**Chat flow (`POST /api/chat`):**
1. Receive `{ message }` from frontend
2. Save user message to MongoDB (`role: "user"`)
3. Forward question to AI service: `POST http://localhost:8000/query`
4. Receive `{ answer, sources }` from AI service
5. Transform sources: `{ source, page }` → `{ filename, chunkIndex, text }`
6. Save assistant message to MongoDB (`role: "assistant"`, sources)
7. Return `{ answer, sources }` to frontend

**Why proxy `/ingest` through Express?**
- Avoids CORS (browser blocks cross-origin calls to `localhost:8000`)
- Keeps frontend on a single API origin
- Allows adding auth/validation later without frontend changes

**MongoDB schema (`ChatMessage`):**
```javascript
{
  role: "user" | "assistant",
  content: String,
  sources: [{ filename, chunkIndex, text }],
  createdAt: Date  // auto via timestamps
}
```

---

### 3. FastAPI AI Service (`ai-service/`) — Port 8000

**Files:**
- `app/main.py` — FastAPI app + endpoints
- `app/config.py` — env vars, paths, model config
- `app/ingestion.py` — document ingestion pipeline
- `app/rag_chain.py` — retrieval + generation
- `app/llm.py` — LLM provider wrapper

**Endpoints:**
| Method | Path       | Purpose                          |
| ------ | ---------- | -------------------------------- |
| GET    | `/health`  | Health check                     |
| POST   | `/ingest`  | Ingest a document into FAISS     |
| POST   | `/query`   | RAG question answering           |

**Ingestion flow (`POST /ingest`):**
1. Receive uploaded file (PDF/TXT)
2. Save to `ai-service/data/`
3. Load document (`PyPDFLoader` / `TextLoader`)
4. Split into chunks (`RecursiveCharacterTextSplitter`, 500 tokens, 50 overlap)
5. Generate embeddings (`HuggingFace all-MiniLM-L6-v2`)
6. Store in FAISS (persisted to `ai-service/faiss_index/`)
7. Return chunk count

**Query flow (`POST /query`):**
1. Receive `{ question }`
2. Generate query embedding
3. Retrieve top-k (k=4) similar chunks from FAISS
4. Build few-shot prompt (context + question)
5. Call LLM (Groq `openai/gpt-oss-20b`)
6. Return `{ answer, sources }`

**LLM providers (`llm.py`):**
- `groq` — Groq's OpenAI-compatible API
- `openai` — OpenAI ChatCompletion
- `anthropic` — Anthropic messages
- `local` — Hugging Face transformers pipeline

---

## Data Flow Example

User asks: *"What is IntelliDocs?"*

```
Browser ──POST /api/chat──▶ Express ──POST /query──▶ FastAPI
   ▲                          │  │                    │  │
   │                          │  │ 1. Save user msg   │  │ 2. Embed query
   │                          │  │    to MongoDB      │  │ 3. FAISS search (top-4)
   │                          │  │                    │  │ 4. Build prompt
   │                          │  │                    │  │ 5. Call Groq LLM
   │                          │  │◀── {answer, sources}│  │
   │                          │  │                    │  │
   │                          │  │ 6. Transform sources│  │
   │                          │  │ 7. Save assistant   │  │
   │                          │  │    msg to MongoDB   │  │
   │◀── {answer, sources} ────│  │                    │  │
```

---

## Key Design Decisions

| Decision                          | Reason                                              |
| --------------------------------- | --------------------------------------------------- |
| Separate AI microservice          | Isolate heavy ML deps (PyTorch, transformers)       |
| FAISS over Chroma                 | Lightweight, file-persisted, no separate server     |
| Express proxies `/ingest`         | Avoid CORS; single API origin for frontend          |
| Few-shot prompt in `rag_chain.py` | Teach LLM to cite sources + say "I don't know"      |
| LLM wrapper (`llm.py`)            | Swap providers in one file                          |
| MongoDB for chat history          | Persistent, queryable, scales for multi-user        |

---

## Environment Variables

### `ai-service/.env`
```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=groq
GROQ_API_KEY=<key>
GROQ_MODEL=openai/gpt-oss-20b
```

### `server/.env`
```env
MONGODB_URI=mongodb://localhost:27017/intellidocs
AI_SERVICE_URL=http://localhost:8000
PORT=5000
```