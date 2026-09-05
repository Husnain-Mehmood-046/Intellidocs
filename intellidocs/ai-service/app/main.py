"""
FastAPI entry point for the AI microservice.

Why a separate microservice?
- ML dependencies (PyTorch, transformers) are heavy and slow to install.
  Keeping them out of the Node backend means the Express server stays
  lightweight and can be deployed/scaled independently.
- The AI service owns the embedding model and vector store, exposing a
  clean REST interface (/health, /ingest, /query) to the rest of the app.
"""
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import os

from . import config
from .ingestion import ingest_document


def convert_numpy_types(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    
    This handles numpy.float32, numpy.int64, numpy.bool_, etc. that can appear
    in LLM structured outputs and cause serialization errors.
    """
    try:
        import numpy as np
    except ImportError:
        return obj
    
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    return obj


app = FastAPI(title="IntelliDocs AI Service", version="0.1.0")

# CORS configuration - allow specific origins in production
# Set ALLOWED_ORIGINS env var as comma-separated list (e.g., "https://app.example.com,https://admin.example.com")
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness check used by the frontend/backend to confirm connectivity."""
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    """
    Ingest a document (PDF or TXT) into the vector store.

    Why a dedicated endpoint?
    - Keeps ingestion logic separate from query logic.
    - Allows the frontend/backend to trigger ingestion without knowing
      the internal details of the vector store.
    """
    # Save the uploaded file to the data directory
    data_dir = Path(config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ingest the document
    try:
        chunk_count = ingest_document(str(file_path))
        return JSONResponse(
            status_code=200,
            content={"message": "Document ingested successfully", "chunks": chunk_count},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"Error ingesting document: {str(e)}"},
        )


from .rag_chain import answer_question
from .schemas import Answer
from .agent_graph import run_agent
from .tracing import trace_graph_execution, is_tracing_enabled, tag_live_traffic


@app.post("/query")
async def query(request: dict):
    """
    Answer a question using the RAG chain with structured output (legacy endpoint).

    Expects: {"question": "..."}
    Returns: {"answer": "...", "citations": [...], "confidence": "high|medium|low"}
    
    Validation failures are retried once, then fall back to a plain-text error response.
    """
    question = request.get("question", "").strip()
    if not question:
        return JSONResponse(
            status_code=400,
            content={"message": "Question is required"},
        )

    # Try once, then retry once on validation error
    for attempt in range(2):
        try:
            result = answer_question(question)
            return JSONResponse(status_code=200, content=result.model_dump())
        except FileNotFoundError:
            return JSONResponse(
                status_code=404,
                content={"message": "No documents ingested yet. Upload a document first."},
            )
        except Exception as e:
            # If this is the last attempt, return error
            if attempt == 1:
                return JSONResponse(
                    status_code=500,
                    content={"message": f"Error answering question after retry: {str(e)}"},
                )
            # Otherwise, log and retry
            import logging
            logging.warning(f"Query attempt {attempt + 1} failed, retrying: {e}")
            continue


@app.post("/agent/query")
async def agent_query(request: dict):
    """
    Answer a question using the full LangGraph agent (Week 3).

    Expects: {"question": "...", "thread_id": "optional-conversation-id"}
    Returns: 
      - If RAG/tool path: {"answer": "...", "citations": [...], "confidence": "...", "route": "rag|tool"}
      - If clarify path: {"clarification": "...", "route": "clarify"}
    
    The agent decides whether to:
    - Use RAG (search ingested documents)
    - Call a tool (search_documents, fetch_web_page, lookup_metadata)
    - Ask for clarification (ambiguous question)
    """
    question = request.get("question", "").strip()
    thread_id = request.get("thread_id", "default")
    
    if not question:
        return JSONResponse(
            status_code=400,
            content={"message": "Question is required"},
        )

    try:
        # Run the agent graph with tracing
        initial_state = {
            "question": question,
            "route": "rag",
            "retrieved_chunks": [],
            "rag_answer": None,
            "tool_name": None,
            "tool_args": None,
            "tool_result": None,
            "tool_answer": None,
            "clarification_question": None,
            "history": [],
            "final_answer": None,
            "final_clarification": None,
            "metadata": {},
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Use tracing if enabled
        if is_tracing_enabled():
            final_state = trace_graph_execution(
                run_agent.__globals__["get_agent_graph"](), 
                initial_state, 
                config
            )
            tag_live_traffic()
        else:
            final_state = run_agent(question, thread_id)
        
        # Build response based on route
        route = final_state.get("route", "rag")
        
        if route == "clarify":
            response = {
                "clarification": final_state.get("final_clarification"),
                "route": "clarify",
            }
            return JSONResponse(status_code=200, content=convert_numpy_types(response))
        else:
            answer = final_state.get("final_answer")
            if answer:
                response = {
                    "answer": answer.answer,
                    "citations": [c.model_dump() for c in answer.citations],
                    "confidence": answer.confidence,
                    "route": route,
                }
                # Include tool info if tool was used
                if route == "tool":
                    response["tool_used"] = final_state.get("metadata", {}).get("tool_called")
                    response["tool_args"] = final_state.get("metadata", {}).get("tool_args") or final_state.get("tool_args")
                return JSONResponse(status_code=200, content=convert_numpy_types(response))
            else:
                return JSONResponse(
                    status_code=500,
                    content={"message": "Agent completed but no answer generated"},
                )
                
    except FileNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"message": "No documents ingested yet. Upload a document first."},
        )
    except Exception as e:
        import logging
        logging.error(f"Agent query error: {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Error running agent: {str(e)}"},
        )