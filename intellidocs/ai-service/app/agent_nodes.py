"""
LangGraph node functions for the IntelliDocs agent (Day 15-17).

Why separate node functions?
- Each node is a pure function (state in, state out) that can be unit tested independently.
- The graph just wires them together; business logic lives here.
- Makes it easy to swap/reorder nodes without touching the graph structure.
"""

from typing import Literal, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser

from . import config
from . import llm
from .rag_chain import retrieve, generate_answer
from .schemas import Answer, Citation
from .mcp_tools import search_documents, fetch_web_page, lookup_metadata
from .tracing import traceable, log_node_transition, log_tool_call


# =============================================================================
# State Schema
# =============================================================================

class AgentState(TypedDict):
    """
    Shared state passed between all nodes in the graph.

    Why TypedDict instead of a Pydantic model?
    - LangGraph expects a dict-like state that can be mutated in place.
    - TypedDict gives us static type checking without Pydantic's validation overhead.
    - We validate at the boundaries (input/output), not at every node transition.
    """
    # Input
    question: str
    
    # Router decision
    route: Literal["rag", "tool", "clarify"]
    
    # RAG path
    retrieved_chunks: list[dict]
    rag_answer: Answer | None
    
    # Tool path
    tool_name: str | None
    tool_args: dict | None
    tool_result: str | list[dict] | dict | None
    tool_answer: Answer | None
    
    # Clarify path
    clarification_question: str | None
    
    # Conversation history (for multi-turn)
    history: list[dict]
    
    # Final output
    final_answer: Answer | None
    final_clarification: str | None
    
    # Metadata for tracing/debugging
    metadata: dict


# =============================================================================
# Node: RAG Answer
# =============================================================================

@traceable(name="rag_answer_node")
def rag_answer_node(state: AgentState) -> AgentState:
    """
    Retrieve relevant chunks and generate a grounded answer using the existing RAG chain.
    
    This wraps the existing `rag_chain.py` logic but returns the Answer object
    in the state instead of directly returning it.
    """
    question = state["question"]
    
    # Retrieve chunks (reuse existing logic)
    chunks = retrieve(question, top_k=config.TOP_K)
    
    if not chunks:
        # No relevant documents found
        answer = Answer(
            answer="I couldn't find any relevant information in the knowledge base to answer that question.",
            citations=[],
            confidence="low",
        )
    else:
        # Generate answer using existing RAG chain
        result = generate_answer(question, chunks)
        
        citations = [
            Citation(
                source=chunk["metadata"].get("source", "unknown"),
                chunk_index=chunk["metadata"].get("chunk_index", 0),
                excerpt=chunk["text"],
            )
            for chunk in chunks
        ]
        
        confidence = "high" if len(chunks) >= 3 else "medium"
        
        answer = Answer(
            answer=result.answer,
            citations=citations,
            confidence=confidence,
        )
    
    # Update state
    state["retrieved_chunks"] = chunks
    state["rag_answer"] = answer
    state["final_answer"] = answer
    state["metadata"]["rag_chunks_count"] = len(chunks)
    
    return state


# =============================================================================
# Node: Call Tool
# =============================================================================

@traceable(name="call_tool_node")
def call_tool_node(state: AgentState) -> AgentState:
    """
    Call the appropriate MCP tool based on the router's decision and fold the result back.
    
    The router should have set `tool_name` and `tool_args` in the state.
    This node executes the tool and then generates an answer incorporating the tool result.
    """
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args", {})
    question = state["question"]
    
    if not tool_name:
        raise ValueError("call_tool_node called but no tool_name in state")
    
    # Execute the appropriate tool
    if tool_name == "search_documents":
        query = tool_args.get("query", question)
        top_k = tool_args.get("top_k", config.TOP_K)
        result = search_documents(query, top_k)
        state["tool_result"] = result
        state["metadata"]["tool_called"] = "search_documents"
        state["metadata"]["tool_query"] = query
        
    elif tool_name == "fetch_web_page":
        url = tool_args.get("url")
        if not url:
            raise ValueError("fetch_web_page requires 'url' in tool_args")
        result = fetch_web_page(url)
        state["tool_result"] = result
        state["metadata"]["tool_called"] = "fetch_web_page"
        state["metadata"]["tool_url"] = url
        
    elif tool_name == "lookup_metadata":
        filename = tool_args.get("filename")
        if not filename:
            raise ValueError("lookup_metadata requires 'filename' in tool_args")
        result = lookup_metadata(filename)
        state["tool_result"] = result
        state["metadata"]["tool_called"] = "lookup_metadata"
        state["metadata"]["tool_filename"] = filename
        
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    # Now generate an answer incorporating the tool result
    tool_result = state["tool_result"]
    
    # Build context from tool result
    if isinstance(tool_result, list):
        # search_documents returns a list of chunks
        context_text = "\n\n".join([
            f"[Result {i}] Source: {r.get('source', 'unknown')}\n{r.get('text', '')}"
            for i, r in enumerate(tool_result)
        ])
        citations = [
            Citation(
                source=r.get("source", "unknown"),
                chunk_index=r.get("chunk_index", i),
                excerpt=r.get("text", ""),
            )
            for i, r in enumerate(tool_result)
        ]
        confidence = "high" if len(tool_result) >= 3 else "medium"
        
    elif isinstance(tool_result, str):
        # fetch_web_page returns a string
        context_text = f"[Web Page Content]\n{tool_result}"
        citations = [
            Citation(
                source=tool_args.get("url", "web"),
                chunk_index=0,
                excerpt=tool_result[:500] + "..." if len(tool_result) > 500 else tool_result,
            )
        ]
        confidence = "medium"
        
    elif isinstance(tool_result, dict):
        # lookup_metadata returns a dict
        if "error" in tool_result:
            context_text = f"Error looking up metadata: {tool_result['error']}"
            citations = []
            confidence = "low"
        else:
            context_text = f"[Document Metadata]\nFilename: {tool_result.get('filename')}\nChunks: {tool_result.get('chunk_count')}\nSample: {tool_result.get('sample_text')}"
            citations = []
            confidence = "high"
    else:
        context_text = str(tool_result)
        citations = []
        confidence = "low"
    
    # Generate answer using the tool result as context
    prompt_template = f"""You are a helpful assistant that answers questions based on the provided information.

Information:
{context_text}

Question: {question}

Answer the question based only on the provided information. If the information doesn't contain enough to answer, say so."""
    
    # Use structured output
    structured_llm = llm.get_structured_llm(Answer)
    result = structured_llm.invoke(prompt_template)
    
    # Override citations and confidence with our computed values
    answer = Answer(
        answer=result.answer,
        citations=citations,
        confidence=confidence,
    )
    
    state["tool_answer"] = answer
    state["final_answer"] = answer
    
    return state


# =============================================================================
# Node: Clarify
# =============================================================================

@traceable(name="clarify_node")
def clarify_node(state: AgentState) -> AgentState:
    """
    Generate a clarifying question when the query is ambiguous or under-specified.
    
    Instead of guessing, the agent asks the user for clarification.
    This is returned as a special response type that the frontend renders differently.
    """
    question = state["question"]
    
    # Use LLM to generate a clarifying question
    prompt = f"""The user asked: "{question}"

This question is ambiguous or under-specified. Generate a clarifying question that would help you provide a better answer. 

Guidelines:
- Ask about specific details that would change the answer
- Keep it concise (1-2 sentences)
- Don't ask yes/no questions if possible
- Focus on what information you're missing

Clarifying question:"""
    
    # Use the base LLM (not structured) for this
    clarification = llm.generate(prompt).strip()
    
    state["clarification_question"] = clarification
    state["final_clarification"] = clarification
    state["metadata"]["clarification_generated"] = True
    
    return state


# =============================================================================
# Router Node (will be in agent_graph.py but defined here for clarity)
# =============================================================================

@traceable(name="router_node")
def router_node(state: AgentState) -> AgentState:
    """
    Decide which path to take: RAG, tool call, or clarification.
    
    This is the "brain" of the agent. It analyzes the question and available
    tools to decide the best approach.
    
    Routing Logic:
    - RAG: Questions about ingested documents, factual queries that can be
      answered from the knowledge base. Keywords: "what does the document say",
      "according to the report", "in the PDF", etc.
    - TOOL: Questions needing real-time info (web search), specific document
      metadata lookup, or when the user explicitly asks to search/fetch.
      Keywords: "search for", "look up", "fetch", "current", "latest", "web".
    - CLARIFY: Vague questions, missing context, multiple possible interpretations.
      Examples: "Tell me about it", "What about the other thing?", "Explain."
    """
    import re
    question = state["question"].lower()
    
    # Tool-worthy patterns (use word boundaries to avoid partial matches like "find" in "findings")
    tool_patterns = [
        r"\bsearch\b", r"\blook up\b", r"\bfetch\b", r"\bfind\b", 
        r"\bcurrent\b", r"\blatest\b", r"\btoday\b",
        r"\bnow\b", r"\brecent\b", r"\bnews\b", r"\bweb\b", 
        r"\binternet\b", r"\bonline\b", r"\bwebsite\b",
        r"\bmetadata\b", r"\bdocument info\b", r"\bfile info\b", 
        r"\bhow many chunks\b", r"\bchunk count\b"
    ]
    
    # Clarification patterns (vague/underspecified)
    clarify_patterns = [
        r"\btell me about\b", r"\bwhat about\b", r"\bexplain\b", r"\bdescribe\b", 
        r"\bit\b", r"\bthat\b", r"\bthis\b", r"\bthe other\b", 
        r"\bmore\b", r"\bcontinue\b", r"\bgo on\b"
    ]
    
    # RAG patterns (document-specific)
    rag_patterns = [
        r"\bdocument\b", r"\breport\b", r"\bpdf\b", r"\bfile\b", 
        r"\bpaper\b", r"\bstudy\b", r"\barticle\b",
        r"\baccording to\b", r"\bin the\b", r"\bfrom the\b", 
        r"\bbased on\b", r"\bingested\b"
    ]
    
    # Check for explicit tool requests first (using word boundaries)
    for pattern in tool_patterns:
        if re.search(pattern, question):
            # Determine which tool based on more specific patterns
            if re.search(r"\b(web|internet|online|website|news|current|latest|today|recent)\b", question):
                state["tool_name"] = "fetch_web_page"
                # Try to extract URL from question
                urls = re.findall(r'https?://\S+', state["question"])
                if urls:
                    state["tool_args"] = {"url": urls[0]}
                else:
                    # If no URL, we'll need to ask for clarification
                    state["route"] = "clarify"
                    return state
            elif re.search(r"\b(metadata|document info|file info|how many chunks|chunk count)\b", question):
                state["tool_name"] = "lookup_metadata"
                # Try to extract filename
                filenames = re.findall(r'["\']([^"\']+\.(?:pdf|txt|docx?))["\']', state["question"], re.IGNORECASE)
                if not filenames:
                    filenames = re.findall(r'\b(\w+\.(?:pdf|txt|docx?))\b', state["question"], re.IGNORECASE)
                if filenames:
                    state["tool_args"] = {"filename": filenames[0]}
                else:
                    state["route"] = "clarify"
                    return state
            else:
                state["tool_name"] = "search_documents"
                state["tool_args"] = {"query": state["question"]}
            
            state["route"] = "tool"
            return state
    
    # Check for clarification needs
    # Short questions with pronouns often need clarification
    words = question.split()
    if len(words) < 5:
        pronoun_count = sum(1 for w in words if w in ["it", "that", "this", "they", "them", "he", "she"])
        if pronoun_count > 0:
            state["route"] = "clarify"
            return state
    
    for pattern in clarify_patterns:
        if re.search(pattern, question) and len(words) < 10:
            state["route"] = "clarify"
            return state
    
    # Check if question appears to be about ingested documents
    # If no document-related keywords, it might be general knowledge
    has_doc_keywords = any(re.search(pattern, question) for pattern in rag_patterns)
    
    # General knowledge / current events patterns (questions likely NOT about ingested docs)
    general_knowledge_patterns = [
        r"\bcapital of\b", r"\bwho won\b", r"\bnobel prize\b", r"\bworld cup\b",
        r"\belection\b", r"\bpresident\b", r"\bprime minister\b", r"\bstock\b",
        r"\bweather\b", r"\btemperature\b", r"\btime\b", r"\bdate\b",
        r"\bcurrent events\b", r"\bbreaking news\b", r"\blatest news\b",
    ]
    
    is_general_knowledge = any(re.search(pattern, question) for pattern in general_knowledge_patterns)
    
    # If it looks like general knowledge/current events and not about documents,
    # route to clarify (for general knowledge) or tool (for current events with web search)
    if is_general_knowledge and not has_doc_keywords:
        # Check if it's a current events question that could use web search
        if re.search(r"\b(latest|current|today|recent|news|2024|2025)\b", question):
            state["tool_name"] = "fetch_web_page"
            # No URL provided, will need clarification
            state["route"] = "clarify"
            return state
        else:
            # General knowledge question - ask for clarification
            state["route"] = "clarify"
            return state
    
    # Default to RAG for document questions
    state["route"] = "rag"
    return state