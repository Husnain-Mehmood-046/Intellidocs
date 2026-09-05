"""
MCP tool implementations (Day 10-11).

Why separate tool implementations from the MCP server?
- Tools are plain Python functions that can be unit tested independently.
- The MCP server is just a thin wrapper that exposes these functions via the MCP protocol.
- This separation keeps business logic decoupled from transport concerns.
"""

import requests
from typing import List, Dict, Any
from pathlib import Path

from . import config
from .ingestion import load_document, split_documents
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


def search_documents(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Search for relevant document chunks using hybrid search (keyword + vector).
    
    Respects RETRIEVAL_MODE config: "vector" for FAISS only, "hybrid" for keyword+vector.

    Args:
        query: The search query string.
        top_k: Number of top results to return (default: 4).

    Returns:
        List of dicts with keys: source, chunk_index, text, metadata.
    """
    from .hybrid_search import hybrid_retrieve
    
    # Use hybrid search which respects RETRIEVAL_MODE config
    chunks = hybrid_retrieve(query, top_k)
    
    # Format results to match expected output format
    results = []
    for i, chunk in enumerate(chunks):
        results.append({
            "source": chunk["metadata"].get("source", "unknown"),
            "chunk_index": chunk["metadata"].get("chunk_index", i),
            "text": chunk["text"],
            "metadata": chunk["metadata"],
        })

    return results


def fetch_web_page(url: str, timeout: int = 10) -> str:
    """
    Fetch and extract clean text from a web page.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds (default: 10).

    Returns:
        Cleaned text content of the page.

    Raises:
        ValueError: If URL is not in the allow-list.
        requests.RequestException: If the request fails.
    """
    # Simple allow-list for security - only allow HTTP/HTTPS
    if not url.startswith(("http://", "https://")):
        raise ValueError("Only HTTP/HTTPS URLs are allowed")

    # Block private/internal IPs (SSRF protection)
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    
    # Blocked hosts and patterns
    blocked_hosts = {
        "localhost", "127.0.0.1", "0.0.0.0", "::1",
        "169.254.169.254",  # AWS/GCP/Azure metadata service
    }
    blocked_prefixes = ("192.168.", "10.", "172.", "169.254.", "fc00:", "fd00:")
    
    if hostname in blocked_hosts or hostname.startswith(blocked_prefixes):
        raise ValueError("Access to local/private addresses is not allowed")

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    # Basic HTML text extraction (for production, use beautifulsoup4 or trafilatura)
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.ignore = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self.ignore = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript"):
                self.ignore = False

        def handle_data(self, data):
            if not self.ignore:
                self.text_parts.append(data)

    extractor = TextExtractor()
    extractor.feed(response.text)
    text = " ".join(extractor.text_parts)

    # Clean up whitespace
    import re
    text = re.sub(r"\s+", " ", text).strip()

    return text[:10000]  # Limit to 10k chars to avoid token overflow


def lookup_metadata(filename: str) -> Dict[str, Any]:
    """
    Look up metadata about an ingested document from the vector store.

    Args:
        filename: The name of the file to look up (e.g., "report.pdf").

    Returns:
        Dict with metadata: chunk_count, upload_date (first chunk's timestamp),
        source_path, and any other stored metadata.
    """
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    vector_store_path = Path(config.CHROMA_DIR)

    if not vector_store_path.exists():
        return {"error": "Vector store not found", "filename": filename}

    vector_store = FAISS.load_local(
        str(vector_store_path), embeddings, allow_dangerous_deserialization=True
    )

    # FAISS doesn't have a direct "get by metadata" method, so we search
    # for the filename in the metadata. We'll do a broad search and filter.
    # Note: This is a limitation of FAISS; Chroma would be better for this.
    all_docs = vector_store.similarity_search(filename, k=100)

    matching_chunks = [
        doc for doc in all_docs
        if filename.lower() in doc.metadata.get("source", "").lower()
    ]

    if not matching_chunks:
        return {"error": "Document not found", "filename": filename}

    # Aggregate metadata
    chunk_count = len(matching_chunks)
    sources = set(doc.metadata.get("source", "") for doc in matching_chunks)
    first_chunk = matching_chunks[0]

    return {
        "filename": filename,
        "chunk_count": chunk_count,
        "sources": list(sources),
        "first_chunk_metadata": first_chunk.metadata,
        "sample_text": first_chunk.page_content[:200] + "..." if len(first_chunk.page_content) > 200 else first_chunk.page_content,
    }