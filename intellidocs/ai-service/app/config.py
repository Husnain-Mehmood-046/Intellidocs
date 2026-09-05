"""
Central configuration for the AI service.

Why a separate config module?
- Keeps all tunable values (model names, paths, env vars) in one place.
- Makes it trivial to swap models or change storage locations without
  hunting through route/ingestion code.
- Loads environment variables once at import time via python-dotenv.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the ai-service/ directory (parent of app/).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# --- Embedding model ---
# all-MiniLM-L6-v2 is a lightweight (384-dim) sentence transformer that is
# fast on CPU and good enough for most RAG demos. Swap for a larger model
# (e.g. all-mpnet-base-v2) if you need higher retrieval quality.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Storage paths ---
# Resolve relative to the ai-service/ directory so the service works
# regardless of the current working directory.
_BASE_DIR = Path(__file__).resolve().parent.parent

# Helper to resolve paths relative to _BASE_DIR
def _resolve_path(env_var: str, default: Path) -> Path:
    """Resolve a path from env var, relative to _BASE_DIR if not absolute."""
    val = os.getenv(env_var)
    if val is None:
        return default
    p = Path(val)
    if p.is_absolute():
        return p
    return _BASE_DIR / p

DATA_DIR = _resolve_path("DATA_DIR", _BASE_DIR / "data")
# CHROMA_DIR is now used for FAISS vector store (index.faiss and index.pkl)
CHROMA_DIR = _resolve_path("CHROMA_DIR", _BASE_DIR / "chroma_db")

# --- LLM provider (used in Day 5-6) ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# --- Ollama (local model serving, Day 12-13) ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# --- Fine-tuned model (Week 4) ---
# Set LLM_PROVIDER=finetuned to use this model via Ollama
FINETUNED_MODEL = os.getenv("FINETUNED_MODEL", "intellidocs-finetuned")

# --- Retrieval defaults ---
TOP_K = 4  # number of chunks to retrieve per query

# --- Retrieval mode (Week 4: hybrid search) ---
# "vector" = FAISS only, "hybrid" = keyword + vector (MongoDB text index + FAISS)
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "vector")