# Day 5 — Spec-Driven Production & A2A Protocol

## The Shift: From Prototype to Production

| Prototype (Days 1-4) | Production (Day 5) |
|----------------------|--------------------|
| Run locally | Deployed, always-on |
| Manual testing | Automated evals + monitoring |
| Single agent | Multi-agent system with A2A |
| Vibe-coded | Spec-driven, documented |
| No auth | Authentication + authorization |

## Spec-Driven Development

Write the SPEC FIRST. Code comes second.

### What Goes in the Spec (AGENTS.md)
```markdown
# My Capstone Agent

## Purpose
A concierge agent that helps small business owners manage their customer communications
and follow-ups, reducing manual work by 80%.

## Target Users
Small business owners (1-10 employees) who are overwhelmed with customer follow-up.

## Capabilities

### Core Tools
- `check_inbox`: Read and categorize new customer messages
- `draft_response`: Generate contextually appropriate reply drafts  
- `schedule_followup`: Schedule automated follow-up for specific customers
- `get_customer_history`: Retrieve past interaction history for context

### MCP Integrations
- Gmail (via @modelcontextprotocol/server-gmail)
- Google Calendar (via @modelcontextprotocol/server-gcal)

## Agent Architecture
Single LlmAgent with all tools. Sessions store customer context per user.
Long-term memory via InMemoryMemoryService for remembering customer preferences.

## Constraints
- MUST ask for confirmation before sending any message on user's behalf
- MUST not delete emails without explicit user confirmation
- MUST log all actions to session state for audit trail
- Response time: < 5 seconds for read operations, < 10s for write operations

## Success Criteria
- [ ] Given a new email, correctly categorizes it (90%+ accuracy in eval)
- [ ] Drafts contextually appropriate replies (LLM-judge score ≥ 4/5)
- [ ] Correctly routes follow-up scheduling to calendar tool
- [ ] Refuses to send without confirmation (100% in security eval)

## Evaluation Coverage
- evals/happy_path.json: 20 normal interactions
- evals/edge_cases.json: 10 edge cases
- evals/security_cases.json: 5 injection/jailbreak tests
```

## A2A Protocol (Agent-to-Agent)

### What is A2A?
A2A is a peer-to-peer open standard for agent discovery and delegation.
It allows agents to:
1. **Discover** each other via Agent Cards
2. **Delegate** tasks to specialized agents
3. **Collaborate** in multi-agent pipelines
4. **Interoperate** across different frameworks and vendors

### Agent Card Structure
```json
{
  "name": "CapstoneAgent",
  "description": "Helps small business owners manage customer communications",
  "version": "1.0.0",
  "url": "https://capstone-agent-xyz.run.app",
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain"],
  "skills": [
    {
      "id": "inbox-management",
      "name": "Inbox Management",
      "description": "Read, categorize, and respond to customer emails",
      "tags": ["email", "customer-service", "communication"],
      "examples": ["Check my inbox", "Categorize new emails", "Draft reply to John"]
    },
    {
      "id": "followup-scheduling",
      "name": "Follow-up Scheduling",
      "description": "Schedule automated customer follow-ups",
      "tags": ["calendar", "scheduling", "automation"]
    }
  ]
}
```

### Exposing Your Agent via A2A (ADK)
```python
from google.adk.agents import Agent
from google.adk.a2a import A2AServer

root_agent = Agent(
    name="capstone_agent",
    model="gemini-2.0-flash",
    instruction="You are a customer communications assistant...",
    tools=[check_inbox, draft_response, schedule_followup],
)

# Expose as A2A server
a2a_server = A2AServer(
    agent=root_agent,
    host="0.0.0.0",
    port=8080,
    agent_card_path="./agent_card.json"
)
```

### Delegating to Another A2A Agent
```python
from google.adk.tools.a2a_tool import A2ATool

# Connect to another agent's A2A endpoint
specialist_agent_tool = A2ATool(
    agent_url="https://specialist-agent.run.app",
    description="A specialist agent for handling complex legal queries"
)

orchestrator = Agent(
    name="orchestrator",
    model="gemini-2.0-flash",
    instruction="Route tasks to the appropriate specialist agent.",
    tools=[specialist_agent_tool],
)
```

## Deployment

### Option 1: Agent Runtime (Recommended for Capstone)
Managed, serverless Cloud Run — best for demos.
```bash
# Deploy
agents-cli deploy agent-runtime \
  --project my-gcp-project \
  --region us-central1 \
  --agent_module agent:root_agent

# Get the deployed URL
agents-cli deploy status
```

### Option 2: Cloud Run (More Control)
```bash
# Deploy to Cloud Run
agents-cli deploy cloud-run \
  --project my-gcp-project \
  --region us-central1 \
  --port 8080
```

### Option 3: Local + ngrok (Quick Demo)
```bash
# Run locally
adk web --port 8080

# Expose via ngrok (for live demo)
ngrok http 8080
```

## Production Checklist for Capstone

```markdown
## Pre-Submission Checklist

### Code
- [ ] AGENTS.md spec written and matches implementation
- [ ] All tools have type hints and docstrings
- [ ] Error handling in all tools
- [ ] No hardcoded secrets (use env vars or Secret Manager)

### Evaluation
- [ ] Eval dataset created (≥15 test cases covering happy path + edge cases)
- [ ] Evals passing at acceptable threshold
- [ ] Security eval cases included (prompt injection tests)

### Observability
- [ ] Logging implemented in key tools
- [ ] Traces accessible (Cloud Trace or local ADK UI)

### Deployment
- [ ] Agent deployed and accessible via URL
- [ ] Demo video recorded (YouTube)
- [ ] GitHub repo public with README.md

### Submission
- [ ] Kaggle writeup submitted with:
    - Problem statement
    - Architecture diagram
    - Key technical decisions
    - Demo video link
    - GitHub repo link
    - Live deployment link (if applicable)
```

## Multi-Agent Production Pattern (Advanced)

```python
from google.adk.agents import Agent, SequentialAgent

# Specialist agents
email_reader = Agent(
    name="email_reader",
    instruction="Read and categorize the provided email. Extract: sender, subject, urgency, required_action.",
    output_key="email_analysis"
)

response_drafter = Agent(
    name="response_drafter",
    instruction="Based on {email_analysis}, draft an appropriate response. Be professional and concise.",
    output_key="draft_response"
)

quality_checker = Agent(
    name="quality_checker",
    instruction="Review {draft_response} for professionalism, completeness, and tone. Approve or suggest improvements.",
    output_key="qa_result"
)

# Orchestrator pipeline
email_pipeline = SequentialAgent(
    name="email_pipeline",
    sub_agents=[email_reader, response_drafter, quality_checker]
)

# Root agent with access to pipeline
root_agent = Agent(
    name="capstone_agent",
    model="gemini-2.0-flash",
    instruction="You are a customer communications assistant. Use the email_pipeline for complex email tasks.",
    sub_agents=[email_pipeline],
)
```
