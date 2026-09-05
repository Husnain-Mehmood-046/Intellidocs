"""
LangGraph state graph for the IntelliDocs agent (Day 15-17).

Why LangGraph?
- Explicit state machine: each node is a pure function, transitions are visible.
- Built-in checkpointing: can pause/resume, inspect intermediate state.
- First-class streaming: stream tokens, state updates, or final results.
- Integrates with LangSmith for tracing (Day 20).
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .agent_nodes import AgentState, router_node, rag_answer_node, call_tool_node, clarify_node


def build_agent_graph():
    """
    Build and compile the LangGraph state graph.
    
    Graph Structure:
    
    START → router_node → rag_answer_node → END
                    ↓
                    → call_tool_node → END
                    ↓
                    → clarify_node → END
    
    The router_node decides which path to take based on the question.
    Each path ends at END with either a final_answer or final_clarification.
    """
    
    # Create the graph with our state schema
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("rag_answer", rag_answer_node)
    workflow.add_node("call_tool", call_tool_node)
    workflow.add_node("clarify", clarify_node)
    
    # Set entry point
    workflow.set_entry_point("router")
    
    # Add conditional edges from router
    def route_decision(state: AgentState) -> Literal["rag_answer", "call_tool", "clarify"]:
        """Determine which node to go to based on router's decision."""
        route = state.get("route", "rag")
        if route == "rag":
            return "rag_answer"
        elif route == "tool":
            return "call_tool"
        elif route == "clarify":
            return "clarify"
        else:
            # Default fallback
            return "rag_answer"
    
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "rag_answer": "rag_answer",
            "call_tool": "call_tool",
            "clarify": "clarify",
        }
    )
    
    # All paths end at END
    workflow.add_edge("rag_answer", END)
    workflow.add_edge("call_tool", END)
    workflow.add_edge("clarify", END)
    
    # Compile with memory saver for checkpointing
    # This allows us to inspect intermediate state and resume if needed
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app


# Create a singleton instance
_agent_graph = None


def get_agent_graph():
    """Get or create the compiled agent graph (singleton)."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


def run_agent(question: str, thread_id: str = "default") -> AgentState:
    """
    Run the agent graph with a question.
    
    Args:
        question: The user's question.
        thread_id: Unique identifier for the conversation thread (for checkpointing).
    
    Returns:
        The final state after graph execution.
    """
    graph = get_agent_graph()
    
    # Initial state
    initial_state: AgentState = {
        "question": question,
        "route": "rag",  # Will be overwritten by router
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
    
    # Run the graph
    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(initial_state, config=config)
    
    return final_state


def stream_agent(question: str, thread_id: str = "default"):
    """
    Stream the agent graph execution (for real-time updates).
    
    Yields:
        State updates as the graph executes.
    """
    graph = get_agent_graph()
    
    initial_state: AgentState = {
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
    
    # Stream state updates
    for chunk in graph.stream(initial_state, config=config, stream_mode="values"):
        yield chunk


if __name__ == "__main__":
    # Quick test
    import json
    
    test_questions = [
        "What does the document say about machine learning?",  # RAG
        "Search for information about neural networks",  # Tool (search_documents)
        "What's the latest news on AI?",  # Tool (fetch_web_page) - but needs URL
        "Tell me about it",  # Clarify
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Question: {q}")
        print(f"{'='*60}")
        
        try:
            result = run_agent(q)
            print(f"Route: {result.get('route')}")
            print(f"Final Answer: {result.get('final_answer')}")
            print(f"Final Clarification: {result.get('final_clarification')}")
            print(f"Metadata: {result.get('metadata')}")
        except Exception as e:
            print(f"Error: {e}")