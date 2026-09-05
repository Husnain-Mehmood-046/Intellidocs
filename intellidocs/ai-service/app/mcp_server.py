"""
MCP Server for IntelliDocs (Day 10-11).

Why a separate MCP server?
- The Model Context Protocol (MCP) standardizes how tools are exposed to LLMs.
- Running as a separate process allows the AI service to call tools via MCP
  without tight coupling, and enables future agent architectures (Week 3).
- The official `mcp` Python SDK handles protocol details (JSON-RPC, stdio/SSE).

Run with: `python -m app.mcp_server`
"""

from mcp.server.mcpserver import MCPServer

from .mcp_tools import search_documents, fetch_web_page, lookup_metadata

# Create the MCP server
mcp = MCPServer("IntelliDocs Tools")


@mcp.tool()
def search_documents_tool(query: str, top_k: int = 4) -> list[dict]:
    """
    Search the knowledge base for relevant document chunks.

    Use this tool when you need to find information from previously ingested
    documents (PDFs, text files) to answer a user's question.

    Args:
        query: The search query - what you're looking for in the documents.
        top_k: Maximum number of chunks to return (default: 4).

    Returns:
        A list of matching chunks, each with:
        - source: document path/filename
        - chunk_index: position within the document
        - text: the actual chunk content
        - metadata: additional metadata (page number, etc.)
    """
    return search_documents(query, top_k)


@mcp.tool()
def fetch_web_page_tool(url: str) -> str:
    """
    Fetch and extract clean text content from a web page.

    Use this tool when you need current information from the web that isn't
    in the local knowledge base. Only HTTP/HTTPS URLs are allowed; local
    and private addresses are blocked for security.

    Args:
        url: The full URL to fetch (must start with http:// or https://).

    Returns:
        The extracted text content of the page (truncated to ~10k chars).
    """
    return fetch_web_page(url)


@mcp.tool()
def lookup_metadata_tool(filename: str) -> dict:
    """
    Look up metadata about a previously ingested document.

    Use this tool when you need to know details about a document in the
    knowledge base, such as how many chunks it has, when it was added,
    or to verify it exists before searching.

    Args:
        filename: The name of the file to look up (e.g., "report.pdf").

    Returns:
        A dict with:
        - filename: the queried filename
        - chunk_count: number of chunks stored for this document
        - sources: list of source paths
        - first_chunk_metadata: metadata from the first chunk
        - sample_text: preview of the document content
    """
    return lookup_metadata(filename)


if __name__ == "__main__":
    # Run the MCP server over stdio (default transport)
    mcp.run()