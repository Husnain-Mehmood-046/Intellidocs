#!/usr/bin/env python
"""
LLM Benchmark Script (Day 12-13).

This script runs the same test questions against both the hosted API
and local Ollama backends, comparing latency, schema validation success,
and allowing manual quality comparison.

Run with: `python scripts/benchmark_llm.py`

Prerequisites:
- For API backend: Set LLM_PROVIDER=groq (or openai/anthropic) and API keys in .env
- For Ollama backend: Install Ollama, pull a model (e.g., `ollama pull llama3.1:8b`),
  and set LLM_PROVIDER=ollama in .env
"""

import os
import sys
import time
import json
from pathlib import Path

# Add the ai-service directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL
from app.rag_chain import answer_question
from app.schemas import Answer


# Test questions for benchmarking
TEST_QUESTIONS = [
    "What is IntelliDocs?",
    "How does the document ingestion process work?",
    "What vector store does IntelliDocs use?",
    "Explain the RAG chain architecture.",
    "What are the main components of the IntelliDocs system?",
]


def run_benchmark(provider_name: str, questions: list) -> list:
    """
    Run benchmark for a specific provider.
    
    Returns list of results with: question, answer, latency, validation_success, error
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking {provider_name}")
    print(f"{'='*60}")
    
    results = []
    
    for i, question in enumerate(questions, 1):
        print(f"\nQuestion {i}/{len(questions)}: {question}")
        
        start_time = time.time()
        try:
            result = answer_question(question)
            latency = time.time() - start_time
            
            # Validate against Answer schema
            try:
                validated = Answer.model_validate(result.model_dump())
                validation_success = True
                validation_error = None
            except Exception as e:
                validation_success = False
                validation_error = str(e)
            
            result_data = {
                "question": question,
                "answer": result.answer,
                "citations_count": len(result.citations),
                "confidence": result.confidence,
                "latency_seconds": round(latency, 3),
                "validation_success": validation_success,
                "validation_error": validation_error,
            }
            
            print(f"  Latency: {latency:.3f}s")
            print(f"  Validation: {'✓' if validation_success else '✗'}")
            print(f"  Confidence: {result.confidence}")
            print(f"  Citations: {len(result.citations)}")
            print(f"  Answer preview: {result.answer[:100]}...")
            
        except Exception as e:
            latency = time.time() - start_time
            result_data = {
                "question": question,
                "answer": None,
                "citations_count": 0,
                "confidence": None,
                "latency_seconds": round(latency, 3),
                "validation_success": False,
                "validation_error": str(e),
            }
            print(f"  Error: {e}")
        
        results.append(result_data)
    
    return results


def print_comparison(api_results: list, ollama_results: list):
    """Print side-by-side comparison of results."""
    print(f"\n{'='*80}")
    print("SIDE-BY-SIDE COMPARISON")
    print(f"{'='*80}")
    
    print(f"\n{'Question':<50} | {'API Latency':>12} | {'Ollama Latency':>14} | {'API Valid':>9} | {'Ollama Valid':>12}")
    print("-" * 110)
    
    for api_r, ollama_r in zip(api_results, ollama_results):
        q = api_r["question"][:48]
        api_lat = f"{api_r['latency_seconds']:.3f}s"
        ollama_lat = f"{ollama_r['latency_seconds']:.3f}s"
        api_val = "✓" if api_r["validation_success"] else "✗"
        ollama_val = "✓" if ollama_r["validation_success"] else "✗"
        print(f"{q:<50} | {api_lat:>12} | {ollama_lat:>14} | {api_val:>9} | {ollama_val:>12}")
    
    # Summary statistics
    api_latencies = [r["latency_seconds"] for r in api_results if r["validation_success"]]
    ollama_latencies = [r["latency_seconds"] for r in ollama_results if r["validation_success"]]
    api_valid = sum(1 for r in api_results if r["validation_success"])
    ollama_valid = sum(1 for r in ollama_results if r["validation_success"])
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"API Backend ({LLM_PROVIDER}):")
    print(f"  Successful validations: {api_valid}/{len(api_results)}")
    if api_latencies:
        print(f"  Avg latency: {sum(api_latencies)/len(api_latencies):.3f}s")
        print(f"  Min latency: {min(api_latencies):.3f}s")
        print(f"  Max latency: {max(api_latencies):.3f}s")
    
    print(f"\nOllama Backend ({OLLAMA_MODEL}):")
    print(f"  Successful validations: {ollama_valid}/{len(ollama_results)}")
    if ollama_latencies:
        print(f"  Avg latency: {sum(ollama_latencies)/len(ollama_latencies):.3f}s")
        print(f"  Min latency: {min(ollama_latencies):.3f}s")
        print(f"  Max latency: {max(ollama_latencies):.3f}s")
    
    # Cost comparison
    print(f"\n{'='*80}")
    print("COST COMPARISON")
    print(f"{'='*80}")
    print("API Backend: Pay per token (varies by provider)")
    print("  - Groq: Free tier available, then pay-per-token")
    print("  - OpenAI: ~$0.15/1M input tokens, ~$0.60/1M output tokens (gpt-4o-mini)")
    print("  - Anthropic: ~$0.25/1M input tokens, ~$1.25/1M output tokens (claude-3-5-haiku)")
    print("\nOllama Backend: $0 per token (runs locally on your hardware)")
    print("  - One-time hardware cost")
    print("  - No ongoing API costs")
    print("  - Privacy: data never leaves your machine")


def save_results(api_results: list, ollama_results: list, output_file: str):
    """Save benchmark results to JSON file."""
    data = {
        "api_provider": LLM_PROVIDER,
        "ollama_model": OLLAMA_MODEL,
        "api_results": api_results,
        "ollama_results": ollama_results,
    }
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nResults saved to {output_file}")


def main():
    print("IntelliDocs LLM Benchmark")
    print("=" * 60)
    
    # Check if we can run both backends
    print(f"Current LLM_PROVIDER: {LLM_PROVIDER}")
    print(f"Ollama URL: {OLLAMA_BASE_URL}")
    print(f"Ollama Model: {OLLAMA_MODEL}")
    
    # Run API benchmark (current provider)
    print(f"\nRunning benchmark with current provider: {LLM_PROVIDER}")
    api_results = run_benchmark(LLM_PROVIDER, TEST_QUESTIONS)
    
    # For Ollama benchmark, we need to temporarily switch provider
    # This requires restarting the Python process or reloading config
    # For simplicity, we'll just note that user should run separately
    print(f"\n{'='*60}")
    print("NOTE: To benchmark Ollama, you need to:")
    print("1. Set LLM_PROVIDER=ollama in .env")
    print("2. Restart this script")
    print("3. Compare results manually")
    print(f"{'='*60}")
    
    # Save API results
    save_results(api_results, [], "benchmark_results_api.json")
    
    print("\nBenchmark complete!")
    print("Run again with LLM_PROVIDER=ollama to get Ollama results.")


if __name__ == "__main__":
    main()