# IntelliDocs Demo Script

**Purpose:** Ordered list of actions to perform live during the final project demonstration.  
**Duration:** ~10-15 minutes  
**Audience:** Technical and non-technical stakeholders

---

## Pre-Demo Setup (5 minutes before)

1. **Verify all services are running:**
   ```bash
   # Check deployed URLs
   curl https://your-ai-service.modal.run/health
   curl https://your-server.onrender.com/api/health
   curl https://your-client.onrender.com
   ```

2. **Open browser tabs:**
   - Tab 1: Client URL (https://your-client.onrender.com)
   - Tab 2: Admin Dashboard (will navigate after login)
   - Tab 3: AI Service logs (Modal dashboard or `modal logs intellidocs-ai-service`)
   - Tab 4: Server logs (Render dashboard)

3. **Prepare test documents:**
   - `sample.pdf` — A 2-3 page technical document (e.g., research paper, technical report)
   - `sample.txt` — A simple text file with key facts

4. **Have credentials ready:**
   - Test user: `demo@intellidocs.com` / `DemoPass123!`
   - Or register fresh during demo

---

## Demo Sequence

### 1. Authentication Flow (1 min)

**Actions:**
- Open client URL → shows Login page
- Click "Register" → fill email/password → submit
- Verify redirect to Chat window with "Welcome!" message
- Click "Logout" → verify redirect to Login
- Log in again → verify instant access (JWT in localStorage)

**Talking Points:**
- "JWT-based auth with bcrypt password hashing"
- "Tokens persist across page reloads — no re-login needed"
- "Protected routes: chat, history, upload all require valid token"

---

### 2. Document Upload & Ingestion (1 min)

**Actions:**
- Click "📄 Upload Document" button
- Select `sample.pdf` → click Upload
- Wait for success toast: "Document ingested successfully (X chunks)"
- Click upload again → select `sample.txt` → upload

**Talking Points:**
- "FastAPI `/ingest` endpoint → Python ingestion pipeline"
- "PDF/text loading → recursive chunking (500 tokens, 50 overlap) → sentence-transformers embeddings → FAISS vector store"
- "Chunks persisted to disk — survives container restarts"

---

### 3. RAG-Grounded Answer with Citations (2 min)

**Actions:**
- Ask: **"What is the main topic of the uploaded document?"**
- Wait for answer → observe:
  - Natural language response
  - **Citations** below answer (source filename, chunk excerpt)
  - **Confidence badge** (High/Medium/Low)
- Ask: **"Summarize the key findings from the document."**
- Verify citations match relevant sections

**Talking Points:**
- "Agent routes to RAG path — retrieves top-4 chunks from FAISS"
- "Structured output via Pydantic `Answer` schema — guaranteed citations"
- "Confidence heuristic: High (≥3 chunks), Medium (1-2), Low (0)"
- "Zero hallucination: 'I don't know' when context insufficient"

---

### 4. Tool-Triggered Answer (MCP Integration) (2 min)

**Actions:**
- Ask: **"Search for information about [specific technical term from doc] in the knowledge base."**
- Observe in AI service logs: `route: "tool"`, `tool_called: "search_documents"`
- Verify answer incorporates search results
- Ask: **"Look up metadata for the document 'sample.pdf'."**
- Observe: `tool_called: "lookup_metadata"` → returns chunk count, sample text

**Talking Points:**
- "LangGraph agent with router node — decides RAG vs Tool vs Clarify"
- "MCP (Model Context Protocol) server exposes 3 tools as stdio"
- "Tools: search_documents, fetch_web_page, lookup_metadata"
- "Tool results folded into context → structured answer with citations"

---

### 5. Clarifying Question Exchange (1 min)

**Actions:**
- Ask: **"Tell me about it."** (vague pronoun)
- Observe: Agent returns `route: "clarify"` with clarification question
- Answer the clarification: **"I mean the methodology section."**
- Verify agent now answers correctly

**Talking Points:**
- "Router detects ambiguity (short queries, pronouns, vague references)"
- "Instead of hallucinating, agent asks targeted clarification"
- "Multi-turn conversation state maintained via LangGraph checkpointer"

---

### 6. Hybrid Search Comparison (1 min)

**Actions:**
- In AI service logs, note: `RETRIEVAL_MODE=hybrid`
- Ask a keyword-heavy question: **"What does the document say about [specific acronym/term]?"**
- Compare with vector-only (mention: toggle `RETRIEVAL_MODE=vector` in .env)
- Explain: Hybrid = MongoDB text index (BM25) + FAISS (cosine) → RRF fusion

**Talking Points:**
- "Vector search misses exact terms, acronyms, proper nouns"
- "Keyword search catches exact matches but misses semantics"
- "Reciprocal Rank Fusion (k=60) merges both — parameter-free"
- "Local fallback uses MongoDB text index; production uses Atlas Search + Atlas Vector Search"

---

### 7. Fine-Tuned Model Comparison (2 min)

**Actions:**
- Switch to fine-tuned model (in .env or explain it's configured):
  ```
  LLM_PROVIDER=finetuned
  FINETUNED_MODEL=intellidocs-finetuned
  ```
- Ask same questions from steps 3-4
- Compare: style, domain vocabulary, citation quality
- Mention: trained on Q&A pairs generated from YOUR documents

**Talking Points:**
- "LoRA/QLoRA fine-tuning on Llama 3.1 8B — 4-bit, ~8GB VRAM"
- "Dataset: 150-300 Q&A pairs generated from ingested chunks"
- "Exported to GGUF via Ollama Modelfile — runs locally, zero API cost"
- "Switchable via `LLM_PROVIDER` — no code changes"

---

### 8. Admin Dashboard & Evaluation (1 min)

**Actions:**
- Navigate to `/admin` (or click "Admin" in header)
- Show charts:
  - Accuracy by category (RAG, Tool, Clarify)
  - Latency distribution
  - Cost per query (estimated)
- Show human evaluation scores (if available)
- Show latest eval report timestamp

**Talking Points:**
- "Automated eval harness: 15 test cases across 4 categories"
- "Metrics: path accuracy, tool accuracy, answer score, latency, cost"
- "Human eval rubric: Relevance, Faithfulness, Helpfulness (1-5)"
- "LangSmith/W&B tracing for debugging agent decisions"

---

### 9. History Persistence (30 sec)

**Actions:**
- Refresh page (F5) → verify chat history loads
- Click "Logout" → log in again → verify history persists
- Show MongoDB: `db.chatmessages.find()` has user-scoped messages

**Talking Points:**
- "Per-user chat history in MongoDB"
- "Messages include: role, content, citations, confidence, timestamp"
- "History loads on mount — seamless UX"

---

### 10. Architecture & Deployment Summary (1 min)

**Actions:**
- Show architecture diagram (README mermaid)
- Mention deployment:
  - AI Service → Modal (GPU, scale-to-zero)
  - Server → Render (free tier web service)
  - Client → Render (free tier static site + CDN)
  - MongoDB → Atlas (M0 free tier)
- Show CI/CD: push to main → GitHub Actions → auto-deploy

**Talking Points:**
- "Three-service architecture: decoupled, independently scalable"
- "Containerized with Docker — identical local and prod environments"
- "CI/CD: lint → test → build → deploy on every push"
- "Free-tier friendly: Modal $30/mo credits, Render free, Atlas M0 free"

---

## Post-Demo Q&A Prep

**Common Questions & Answers:**

| Question | Answer |
|----------|--------|
| "How does it handle large documents?" | Chunking (500 tokens) + FAISS; for production, migrate to Chroma/Qdrant for metadata filtering |
| "Can multiple users share documents?" | Currently per-user isolation; next step: shared collections with access control |
| "What's the cost at scale?" | Modal: ~$0.73/hr (T4) only when active; Render: free tier; Atlas: M0 free |
| "How accurate is the fine-tuned model?" | Run `LLM_PROVIDER=finetuned python -m eval.run_eval` — compare with base |
| "Can I use OpenAI/Anthropic instead?" | Yes — change `LLM_PROVIDER` in .env, no code changes |
| "What about streaming responses?" | Not yet implemented; next step: LangGraph streaming + SSE |

---

## Fallback Plans

| Issue | Fallback |
|-------|----------|
| Deployed URL down | Run locally with `docker-compose up` |
| Fine-tuned model not ready | Demo with `LLM_PROVIDER=ollama` (base model) |
| MongoDB Atlas unavailable | Use local MongoDB in docker-compose |
| GPU quota exceeded | Demo CPU inference (slower) or use API provider |

---

## Success Criteria (All Must Pass)

- [ ] User registers, logs in, sees chat
- [ ] Document uploads successfully (chunk count shown)
- [ ] RAG question returns cited answer with confidence badge
- [ ] Tool-triggered question shows `route: "tool"` in logs
- [ ] Clarifying question triggers clarification flow
- [ ] Hybrid search mode visible in logs
- [ ] Fine-tuned model answers (or base model if not ready)
- [ ] Admin dashboard shows eval charts
- [ ] History persists across reload and re-login
- [ ] Architecture and deployment story told clearly

---

**End of Demo** — Thank the audience, offer to answer questions!