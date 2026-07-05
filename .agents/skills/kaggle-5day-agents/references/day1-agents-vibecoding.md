# Day 1 — Introduction to Agents & Vibe Coding

## What is Vibe Coding?
"Vibe Coding" is the practice of using AI (like Antigravity/ADK) as your primary programming interface.
Instead of writing code line-by-line, you describe your intent in natural language and let the AI:
- Scaffold the project structure
- Write the implementation
- Verify correctness via evals
- Iterate based on your feedback

**The New SDLC**:
```
Traditional:  Requirements → Design → Code → Test → Deploy
Vibe Coding:  Describe → Generate → Review → Eval → Deploy
```

## What Makes an Agent Different from a Chatbot?

| Property | Chatbot | Agent |
|----------|---------|-------|
| Autonomy | Responds once | Multi-step actions |
| Tools | None | APIs, search, code exec, files |
| Memory | Single turn | Session state + long-term memory |
| Planning | None | Can decompose and sequence tasks |
| Goal | Answer question | Achieve a goal |

## Agent Architecture Patterns

### Single Agent (simple tasks)
```
User → LlmAgent (tools: [tool1, tool2]) → Response
```

### Multi-Agent (complex tasks)
```
User → Orchestrator LlmAgent
           ├── Specialist A (e.g. data_analyst)
           ├── Specialist B (e.g. report_writer)
           └── Specialist C (e.g. email_sender)
```

### Sequential Pipeline
```python
from google.adk.agents import SequentialAgent, LlmAgent

pipeline = SequentialAgent(
    name="data_pipeline",
    sub_agents=[
        LlmAgent(name="fetcher", instruction="Fetch data from API", output_key="raw_data"),
        LlmAgent(name="processor", instruction="Process {raw_data}", output_key="processed"),
        LlmAgent(name="reporter", instruction="Create report from {processed}"),
    ]
)
```

### Parallel Execution
```python
from google.adk.agents import ParallelAgent, LlmAgent

parallel = ParallelAgent(
    name="concurrent_tasks",
    sub_agents=[
        LlmAgent(name="task_a", instruction="Do task A", output_key="result_a"),
        LlmAgent(name="task_b", instruction="Do task B", output_key="result_b"),
    ]
)
```

### Loop Agent (iterative refinement)
```python
from google.adk.agents import LoopAgent, LlmAgent

loop = LoopAgent(
    name="refiner",
    max_iterations=5,
    sub_agents=[
        LlmAgent(name="draft_writer", instruction="Write/improve draft based on feedback"),
        LlmAgent(name="critic", instruction="Critique the draft and provide specific feedback"),
    ]
)
```

## ADK Agent Full Reference

```python
from google.adk.agents import Agent

agent = Agent(
    # Required
    name="my_agent",              # Unique name for this agent
    model="gemini-2.0-flash",     # Model to use
    
    # Optional
    instruction="You are...",     # System prompt / persona
    tools=[tool1, tool2],         # List of tools (functions or toolsets)
    sub_agents=[agent_a, agent_b], # Child agents this can delegate to
    
    # Callbacks (lifecycle hooks)
    before_agent_callback=...,    # Before agent starts processing
    after_agent_callback=...,     # After agent finishes
    before_model_callback=...,    # Before each LLM call
    after_model_callback=...,     # After each LLM call
    before_tool_callback=...,     # Before each tool call
    after_tool_callback=...,      # After each tool call
    
    # Output
    output_key="result",          # If set, saves final response to session state
)
```

## Setting Up Your Environment

```bash
# Install ADK
pip install google-adk

# Install agents-cli (for scaffolding + deployment)
uv tool install google-agents-cli

# Scaffold your capstone project
agents-cli scaffold create my-capstone --deployment cloud-run

# Run locally with dev UI
adk web
```

## Getting Your Gemini API Key
1. Go to https://aistudio.google.com
2. Click "Get API key"
3. Set `GOOGLE_API_KEY=your_key_here` in `.env`

## Antigravity Integration
- Use `agy` CLI or Antigravity 2.0 desktop app
- Describe your agent in natural language — Antigravity will scaffold, write, and iterate
- Review the generated code, test it, then refine via re-prompting
