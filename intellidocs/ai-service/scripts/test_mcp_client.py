#!/usr/bin/env python
"""
MCP Test Client (Day 10-11).

This script connects to the MCP server and calls each tool once to verify
they work correctly in isolation before Week 3 wires them into an agent.

Run with: `python scripts/test_mcp_client.py`

Prerequisites:
- MCP server must be running in another terminal: `python -m app.mcp_server`
- Some documents should be ingested first (via /ingest endpoint)
"""

import asyncio
import sys
from pathlib import Path

# Add the ai-service directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters


async def test_mcp_tools():
    """Connect to MCP server and test all three tools."""

    # Configure the server parameters - run the MCP server as a subprocess
    # Use the virtual environment's Python executable
    import sys
    python_exe = sys.executable
    server_params = StdioServerParameters(
        command=python_exe,
        args=["-m", "app.mcp_server"],
        cwd=str(Path(__file__).resolve().parent.parent),
    )

    print("=" * 60)
    print("MCP Test Client - Testing IntelliDocs Tools")
    print("=" * 60)

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the session
            await session.initialize()
            print("\n✓ MCP session initialized")

            # List available tools
            tools_result = await session.list_tools()
            print(f"\n📋 Available tools ({len(tools_result.tools)}):")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Test 1: search_documents
            print("\n" + "=" * 60)
            print("TEST 1: search_documents_tool")
            print("=" * 60)
            try:
                result = await session.call_tool(
                    "search_documents_tool",
                    {"query": "machine learning", "top_k": 3}
                )
                print(f"✓ Tool call succeeded")
                print(f"  Result type: {type(result.content)}")
                if result.content:
                    for i, content in enumerate(result.content):
                        if hasattr(content, 'text'):
                            print(f"  Result {i+1}: {content.text[:200]}...")
                        else:
                            print(f"  Result {i+1}: {str(content)[:200]}...")
            except Exception as e:
                print(f"✗ Tool call failed: {e}")

            # Test 2: fetch_web_page
            print("\n" + "=" * 60)
            print("TEST 2: fetch_web_page_tool")
            print("=" * 60)
            try:
                result = await session.call_tool(
                    "fetch_web_page_tool",
                    {"url": "https://example.com"}
                )
                print(f"✓ Tool call succeeded")
                if result.content:
                    for i, content in enumerate(result.content):
                        if hasattr(content, 'text'):
                            print(f"  Result {i+1}: {content.text[:200]}...")
                        else:
                            print(f"  Result {i+1}: {str(content)[:200]}...")
            except Exception as e:
                print(f"✗ Tool call failed: {e}")

            # Test 3: lookup_metadata
            print("\n" + "=" * 60)
            print("TEST 3: lookup_metadata_tool")
            print("=" * 60)
            try:
                result = await session.call_tool(
                    "lookup_metadata_tool",
                    {"filename": "sample.txt"}
                )
                print(f"✓ Tool call succeeded")
                if result.content:
                    for i, content in enumerate(result.content):
                        if hasattr(content, 'text'):
                            print(f"  Result {i+1}: {content.text[:200]}...")
                        else:
                            print(f"  Result {i+1}: {str(content)[:200]}...")
            except Exception as e:
                print(f"✗ Tool call failed: {e}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())