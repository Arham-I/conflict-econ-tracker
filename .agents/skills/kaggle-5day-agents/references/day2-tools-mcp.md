# Day 2 — Agent Tools & Interoperability (MCP)

## Why Tools?
Tools are how agents take action in the real world. Without tools, agents can only generate text.
With tools, they can: call APIs, search the web, read/write files, query databases, send emails, etc.

## Tool Definition Rules (ADK)
1. Function must have type hints on ALL parameters
2. Must have a docstring — this becomes the tool description for the LLM
3. Return type should be dict (structured data the LLM can reason about)
4. Use specific parameter types (str, int, bool, list, dict) — avoid Any

```python
# ✅ Good tool definition
def get_product_details(product_id: str, include_reviews: bool = False) -> dict:
    """
    Retrieve product details from the catalog.
    
    Args:
        product_id: The unique product identifier (e.g. "PROD-123")
        include_reviews: Whether to include customer reviews in response
    
    Returns:
        dict with keys: name, price, stock, description, reviews (if requested)
    """
    # implementation
    return {"name": "Widget", "price": 9.99, "stock": 100}

# ❌ Bad tool definition (no type hints, no docstring)
def get_product(id, reviews):
    return db.fetch(id)
```

## Built-in ADK Tools

```python
from google.adk.tools import google_search, code_execution

agent = Agent(
    name="research_agent",
    tools=[
        google_search,      # Search Google for real-time information
        code_execution,     # Execute Python code in a sandbox
    ]
)
```

## MCP (Model Context Protocol) Deep Dive

### What is MCP?
MCP is the de facto standard (2025+) for agent-to-tool communication.
It separates the agent (client) from the tool provider (server) via a standard protocol.

```
Agent (MCP Client) ←──[MCP Protocol]──→ MCP Server ←──→ Data Source/API
```

### Why MCP over custom integrations?
- **Standardized**: Any MCP-compatible agent can use any MCP server
- **Discoverable**: Agents can list available tools dynamically
- **Composable**: Mix and match servers without code changes
- **Community ecosystem**: 500+ open-source MCP servers available

### Connecting to an MCP Server (stdio)
```python
from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters

# Filesystem access
filesystem_tools = MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/data"]
    )
)

# GitHub access
github_tools = MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."}
    )
)
```

### Connecting to an MCP Server (HTTP/SSE)
```python
from google.adk.tools.mcp_tool import MCPToolset, SseServerParams

remote_tools = MCPToolset(
    connection_params=SseServerParams(
        url="https://my-mcp-server.com/sse",
        headers={"Authorization": "Bearer my-token"}
    )
)
```

### Popular MCP Servers Ecosystem

| Server Package | Purpose | Key Tools Exposed |
|----------------|---------|-------------------|
| `@modelcontextprotocol/server-filesystem` | Local file I/O | read_file, write_file, list_directory |
| `@modelcontextprotocol/server-github` | GitHub API | create_issue, get_file_contents, search_code |
| `@modelcontextprotocol/server-brave-search` | Web search | brave_web_search |
| `@modelcontextprotocol/server-postgres` | PostgreSQL | query, describe_table |
| `@modelcontextprotocol/server-slack` | Slack | send_message, list_channels |
| `@modelcontextprotocol/server-google-maps` | Maps/Places | search_places, get_directions |
| `@modelcontextprotocol/server-puppeteer` | Browser automation | navigate, screenshot, click |

### Creating Your Own MCP Server (Python)
```python
# my_mcp_server.py
from mcp import Server, types

server = Server("my-capstone-server")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_sentiment",
            description="Analyze the sentiment of text",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "analyze_sentiment":
        # your logic here
        return [types.TextContent(type="text", text="positive")]

# Run with: python -m mcp.server.stdio my_mcp_server:server
```

## Tool Error Handling
```python
def safe_api_call(endpoint: str, params: dict) -> dict:
    """Call external API safely with error handling."""
    try:
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.Timeout:
        return {"success": False, "error": "API timed out after 10 seconds"}
    except requests.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```
