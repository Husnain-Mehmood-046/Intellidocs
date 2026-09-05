"""
Pydantic schemas for structured outputs (Day 8-9).

Why Pydantic models instead of raw dicts?
- They give us a single source of truth for the shape of our API responses.
- FastAPI can validate/serialize them automatically, so a malformed response
  from the LLM is caught before it reaches the client.
- They document the contract between the AI service, the Express server, and
  the React frontend in one place.

Why a separate `schemas.py` instead of defining models inline?
- `rag_chain.py` (retrieval + generation) and `main.py` (HTTP layer) both need
  these types. A shared module avoids circular imports and keeps the contract
  in one obvious location.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """
    A single source citation for a claim in the answer.

    - `source`: the document the chunk came from (e.g. "data/report.pdf").
    - `chunk_index`: which chunk within that document (0-based).
    - `excerpt`: the actual text of the retrieved chunk, so the user can verify
      the answer against the source without re-opening the document.
    """

    source: str = Field(..., description="Document path the chunk came from")
    chunk_index: int = Field(..., description="0-based index of the chunk in the document")
    excerpt: str = Field(..., description="The retrieved chunk text used to ground the answer")


class Answer(BaseModel):
    """
    The structured answer returned by the RAG pipeline.

    - `answer`: the natural-language response to the user's question.
    - `citations`: the chunks that grounded the answer (may be empty if no
      relevant chunks were found).
    - `confidence`: a coarse confidence label. Using a `Literal` (rather than a
      float) makes the LLM's job easier — it only has to pick one of three
      words, which is far more reliable than emitting a calibrated number.
    """

    answer: str = Field(..., description="The generated answer text")
    citations: list[Citation] = Field(default_factory=list, description="Source chunks that grounded the answer")
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium", description="Coarse confidence label for the answer"
    )