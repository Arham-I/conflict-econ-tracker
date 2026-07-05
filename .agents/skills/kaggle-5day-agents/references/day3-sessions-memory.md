# Day 3 — Agent Skills: Sessions & Memory

## The Memory Hierarchy

```
┌─────────────────────────────────┐
│  In-Context (current prompt)    │  ← Fastest, most direct, limited size
├─────────────────────────────────┤
│  Session State (this session)   │  ← Persists across turns in one conversation
├─────────────────────────────────┤
│  Memory Service (cross-session) │  ← Long-term, retrieved via semantic search
└─────────────────────────────────┘
```

## Sessions

A **Session** represents one conversation with a user.

```python
from google.adk.sessions import InMemorySessionService, DatabaseSessionService

# Local dev — in memory (not persistent)
session_service = InMemorySessionService()

# Production — database-backed (persistent)
# session_service = DatabaseSessionService(db_url="postgresql://...")

# Create a session
session = session_service.create_session(
    app_name="capstone_app",
    user_id="user_123",           # Links session to a user
    session_id="optional_uuid",   # Auto-generated if omitted
    state={                        # Optional initial state
        "user:name": "Alice",
        "app:version": "1.0"
    }
)
```

## State Management

State is a key-value store on the session. It's the agent's "working memory".

### State Scoping Prefixes
| Prefix | Scope | Persists When? |
|--------|-------|----------------|
| `user:` | Per user, across sessions | User-level persistence |
| `app:` | Shared across all users | App-level persistence |
| (none) | Current session only | Session ends → gone |

### Accessing State in Tools
```python
from google.adk.tools.tool_context import ToolContext

def remember_preference(preference: str, value: str, tool_context: ToolContext) -> dict:
    """Store a user preference that persists across sessions."""
    tool_context.state[f"user:{preference}"] = value
    return {"status": "saved", "preference": preference, "value": value}

def get_preference(preference: str, tool_context: ToolContext) -> dict:
    """Retrieve a previously stored preference."""
    value = tool_context.state.get(f"user:{preference}", None)
    return {"preference": preference, "value": value, "found": value is not None}

def list_user_preferences(tool_context: ToolContext) -> dict:
    """List all preferences for the current user."""
    user_prefs = {k: v for k, v in tool_context.state.items() if k.startswith("user:")}
    return {"preferences": user_prefs}
```

### State in Callbacks
```python
from google.adk.agents.callback_context import CallbackContext

def enrich_context(callback_context: CallbackContext, llm_request):
    """Add user context to every LLM call."""
    state = callback_context.state
    user_name = state.get("user:name", "User")
    user_tier = state.get("user:tier", "free")
    turn_count = state.get("session_turns", 0) + 1
    
    # Update turn counter
    callback_context.state["session_turns"] = turn_count
    
    # Inject into system instruction
    extra = f"\nUser: {user_name} (tier: {user_tier}, turn: {turn_count})"
    llm_request.config.system_instruction += extra
    return None
```

## Memory Service (Long-Term Memory)

Memory persists ACROSS sessions. It's retrieved via semantic search.

### In-Memory (dev only)
```python
from google.adk.memory import InMemoryMemoryService

memory_service = InMemoryMemoryService()

# Store a memory
await memory_service.add_session_to_memory(session)

# Search memories
memories = await memory_service.search_memory(
    app_name="capstone_app",
    user_id="user_123",
    query="user's diet preferences"
)
```

### Vertex AI RAG (production)
```python
from google.adk.memory import VertexAiRagMemoryService

memory_service = VertexAiRagMemoryService(
    rag_corpus="projects/my-project/locations/us-central1/ragCorpora/123",
    similarity_top_k=5,
    vector_distance_threshold=0.7
)
```

### Using Memory in an Agent
```python
from google.adk.agents import Agent
from google.adk.tools import load_memory

agent = Agent(
    name="memory_agent",
    model="gemini-2.0-flash",
    instruction="""You are a helpful personal assistant. 
    Before answering, check your memory for relevant context about this user.
    Always personalize responses based on what you know about the user.""",
    tools=[load_memory],  # Gives agent access to search memories
)
```

## All Callback Types

```python
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools.tool_context import ToolContext

# Before agent starts processing the turn
def before_agent(callback_context: CallbackContext):
    print(f"Agent starting turn {callback_context.state.get('turns', 0)}")
    # Return None to continue, or Content to respond immediately

# After agent finishes
def after_agent(callback_context: CallbackContext):
    print("Agent finished turn")

# Before each LLM API call
def before_model(callback_context: CallbackContext, llm_request: LlmRequest):
    # Modify request, add context, or short-circuit
    return None  # or return LlmResponse to skip LLM

# After each LLM API call  
def after_model(callback_context: CallbackContext, llm_response: LlmResponse):
    # Inspect/modify response
    return None  # or return new LlmResponse

# Before a tool is called
def before_tool(tool, args: dict, tool_context: ToolContext):
    print(f"Calling tool: {tool.name} with {args}")
    return None  # or return dict to skip tool execution

# After a tool returns
def after_tool(tool, args: dict, tool_context: ToolContext, tool_response: dict):
    print(f"Tool returned: {tool_response}")
    return None  # or return modified response dict

agent = Agent(
    name="fully_observed_agent",
    before_agent_callback=before_agent,
    after_agent_callback=after_agent,
    before_model_callback=before_model,
    after_model_callback=after_model,
    before_tool_callback=before_tool,
    after_tool_callback=after_tool,
)
```

## Context Engineering Tips

1. **Keep system prompts focused** — One job per agent. Don't cram everything into one instruction.
2. **Use state for dynamic context** — Don't repeat user info in every message; store it in state.
3. **Summarize long histories** — For long sessions, use a summarization tool to compress old turns.
4. **Retrieve, don't store everything** — Use memory search to retrieve only relevant past context.
5. **Output keys for pipelines** — Use `output_key` to pass data between sequential agents cleanly.
