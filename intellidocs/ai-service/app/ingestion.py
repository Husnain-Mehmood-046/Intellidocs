"""Document ingestion pipeline (Day 3-4).

Why a dedicated ingestion module?
- Ingestion (load -> split -> embed -> store) is a distinct, testable unit
  from the query-time RAG chain. Keeping them separate means we can re-ingest
  documents without touching the answer-generation code, and vice versa.
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config
5

def load_document(file_path: str):
    """Load a .pdf or .txt file into LangChain Document objects."""
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        loader = PyPDFLoader(str(path))
    else:
        loader = TextLoader(str(path), encoding="utf-8")
    return loader.load()


def split_documents(documents, chunk_size: int = 500, chunk_overlap: int = 50):
    """
    Split documents into overlapping chunks.

    Why overlap? A sentence that straddles a chunk boundary would otherwise be
    cut in half, losing meaning. Overlap lets each chunk carry a little context
    from its neighbours so retrieval stays coherent.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(documents)


def ingest_document(file_path: str) -> int:
    """
    Full ingestion: load -> split -> embed -> store.

    Returns the number of chunks stored.
    """
    # Load and split
    documents = load_document(file_path)
    chunks = split_documents(documents)

    # Initialize embeddings
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)

    # Load existing vector store or create a new one
    vector_store_path = Path(config.CHROMA_DIR)
    if vector_store_path.exists():
        vector_store = FAISS.load_local(str(vector_store_path), embeddings, allow_dangerous_deserialization=True)
        vector_store.add_documents(chunks)
    else:
        vector_store = FAISS.from_documents(chunks, embeddings)

    # Save the vector store
    vector_store.save_local(str(vector_store_path))

    return len(chunks)