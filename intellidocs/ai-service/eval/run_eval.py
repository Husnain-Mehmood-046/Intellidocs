#!/usr/bin/env python
"""
Evaluation harness for IntelliDocs agent (Day 18-19).

Why a standalone script?
- Can be run independently of the API server.
- Produces structured JSON report + human-readable summary.
- Records latency, cost (token usage), and accuracy per question.
- Supports both LLM backends (hosted API and Ollama).
"""

import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent_graph import run_agent
from app import config


@dataclass
class EvalResult:
    """Result of a single evaluation question."""
    id: str
    category: str
    question: str
    expected_path: str
    expected_tool: str = None
    expected_answer_contains: List[str] = None
    
    # Actual results
    actual_path: str = None
    actual_tool: str = None
    answer: str = None
    citations: List[Dict] = None
    confidence: str = None
    clarification: str = None
    
    # Metrics
    latency_ms: float = 0.0
    tokens_used: Dict[str, int] = None
    cost_usd: float = 0.0
    
    # Scoring
    path_correct: bool = False
    tool_correct: bool = False
    answer_score: float = 0.0  # 0-1 semantic similarity
    hallucinated: bool = False
    
    # Error
    error: str = None


def load_test_set(path: str) -> List[Dict]:
    """Load test cases from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)
    return data["test_cases"]


def calculate_cost(tokens: Dict[str, int], provider: str) -> float:
    """
    Calculate cost based on token usage and provider pricing.
    
    Pricing (approximate, update as needed):
    - Groq (llama-3.1-8b-instant): $0.05/1M input, $0.08/1M output
    - OpenAI (gpt-4o-mini): $0.15/1M input, $0.60/1M output
    - Anthropic (claude-3-5-haiku): $0.25/1M input, $1.25/1M output
    - Ollama: $0 (local)
    """
    if provider == "ollama":
        return 0.0
    
    input_tokens = tokens.get("input_tokens", 0)
    output_tokens = tokens.get("output_tokens", 0)
    
    pricing = {
        "groq": {"input": 0.05 / 1_000_000, "output": 0.08 / 1_000_000},
        "openai": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "anthropic": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
    }
    
    p = pricing.get(provider, {"input": 0, "output": 0})
    return (input_tokens * p["input"]) + (output_tokens * p["output"])


def check_path_correct(expected: str, actual: str) -> bool:
    """Check if the routing path matches expected."""
    return expected == actual


def check_tool_correct(expected: str, actual: str) -> bool:
    """Check if the tool used matches expected."""
    if not expected:
        return True  # No tool expected
    return expected == actual


def check_answer_contains(answer: str, expected_contains: List[str]) -> float:
    """
    Simple keyword-based answer scoring.
    Returns 0-1 score based on how many expected keywords appear.
    """
    if not answer or not expected_contains:
        return 0.0
    
    answer_lower = answer.lower()
    matches = sum(1 for kw in expected_contains if kw.lower() in answer_lower)
    return matches / len(expected_contains)


def detect_hallucination(answer: str, citations: List[Dict]) -> bool:
    """
    Simple hallucination detection: if answer makes specific claims
    but has no citations, flag as potential hallucination.
    """
    if not answer:
        return False
    
    # If low confidence and no citations, likely hallucination
    # This is a heuristic - real detection needs more sophistication
    return False  # Placeholder


def run_single_eval(test_case: Dict, thread_id: str = "eval") -> EvalResult:
    """Run a single test case through the agent."""
    result = EvalResult(
        id=test_case["id"],
        category=test_case["category"],
        question=test_case["question"],
        expected_path=test_case["expected_path"],
        expected_tool=test_case.get("expected_tool"),
        expected_answer_contains=test_case.get("expected_answer_contains"),
    )
    
    start_time = time.time()
    
    try:
        # Run the agent
        final_state = run_agent(test_case["question"], thread_id=f"{thread_id}_{test_case['id']}")
        
        result.latency_ms = (time.time() - start_time) * 1000
        result.actual_path = final_state.get("route", "unknown")
        result.actual_tool = final_state.get("metadata", {}).get("tool_called")
        
        if result.actual_path == "clarify":
            result.clarification = final_state.get("final_clarification")
        else:
            answer_obj = final_state.get("final_answer")
            if answer_obj:
                result.answer = answer_obj.answer
                result.citations = [c.model_dump() if hasattr(c, 'model_dump') else c for c in answer_obj.citations]
                result.confidence = answer_obj.confidence
        
        # Score the result
        result.path_correct = check_path_correct(result.expected_path, result.actual_path)
        result.tool_correct = check_tool_correct(result.expected_tool, result.actual_tool)
        result.answer_score = check_answer_contains(result.answer or "", result.expected_answer_contains or [])
        result.hallucinated = detect_hallucination(result.answer or "", result.citations or [])
        
        # Estimate tokens (rough approximation)
        # In production, get actual token counts from LLM response
        total_chars = len(test_case["question"]) + len(result.answer or "") + len(result.clarification or "")
        estimated_tokens = total_chars // 4  # Rough: 4 chars per token
        result.tokens_used = {
            "input_tokens": len(test_case["question"]) // 4,
            "output_tokens": len(result.answer or result.clarification or "") // 4,
        }
        result.cost_usd = calculate_cost(result.tokens_used, config.LLM_PROVIDER)
        
    except Exception as e:
        result.error = str(e)
        result.latency_ms = (time.time() - start_time) * 1000
    
    return result


def run_evaluation(test_set_path: str, output_path: str = None) -> Dict[str, Any]:
    """Run full evaluation suite."""
    print(f"Loading test set from {test_set_path}...")
    test_cases = load_test_set(test_set_path)
    print(f"Running {len(test_cases)} test cases with {config.LLM_PROVIDER} backend...\n")
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] {test_case['id']} ({test_case['category']}): {test_case['question'][:60]}...")
        result = run_single_eval(test_case)
        results.append(result)
        
        # Print quick status
        status = "✓" if result.path_correct else "✗"
        print(f"  Path: {result.actual_path} (expected: {result.expected_path}) {status}")
        if result.expected_tool:
            tool_status = "✓" if result.tool_correct else "✗"
            print(f"  Tool: {result.actual_tool} (expected: {result.expected_tool}) {tool_status}")
        if result.answer:
            print(f"  Answer score: {result.answer_score:.2f}")
        if result.error:
            print(f"  ERROR: {result.error}")
        print(f"  Latency: {result.latency_ms:.0f}ms, Cost: ${result.cost_usd:.6f}")
        print()
    
    # Aggregate results
    total = len(results)
    path_correct = sum(1 for r in results if r.path_correct)
    tool_correct = sum(1 for r in results if r.tool_correct)
    avg_answer_score = sum(r.answer_score for r in results) / total if total > 0 else 0
    avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0
    total_cost = sum(r.cost_usd for r in results)
    total_tokens = sum(
        (r.tokens_used or {}).get("input_tokens", 0) + (r.tokens_used or {}).get("output_tokens", 0) 
        for r in results
    )
    errors = sum(1 for r in results if r.error)
    
    # By category
    by_category = {}
    for r in results:
        cat = r.category
        if cat not in by_category:
            by_category[cat] = {"total": 0, "path_correct": 0, "tool_correct": 0, "avg_score": 0, "avg_latency": 0}
        by_category[cat]["total"] += 1
        if r.path_correct:
            by_category[cat]["path_correct"] += 1
        if r.tool_correct:
            by_category[cat]["tool_correct"] += 1
        by_category[cat]["avg_score"] += r.answer_score
        by_category[cat]["avg_latency"] += r.latency_ms
    
    for cat in by_category:
        c = by_category[cat]
        c["avg_score"] /= c["total"]
        c["avg_latency"] /= c["total"]
        c["path_accuracy"] = c["path_correct"] / c["total"]
        c["tool_accuracy"] = c["tool_correct"] / c["total"] if c["tool_correct"] > 0 else 0
    
    # Build report
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "llm_provider": config.LLM_PROVIDER,
            "llm_model": getattr(config, f"{config.LLM_PROVIDER.upper()}_MODEL", "unknown"),
            "total_questions": total,
        },
        "summary": {
            "path_accuracy": path_correct / total if total > 0 else 0,
            "tool_accuracy": tool_correct / total if total > 0 else 0,
            "avg_answer_score": avg_answer_score,
            "avg_latency_ms": avg_latency,
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
            "error_rate": errors / total if total > 0 else 0,
        },
        "by_category": by_category,
        "results": [asdict(r) for r in results],
    }
    
    # Save report
    if output_path is None:
        output_path = Path(__file__).parent / f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"LLM Provider: {config.LLM_PROVIDER}")
    print(f"Total Questions: {total}")
    print(f"Path Accuracy: {path_correct}/{total} ({report['summary']['path_accuracy']:.1%})")
    print(f"Tool Accuracy: {tool_correct}/{total} ({report['summary']['tool_accuracy']:.1%})")
    print(f"Avg Answer Score: {avg_answer_score:.2f}")
    print(f"Avg Latency: {avg_latency:.0f}ms")
    print(f"Total Cost: ${total_cost:.6f}")
    print(f"Total Tokens: {total_tokens}")
    print(f"Errors: {errors}")
    print(f"\nBy Category:")
    for cat, stats in by_category.items():
        print(f"  {cat}: {stats['total']} q, Path: {stats['path_accuracy']:.1%}, Tool: {stats['tool_accuracy']:.1%}, Score: {stats['avg_score']:.2f}, Latency: {stats['avg_latency']:.0f}ms")
    print(f"\nReport saved to: {output_path}")
    
    return report


def print_detailed_results(report: Dict):
    """Print detailed per-question results."""
    print(f"\n{'='*60}")
    print("DETAILED RESULTS")
    print(f"{'='*60}")
    
    for r in report["results"]:
        print(f"\n{r['id']} [{r['category']}]")
        print(f"  Q: {r['question']}")
        print(f"  Expected Path: {r['expected_path']} | Actual: {r['actual_path']} {'✓' if r['path_correct'] else '✗'}")
        if r['expected_tool']:
            print(f"  Expected Tool: {r['expected_tool']} | Actual: {r['actual_tool']} {'✓' if r['tool_correct'] else '✗'}")
        if r['answer']:
            print(f"  Answer: {r['answer'][:100]}...")
            print(f"  Score: {r['answer_score']:.2f} | Confidence: {r['confidence']}")
        if r['clarification']:
            print(f"  Clarification: {r['clarification'][:100]}...")
        print(f"  Latency: {r['latency_ms']:.0f}ms | Cost: ${r['cost_usd']:.6f}")
        if r['error']:
            print(f"  ERROR: {r['error']}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run IntelliDocs agent evaluation")
    parser.add_argument("--test-set", default="eval/test_set.json", help="Path to test set JSON")
    parser.add_argument("--output", help="Output report path")
    parser.add_argument("--detailed", action="store_true", help="Print detailed results")
    parser.add_argument("--provider", help="Override LLM provider (groq, openai, anthropic, ollama, finetuned)")
    parser.add_argument("--retrieval-mode", choices=["vector", "hybrid"], help="Override retrieval mode (vector|hybrid)")
    
    args = parser.parse_args()
    
    # Override provider if specified
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
        # Reload config
        import importlib
        from app import config as config_module
        importlib.reload(config_module)
    
    # Override retrieval mode if specified
    if args.retrieval_mode:
        os.environ["RETRIEVAL_MODE"] = args.retrieval_mode
        # Reload config
        import importlib
        from app import config as config_module
        importlib.reload(config_module)
    
    test_set_path = Path(__file__).parent / args.test_set
    if not test_set_path.exists():
        print(f"Test set not found: {test_set_path}")
        sys.exit(1)
    
    output_path = Path(args.output) if args.output else None
    
    report = run_evaluation(str(test_set_path), str(output_path) if output_path else None)
    
    if args.detailed:
        print_detailed_results(report)