"""
RAG chain: retrieve relevant chunks and generate a grounded answer (Day 5-6).

Why a separate module?
- The retrieval + generation logic is the heart of the system and changes
  often (prompt tweaks, top-k tuning, provider swaps). Isolating it keeps
  those changes from leaking into the HTTP layer (main.py).
"""

from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from . import config
from . import llm
from .schemas import Answer, Citation

# Module-level caches to avoid reloading embeddings and vector store on every call
_embeddings = None
_vector_store = None


def _get_embeddings():
    """Get cached embeddings instance."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    return _embeddings


def _get_vector_store():
    """Get cached vector store instance."""
    global _vector_store
    if _vector_store is None:
        vector_store_path = Path(config.CHROMA_DIR)
        if not vector_store_path.exists():
            raise FileNotFoundError(f"Vector store not found at {vector_store_path}")
        _vector_store = FAISS.load_local(str(vector_store_path), _get_embeddings(), allow_dangerous_deserialization=True)
    return _vector_store


def retrieve(query: str, top_k: int = 4):
    """
    Retrieve the top-k most relevant chunks for a query.
    
    Uses hybrid search (keyword + vector) when RETRIEVAL_MODE=hybrid,
    otherwise falls back to pure FAISS vector search.
    
    Why hybrid search?
    - Pure vector search excels at semantic similarity but misses exact keywords
    - Pure keyword search excels at exact matches but misses semantic relationships
    - Hybrid combines both via Reciprocal Rank Fusion (RRF)
    """
    # Use hybrid search module which respects RETRIEVAL_MODE config
    from .hybrid_search import hybrid_retrieve
    return hybrid_retrieve(query, top_k)


def generate_answer(query: str, context_chunks) -> Answer:
    """
    Build a prompt from retrieved chunks and call the LLM with structured output.

    Returns an `Answer` Pydantic model with answer, citations, and confidence.

    Why structured output (with_structured_output) instead of "return JSON" in prompt?
    - The LLM provider's native function-calling/structured-output API enforces
      the schema at the token level, not just via prompt instructions.
    - This eliminates hallucinated fields, missing required fields, and type mismatches.
    - LangChain's `with_structured_output` abstracts provider differences (OpenAI,
      Anthropic, Groq, etc.) so we write the schema once and it works everywhere.
    """
    # Build the context string from chunks
    context_text = "\n\n".join([
        f"[Chunk {i}] Source: {chunk['metadata'].get('source', 'unknown')}\n{chunk['text']}"
        for i, chunk in enumerate(context_chunks)
    ])

    # Create the prompt template - no format_instructions needed since with_structured_output handles schema
    prompt_template = PromptTemplate(
        template="""You are a helpful assistant that answers questions based on the provided context.

Context:
{context}

Question: {question}

Answer the question based only on the provided context. If the context doesn't contain enough information, say so.""",
        input_variables=["context", "question"],
    )

    # Get the LLM with structured output
    structured_llm = llm.get_structured_llm(Answer)
    
    # Create the chain
    chain = prompt_template | structured_llm
    
    # Invoke the chain
    result = chain.invoke({"context": context_text, "question": query})
    
    return result


def answer_query(query: str) -> dict:
    """End-to-end: retrieve -> generate -> return answer + sources."""
    chunks = retrieve(query)
    return generate_answer(query, chunks)


def answer_question(query: str) -> Answer:
    """
    End-to-end structured answer: retrieve -> generate -> wrap in an `Answer`.

    This is the public entry point used by the HTTP layer. It returns a
    Pydantic `Answer` (answer + citations + confidence) rather than a raw dict,
    so the API response is self-describing and easy to validate.

    Confidence heuristic:
    - "high"   -> at least 3 retrieved chunks (strong grounding).
    - "medium" -> 1-2 retrieved chunks (partial grounding).
    - "low"    -> no chunks retrieved (the LLM is answering from memory only).
    """
    chunks = retrieve(query)

    if not chunks:
        return Answer(
            answer="I couldn't find any relevant information in the knowledge base to answer that question.",
            citations=[],
            confidence="low",
        )

    result = generate_answer(query, chunks)

    citations = [
        Citation(
            source=chunk["metadata"].get("source", "unknown"),
            chunk_index=chunk["metadata"].get("chunk_index", 0),
            excerpt=chunk["text"],
        )
        for chunk in chunks
    ]

    if len(chunks) >= 3:
        confidence = "high"
    else:
        confidence = "medium"

    return Answer(
        answer=result.answer,
        citations=citations,
        confidence=confidence,
    )