#!/usr/bin/env python
"""
Hybrid search: keyword (text) + vector search with reciprocal rank fusion.

Why hybrid search?
- Pure vector search (embeddings) excels at semantic similarity but can miss
  exact keyword matches, proper nouns, acronyms, and rare terms.
- Pure keyword search (BM25/text index) excels at exact matches but misses
  semantic relationships and synonyms.
- Hybrid combines both: vector for semantic, keyword for exact, merged with RRF.

Two implementations:
1. **MongoDB Atlas (production)**: Atlas Search (Lucene) + Atlas Vector Search
   - Managed, scalable, single query combines both
   - Requires Atlas cluster (not free tier for vector search)
   
2. **Local MongoDB (development fallback)**: MongoDB text index + FAISS vector store
   - Separate queries, merged in Python with RRF
   - Works with local MongoDB, no Atlas required
   - Flagged as "local-dev equivalent" - not production Atlas setup

Usage:
    from app.hybrid_search import hybrid_retrieve
    
    chunks = hybrid_retrieve("machine learning", top_k=4)
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from . import config
from .rag_chain import _get_vector_store, _get_embeddings


def reciprocal_rank_fusion(
    results_list: List[List[Dict[str, Any]]],
    k: int = 60,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion (RRF).
    
    RRF formula: score = sum(1 / (k + rank_i)) for each result list i
    where rank_i is the 1-based position in list i.
    
    Why RRF?
    - Parameter-free (k=60 is standard default)
    - Works with any number of result lists
    - Robust to different score scales (vector cosine vs BM25)
    - Proven effective in IR literature (Cormack et al., 2009)
    
    Args:
        results_list: List of result lists, each sorted by relevance (best first)
        k: RRF constant (default 60)
        top_k: Number of final results to return
    
    Returns:
        Merged and re-ranked results with 'rrf_score' added
    """
    # Collect all unique documents with their ranks in each list
    doc_scores = {}  # doc_id -> {list_idx: rank}
    
    for list_idx, results in enumerate(results_list):
        for rank, doc in enumerate(results, 1):
            # Create a unique ID for the document
            doc_id = doc.get("metadata", {}).get("source", "") + "_" + str(doc.get("metadata", {}).get("chunk_index", rank))
            if not doc_id or doc_id == "_":
                doc_id = f"doc_{list_idx}_{rank}"
            
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {"doc": doc, "ranks": {}}
            doc_scores[doc_id]["ranks"][list_idx] = rank
    
    # Calculate RRF scores
    for doc_id, data in doc_scores.items():
        rrf_score = 0.0
        for list_idx, rank in data["ranks"].items():
            rrf_score += 1.0 / (k + rank)
        data["rrf_score"] = rrf_score
    
    # Sort by RRF score descending
    sorted_docs = sorted(doc_scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    
    # Return top_k with rrf_score in metadata
    final_results = []
    for data in sorted_docs[:top_k]:
        doc = data["doc"].copy()
        if "metadata" not in doc:
            doc["metadata"] = {}
        doc["metadata"]["rrf_score"] = data["rrf_score"]
        doc["metadata"]["retrieval_method"] = "hybrid_rrf"
        final_results.append(doc)
    
    return final_results


def keyword_search_local_mongodb(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Keyword search using local MongoDB text index.
    
    This is the LOCAL FALLBACK implementation - not MongoDB Atlas Search.
    Requires a text index on the 'text' field in the chunks collection.
    
    Setup (run once):
        db.chunks.createIndex({ "text": "text" })
    
    Args:
        query: Search query string
        top_k: Number of results to return
    
    Returns:
        List of chunks with 'text', 'metadata', and 'score' (BM25 score)
    """
    try:
        from pymongo import MongoClient
        from pymongo.errors import OperationFailure
    except ImportError:
        print("WARNING: pymongo not installed. Keyword search unavailable.")
        return []
    
    # Get MongoDB URI from environment
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/intellidocs")
    
    try:
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        chunks_collection = db["chunks"]
        
        # Check if text index exists, create if not
        indexes = list(chunks_collection.list_indexes())
        has_text_index = any("text" in str(idx.get("key", {})) for idx in indexes)
        
        if not has_text_index:
            print("Creating MongoDB text index on 'text' field...")
            chunks_collection.create_index([("text", "text")])
        
        # Perform text search
        cursor = chunks_collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(top_k)
        
        results = []
        for doc in cursor:
            results.append({
                "text": doc.get("text", ""),
                "metadata": {
                    "source": doc.get("source", "unknown"),
                    "chunk_index": doc.get("chunk_index", 0),
                    "mongodb_id": str(doc.get("_id", "")),
                    "bm25_score": doc.get("score", 0),
                },
                "score": doc.get("score", 0),
            })
        
        client.close()
        return results
        
    except Exception as e:
        print(f"WARNING: MongoDB keyword search failed: {e}")
        return []


def vector_search_faiss(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Vector search using existing FAISS store.
    
    Reuses the existing FAISS vector store from rag_chain.py.
    
    Args:
        query: Search query string
        top_k: Number of results to return
    
    Returns:
        List of chunks with 'text', 'metadata', and 'score' (cosine similarity)
    """
    try:
        vector_store = _get_vector_store()
        docs = vector_store.similarity_search_with_score(query, k=top_k)
        
        results = []
        for doc, score in docs:
            # FAISS returns distance (lower = more similar), convert to similarity
            # Convert numpy types to Python native types for JSON serialization
            score = float(score) if hasattr(score, 'item') else float(score)
            similarity = 1.0 / (1.0 + score) if score >= 0 else 1.0
            similarity = float(similarity)
            results.append({
                "text": doc.page_content,
                "metadata": {
                    **doc.metadata,
                    "vector_score": similarity,
                    "vector_distance": score,
                },
                "score": similarity,
            })
        
        return results
        
    except Exception as e:
        print(f"WARNING: FAISS vector search failed: {e}")
        return []


def hybrid_retrieve(
    query: str,
    top_k: int = 4,
    retrieval_mode: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Main hybrid retrieval function.
    
    Combines keyword and vector search based on RETRIEVAL_MODE config.
    
    Args:
        query: Search query
        top_k: Final number of results to return
        retrieval_mode: Override config.RETRIEVAL_MODE ("vector" | "hybrid")
    
    Returns:
        List of chunks with merged/re-ranked results
    """
    mode = retrieval_mode or config.RETRIEVAL_MODE
    
    if mode == "vector":
        # Pure vector search (existing behavior)
        print(f"[Hybrid Search] Mode: vector-only")
        return vector_search_faiss(query, top_k)
    
    elif mode == "hybrid":
        print(f"[Hybrid Search] Mode: hybrid (keyword + vector)")
        
        # Run both searches in parallel (sequential here for simplicity)
        # In production, use asyncio or threading for true parallelism
        keyword_results = keyword_search_local_mongodb(query, top_k * 2)
        vector_results = vector_search_faiss(query, top_k * 2)
        
        print(f"  Keyword results: {len(keyword_results)}")
        print(f"  Vector results: {len(vector_results)}")
        
        if not keyword_results and not vector_results:
            return []
        
        if not keyword_results:
            print("  No keyword results, returning vector only")
            return vector_results[:top_k]
        
        if not vector_results:
            print("  No vector results, returning keyword only")
            return keyword_results[:top_k]
        
        # Merge with RRF
        merged = reciprocal_rank_fusion(
            [keyword_results, vector_results],
            k=60,
            top_k=top_k
        )
        
        print(f"  Merged results: {len(merged)}")
        return merged
    
    else:
        raise ValueError(f"Unknown RETRIEVAL_MODE: {mode}. Use 'vector' or 'hybrid'.")


def hybrid_retrieve_atlas(
    query: str,
    top_k: int = 4,
    mongodb_uri: Optional[str] = None,
    database: str = "intellidocs",
    collection: str = "chunks",
    vector_index: str = "vector_index",
    search_index: str = "search_index",
) -> List[Dict[str, Any]]:
    """
    Hybrid search using MongoDB Atlas Search + Atlas Vector Search (PRODUCTION).
    
    This is the TRUE Atlas implementation - single query, server-side fusion.
    Requires:
    - MongoDB Atlas cluster (M10+ for vector search)
    - Atlas Search index named `search_index` on `text` field
    - Atlas Vector Search index named `vector_index` on `embedding` field
    
    Args:
        query: Search query
        top_k: Number of results
        mongodb_uri: Atlas connection string (from env if not provided)
        database: Database name
        collection: Collection name
        vector_index: Atlas Vector Search index name
        search_index: Atlas Search index name
    
    Returns:
        List of chunks with 'text', 'metadata', 'score'
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        print("ERROR: pymongo required for Atlas hybrid search")
        return []
    
    uri = mongodb_uri or os.getenv("MONGODB_URI")
    if not uri or "mongodb.net" not in uri:
        print("ERROR: Atlas hybrid search requires MongoDB Atlas URI (mongodb+srv://...)")
        print("Falling back to local hybrid search...")
        return hybrid_retrieve(query, top_k, "hybrid")
    
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        db = client[database]
        coll = db[collection]
        
        # Atlas hybrid search pipeline
        # Uses $search with compound: text + knnBeta
        pipeline = [
            {
                "$search": {
                    "compound": {
                        "should": [
                            {
                                "text": {
                                    "query": query,
                                    "path": "text",
                                    "score": {"boost": {"value": 1}}
                                }
                            },
                            {
                                "knnBeta": {
                                    "vector": _get_embeddings().embed_query(query),
                                    "path": "embedding",
                                    "k": top_k * 2,
                                    "score": {"boost": {"value": 1}}
                                }
                            }
                        ]
                    }
                }
            },
            {"$limit": top_k},
            {
                "$project": {
                    "text": 1,
                    "metadata": 1,
                    "score": {"$meta": "searchScore"}
                }
            }
        ]
        
        results = list(coll.aggregate(pipeline))
        client.close()
        
        formatted = []
        for doc in results:
            formatted.append({
                "text": doc.get("text", ""),
                "metadata": {
                    **doc.get("metadata", {}),
                    "source": doc.get("metadata", {}).get("source", "unknown"),
                    "chunk_index": doc.get("metadata", {}).get("chunk_index", 0),
                    "atlas_score": doc.get("score", 0),
                    "retrieval_method": "atlas_hybrid",
                },
                "score": doc.get("score", 0),
            })
        
        return formatted
        
    except Exception as e:
        print(f"ERROR: Atlas hybrid search failed: {e}")
        print("Falling back to local hybrid search...")
        return hybrid_retrieve(query, top_k, "hybrid")


# Convenience function for the RAG chain
def retrieve(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for rag_chain.retrieve() that uses hybrid search
    when RETRIEVAL_MODE=hybrid.
    """
    return hybrid_retrieve(query, top_k)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test hybrid search")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--top-k", type=int, default=4, help="Number of results")
    parser.add_argument("--mode", type=str, choices=["vector", "hybrid"], default=None, help="Override retrieval mode")
    args = parser.parse_args()
    
    print(f"Query: {args.query}")
    print(f"Mode: {args.mode or config.RETRIEVAL_MODE}")
    print("-" * 60)
    
    results = hybrid_retrieve(args.query, args.top_k, args.mode)
    
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] Score: {r.get('metadata', {}).get('rrf_score', r.get('score', 0)):.4f}")
        print(f"    Source: {r.get('metadata', {}).get('source', 'unknown')}")
        print(f"    Chunk: {r.get('metadata', {}).get('chunk_index', 0)}")
        print(f"    Text: {r['text'][:200]}...")