#!/usr/bin/env python
"""
Generate a domain-specific Q&A fine-tuning dataset from ingested documents.

Why this script?
- Fine-tuning needs supervised examples (instruction + input + output).
- We generate these by asking an LLM to create Q&A pairs grounded in each
  document chunk, ensuring the training data matches our domain.
- Output format: JSONL with {"instruction": ..., "input": ..., "output": ...}
  compatible with Hugging Face `datasets` and standard SFT trainers.

Usage:
    python -m finetune.build_dataset [--num-chunks N] [--pairs-per-chunk K] [--output dataset.jsonl]

Requirements:
- Vector store must exist (run ingestion first).
- LLM_PROVIDER must be set to a capable model (groq, openai, anthropic, ollama).
"""

import json
import sys
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Set
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config
from app.rag_chain import _get_vector_store, _get_embeddings


@dataclass
class QAPair:
    """A single question-answer pair for fine-tuning."""
    instruction: str
    input: str
    output: str
    source_chunk: str
    chunk_metadata: Dict[str, Any]


def load_all_chunks() -> List[Dict[str, Any]]:
    """
    Load all document chunks from the FAISS vector store.
    
    Returns:
        List of dicts with 'text', 'metadata', and 'id' keys.
    """
    vector_store = _get_vector_store()
    
    # FAISS doesn't have a direct "get all" method, so we do a broad search
    # with a generic query and high k to retrieve most chunks.
    # Note: This is a limitation of FAISS; for production, consider Chroma or
    # storing chunks in a separate JSONL file during ingestion.
    docs = vector_store.similarity_search("", k=10000)
    
    chunks = []
    for i, doc in enumerate(docs):
        chunks.append({
            "id": i,
            "text": doc.page_content,
            "metadata": doc.metadata,
        })
    
    return chunks


def generate_qa_pairs_for_chunk(
    chunk_text: str,
    chunk_metadata: Dict[str, Any],
    num_pairs: int = 2,
    llm_provider: str = "groq"
) -> List[QAPair]:
    """
    Use an LLM to generate question/answer pairs grounded in a chunk.
    
    Args:
        chunk_text: The text content of the chunk.
        chunk_metadata: Metadata dict (source, chunk_index, etc.).
        num_pairs: Number of Q&A pairs to generate (1-3).
        llm_provider: Which LLM to use for generation.
    
    Returns:
        List of QAPair objects.
    """
    from app.llm import generate
    
    # Truncate chunk if too long (leave room for prompt + response)
    max_chunk_len = 2000
    if len(chunk_text) > max_chunk_len:
        chunk_text = chunk_text[:max_chunk_len] + "..."
    
    prompt = f"""You are creating a fine-tuning dataset for a document Q&A assistant.
Given the following document chunk, generate {num_pairs} diverse question-answer pairs
that a user might ask about this content.

Requirements:
- Questions should be natural and varied (factual, summary, inference, etc.)
- Answers MUST be grounded ONLY in the provided chunk - do not hallucinate.
- If the chunk doesn't contain enough info for a question, don't generate it.
- Format each pair as a JSON object with "question" and "answer" fields.

Document chunk:
---
{chunk_text}
---

Source: {chunk_metadata.get('source', 'unknown')}

Output {num_pairs} JSON objects, one per line:"""
    
    try:
        response = generate(prompt)
        
        # Parse JSONL response
        pairs = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                question = data.get("question", "").strip()
                answer = data.get("answer", "").strip()
                if question and answer:
                    pairs.append(QAPair(
                        instruction="Answer the question based on the provided context.",
                        input=question,
                        output=answer,
                        source_chunk=chunk_text[:500],  # Store preview for debugging
                        chunk_metadata=chunk_metadata,
                    ))
            except json.JSONDecodeError:
                continue
        
        return pairs[:num_pairs]
    
    except Exception as e:
        print(f"Error generating QA pairs: {e}")
        return []


def deduplicate_pairs(pairs: List[QAPair]) -> List[QAPair]:
    """
    Remove duplicate or near-duplicate Q&A pairs.
    
    Uses a simple hash of (instruction + input) for exact dedup,
    and could be extended with semantic similarity for near-dedup.
    """
    seen: Set[str] = set()
    unique = []
    
    for pair in pairs:
        # Create a hash key from instruction + input (normalized)
        key = hashlib.md5(
            (pair.instruction.lower().strip() + "||" + pair.input.lower().strip()).encode()
        ).hexdigest()
        
        if key not in seen:
            seen.add(key)
            unique.append(pair)
    
    return unique


def filter_quality(pairs: List[QAPair], min_answer_len: int = 20) -> List[QAPair]:
    """
    Filter out low-quality pairs (too short, generic, etc.).
    """
    filtered = []
    for pair in pairs:
        # Skip if answer is too short (likely "I don't know" or similar)
        if len(pair.output) < min_answer_len:
            continue
        
        # Skip if answer contains refusal phrases
        refusal_phrases = [
            "i don't know", "i cannot", "not mentioned", "not in the",
            "no information", "cannot answer", "insufficient"
        ]
        output_lower = pair.output.lower()
        if any(phrase in output_lower for phrase in refusal_phrases):
            continue
        
        filtered.append(pair)
    
    return filtered


def save_dataset(pairs: List[QAPair], output_path: Path):
    """Save Q&A pairs to JSONL file in instruction-tuning format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for pair in pairs:
            # Standard instruction-tuning format
            record = {
                "instruction": pair.instruction,
                "input": pair.input,
                "output": pair.output,
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    print(f"Saved {len(pairs)} pairs to {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build fine-tuning dataset from ingested documents")
    parser.add_argument("--num-chunks", type=int, default=None,
                        help="Max number of chunks to process (default: all)")
    parser.add_argument("--pairs-per-chunk", type=int, default=2,
                        help="Number of Q&A pairs per chunk (1-3, default: 2)")
    parser.add_argument("--output", type=str, default="dataset.jsonl",
                        help="Output JSONL file path (default: dataset.jsonl)")
    parser.add_argument("--min-pairs", type=int, default=150,
                        help="Minimum target dataset size (default: 150)")
    args = parser.parse_args()
    
    output_path = Path(__file__).parent / args.output
    
    print("=" * 60)
    print("Building fine-tuning dataset from ingested documents")
    print("=" * 60)
    
    # Load chunks
    print("\n[1/4] Loading document chunks from vector store...")
    chunks = load_all_chunks()
    print(f"       Found {len(chunks)} chunks")
    
    if not chunks:
        print("ERROR: No chunks found. Run ingestion first (POST /ingest).")
        sys.exit(1)
    
    # Limit chunks if requested
    if args.num_chunks:
        chunks = chunks[:args.num_chunks]
        print(f"       Processing first {len(chunks)} chunks")
    
    # Generate Q&A pairs
    print(f"\n[2/4] Generating Q&A pairs ({args.pairs_per_chunk} per chunk)...")
    all_pairs = []
    for i, chunk in enumerate(chunks):
        if i % 10 == 0:
            print(f"       Processing chunk {i+1}/{len(chunks)}...")
        
        pairs = generate_qa_pairs_for_chunk(
            chunk["text"],
            chunk["metadata"],
            num_pairs=args.pairs_per_chunk,
        )
        all_pairs.extend(pairs)
    
    print(f"       Generated {len(all_pairs)} raw pairs")
    
    # Deduplicate
    print("\n[3/4] Deduplicating...")
    all_pairs = deduplicate_pairs(all_pairs)
    print(f"       After dedup: {len(all_pairs)} pairs")
    
    # Quality filter
    print("\n[4/4] Quality filtering...")
    all_pairs = filter_quality(all_pairs)
    print(f"       After filtering: {len(all_pairs)} pairs")
    
    # Check minimum size
    if len(all_pairs) < args.min_pairs:
        print(f"\n⚠️  WARNING: Dataset size ({len(all_pairs)}) is below target ({args.min_pairs})")
        print("   Options to increase dataset size:")
        print("   - Ingest more documents (run POST /ingest with more files)")
        print("   - Increase --pairs-per-chunk (try 3)")
        print("   - Process more chunks (remove --num-chunks limit)")
        print("   - Use a more capable LLM for generation (Groq/OpenAI vs Ollama)")
        
        # Ask user if they want to continue
        response = input(f"\nContinue with {len(all_pairs)} pairs? [y/N]: ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(1)
    
    # Save
    save_dataset(all_pairs, output_path)
    
    # Print stats
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"Total pairs: {len(all_pairs)}")
    print(f"Unique sources: {len(set(p.chunk_metadata.get('source') for p in all_pairs))}")
    avg_q_len = sum(len(p.input) for p in all_pairs) / len(all_pairs) if all_pairs else 0
    avg_a_len = sum(len(p.output) for p in all_pairs) / len(all_pairs) if all_pairs else 0
    print(f"Avg question length: {avg_q_len:.0f} chars")
    print(f"Avg answer length: {avg_a_len:.0f} chars")
    print(f"Output: {output_path}")
    print("\nNext step: Run training with `python -m finetune.train_lora`")


if __name__ == "__main__":
    main()