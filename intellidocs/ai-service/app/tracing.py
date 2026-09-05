"""
Tracing setup for LangSmith (preferred) or Weights & Biases fallback (Day 20).

Why tracing?
- Debug agent behavior: see every node transition, LLM call, and tool invocation.
- Monitor production: track latency, token usage, error rates.
- Evaluate: compare runs across different prompts/models/configurations.
- LangSmith is purpose-built for LLM apps; W&B is a general ML platform.
"""

import os
from typing import Optional
from functools import wraps

from . import config


# Global tracer instance
_tracer = None
_tracing_enabled = False
_tracing_backend = None  # "langsmith" or "wandb"


def init_tracing() -> bool:
    """
    Initialize tracing based on available API keys.
    
    Priority:
    1. LangSmith (if LANGSMITH_API_KEY is set)
    2. Weights & Biases (if WANDB_API_KEY is set)
    3. Disabled (no keys)
    
    Returns:
        True if tracing was initialized, False otherwise.
    """
    global _tracer, _tracing_enabled, _tracing_backend
    
    # Check for LangSmith
    langsmith_key = os.getenv("LANGSMITH_API_KEY")
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "intellidocs")
    
    if langsmith_key:
        try:
            from langsmith import Client
            from langsmith.run_helpers import traceable
            
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
            os.environ["LANGSMITH_API_KEY"] = langsmith_key
            os.environ["LANGSMITH_PROJECT"] = langsmith_project
            
            _tracer = Client()
            _tracing_enabled = True
            _tracing_backend = "langsmith"
            
            print(f"[Tracing] LangSmith initialized (project: {langsmith_project})")
            return True
        except ImportError:
            print("[Tracing] langsmith package not installed, trying W&B...")
        except Exception as e:
            print(f"[Tracing] LangSmith init failed: {e}")
    
    # Check for Weights & Biases
    wandb_key = os.getenv("WANDB_API_KEY")
    wandb_project = os.getenv("WANDB_PROJECT", "intellidocs")
    
    if wandb_key:
        try:
            import wandb
            
            wandb.login(key=wandb_key)
            wandb.init(project=wandb_project, reinit=True)
            
            _tracer = wandb
            _tracing_enabled = True
            _tracing_backend = "wandb"
            
            print(f"[Tracing] Weights & Biases initialized (project: {wandb_project})")
            return True
        except ImportError:
            print("[Tracing] wandb package not installed")
        except Exception as e:
            print(f"[Tracing] W&B init failed: {e}")
    
    print("[Tracing] No tracing backend configured (set LANGSMITH_API_KEY or WANDB_API_KEY)")
    _tracing_enabled = False
    return False


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    return _tracing_enabled


def get_tracing_backend() -> Optional[str]:
    """Get the active tracing backend name."""
    return _tracing_backend


def get_tracer():
    """Get the tracer client."""
    return _tracer


# =============================================================================
# Decorators for tracing functions
# =============================================================================

def traceable(name: str = None, metadata: dict = None):
    """
    Decorator to trace a function call.
    
    Works with both LangSmith and W&B.
    
    Args:
        name: Custom name for the trace (defaults to function name).
        metadata: Additional metadata to attach to the trace.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _tracing_enabled:
                return func(*args, **kwargs)
            
            trace_name = name or func.__name__
            trace_metadata = metadata or {}
            
            if _tracing_backend == "langsmith":
                from langsmith.run_helpers import traceable as ls_traceable
                # LangSmith's traceable decorator handles this
                traced_func = ls_traceable(name=trace_name, metadata=trace_metadata)(func)
                return traced_func(*args, **kwargs)
            
            elif _tracing_backend == "wandb":
                import wandb
                # W&B doesn't have a direct function tracer, log as artifact
                with wandb.start_run(name=trace_name, reinit=True, config=trace_metadata) as run:
                    result = func(*args, **kwargs)
                    # Log result summary
                    if hasattr(result, 'model_dump'):
                        wandb.log({"result": result.model_dump()})
                    elif isinstance(result, dict):
                        wandb.log({"result": result})
                    return result
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# LangGraph-specific tracing helpers
# =============================================================================

def trace_graph_execution(graph, initial_state: dict, config: dict = None) -> dict:
    """
    Execute a LangGraph with tracing enabled.
    
    This wraps graph.invoke() and ensures the entire execution is traced
    as a single run in LangSmith/W&B.
    
    Args:
        graph: Compiled LangGraph app.
        initial_state: Initial state dict.
        config: LangGraph config (thread_id, etc.).
    
    Returns:
        Final state from graph execution.
    """
    if not _tracing_enabled:
        return graph.invoke(initial_state, config=config)
    
    if _tracing_backend == "langsmith":
        from langsmith.run_helpers import traceable
        
        @traceable(name="agent_graph_execution", metadata={
            "question": initial_state.get("question", ""),
            "thread_id": config.get("configurable", {}).get("thread_id") if config else None,
        })
        def _traced_invoke():
            return graph.invoke(initial_state, config=config)
        
        return _traced_invoke()
    
    elif _tracing_backend == "wandb":
        import wandb
        thread_id = config.get("configurable", {}).get("thread_id") if config else "unknown"
        
        with wandb.start_run(
            name=f"agent_execution_{thread_id}",
            reinit=True,
            config={
                "question": initial_state.get("question", ""),
                "thread_id": thread_id,
            }
        ) as run:
            result = graph.invoke(initial_state, config=config)
            # Log final state summary
            if result.get("final_answer"):
                wandb.log({
                    "answer": result["final_answer"].answer if hasattr(result["final_answer"], "answer") else str(result["final_answer"]),
                    "confidence": result["final_answer"].confidence if hasattr(result["final_answer"], "confidence") else "unknown",
                    "route": result.get("route"),
                })
            elif result.get("final_clarification"):
                wandb.log({
                    "clarification": result["final_clarification"],
                    "route": result.get("route"),
                })
            return result
    
    return graph.invoke(initial_state, config=config)


def log_node_transition(node_name: str, state: dict, metadata: dict = None):
    """
    Log a node transition for debugging/tracing.
    
    Call this at the start of each node function to track the flow.
    """
    if not _tracing_enabled:
        return
    
    log_data = {
        "node": node_name,
        "question": state.get("question", "")[:100],
        "route": state.get("route"),
        **(metadata or {}),
    }
    
    if _tracing_backend == "langsmith":
        # LangSmith automatically captures this via @traceable on nodes
        pass
    elif _tracing_backend == "wandb":
        import wandb
        wandb.log({f"node_{node_name}": log_data})


def log_llm_call(prompt: str, response: str, model: str = None, tokens: dict = None):
    """Log an LLM call with prompt, response, and token usage."""
    if not _tracing_enabled:
        return
    
    log_data = {
        "prompt_length": len(prompt),
        "response_length": len(response),
        "model": model or config.LLM_PROVIDER,
    }
    if tokens:
        log_data.update(tokens)
    
    if _tracing_backend == "langsmith":
        # LangSmith captures this automatically via callbacks
        pass
    elif _tracing_backend == "wandb":
        import wandb
        wandb.log({"llm_call": log_data})


def log_tool_call(tool_name: str, args: dict, result: any, duration_ms: float = None):
    """Log an MCP tool call."""
    if not _tracing_enabled:
        return
    
    log_data = {
        "tool": tool_name,
        "args": args,
        "result_type": type(result).__name__,
        "result_preview": str(result)[:200],
    }
    if duration_ms:
        log_data["duration_ms"] = duration_ms
    
    if _tracing_backend == "langsmith":
        pass
    elif _tracing_backend == "wandb":
        import wandb
        wandb.log({"tool_call": log_data})


# =============================================================================
# Evaluation run tagging
# =============================================================================

def tag_eval_run(run_id: str = None, tags: list = None):
    """
    Tag the current run as an evaluation run.
    
    Call this before running eval harness to distinguish eval traces from live traffic.
    """
    if not _tracing_enabled:
        return
    
    eval_tags = ["eval"] + (tags or [])
    
    if _tracing_backend == "langsmith":
        from langsmith import Client
        client = Client()
        if run_id:
            client.update_run(run_id, tags=eval_tags)
    elif _tracing_backend == "wandb":
        import wandb
        wandb.run.tags = eval_tags


def tag_live_traffic(run_id: str = None):
    """Tag the current run as live traffic."""
    if not _tracing_enabled:
        return
    
    if _tracing_backend == "langsmith":
        from langsmith import Client
        client = Client()
        if run_id:
            client.update_run(run_id, tags=["live"])
    elif _tracing_backend == "wandb":
        import wandb
        wandb.run.tags = ["live"]


# Initialize on import
init_tracing()