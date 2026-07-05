# Conflict Economics Intelligence Dashboard

An advanced, multi-agent geopolitical financial and economic transmission tracker built using the **Google Agent Development Kit (ADK)**. 

This system monitors the measurable financial impacts of Middle East conflict escalations (focusing on crude oil benchmarks, regional stock indices, safe havens, and logistical channels), calculates historical performance deltas, and presents results in a dark-themed, interactive FastAPI dashboard equipped with live terminal logging, dynamic charts, and an expandable "Focus View" analyst modal.

---

## 1. Problem Statement

During periods of regional geopolitical conflict, financial markets experience substantial volatility. Analysts, investors, and policymakers face two major hurdles:
1. **Speculative Noise**: Most trackers focus on military maneuvers or political statements, introducing heavy bias and speculation rather than analyzing concrete market indicators.
2. **Scattered Indicators**: Crucial transmission metrics (such as Brent/WTI crude, regional indices like Tadawul/TA-35, shipping route delay metrics, and safe havens like Gold) are scattered across disparate APIs, making cross-correlation slow and manual.

### The Solution: An Agentic Transmission Tracker
We solve this by orchestrating a sequential pipeline of specialist agents that ingest market numbers and news, evaluate severity, calculate historical deltas against previous days, and synthesize results into a standardized, machine-readable JSON briefing.

---

## 2. System Architecture

The tracker is implemented as a sequential multi-agent system. State (raw metrics and text commentaries) is passed dynamically between sub-agents via the ADK session state callbacks.

```mermaid
graph TD
    User([Scheduled Trigger / Manual UI Click]) --> Orchestrator[Orchestrator Agent]
    Orchestrator --> News[News Analyst Agent]
    Orchestrator --> Oil[Oil Markets Analyst Agent]
    Orchestrator --> Regional[Regional Markets Analyst Agent]
    News --> Synthesiser[Synthesiser Agent]
    Oil --> Synthesiser
    Regional --> Synthesiser
    Synthesiser --> Deltas[Delta Calculator Callback]
    Deltas --> History[(history/briefings.json)]
    Synthesiser --> Output([Structured JSON Briefing])
```

### Specialist Agent Breakdown
1. **News Analyst**: Queries Google News RSS feeds to fetch real-world conflict-related maritime and economic headlines (e.g., Red Sea shipping reroutings, Hormuz delays) and assigns High/Medium/Low market impact ratings.
2. **Oil Markets Analyst**: Ingests Brent and WTI crude futures prices, computes performance compared to the 5-day Simple Moving Average (SMA), and writes commentary about market concerns.
3. **Regional Markets Analyst**: Tracks Middle East stock benchmarks (TADAWUL, TA-35, EGX-30, QE-Index) alongside safe havens (Gold spot, US Dollar Index).
4. **Synthesiser Agent**: Connects the dots, assigns a consolidated conflict economics sentiment index (1–10 scale), and outputs the payload conforming to the strict Pydantic `ConflictBriefing` schema.

---

## 3. Resilience & Rate-Limit Engineering

To accommodate the strict constraints of the Google AI Studio free tier (which enforces limits of **5 Requests Per Minute (RPM)** and **250,000 Tokens Per Minute (TPM)** on unbilled accounts), the system implements two custom engineering safeguards:

1. **Orchestrator Lifecycle Delays**: In `app/agent.py`, a custom `rate_limit_delay_callback` hook intercepts the pipeline before the execution of the Oil, Regional, and Synthesiser agents, applying a **20-second sleep delay**. This spreads out the pipeline's 8 sequential API calls over 65 seconds, ensuring the pipeline *never* triggers a 5 RPM rate limit block during a run.
2. **Suspension Interception & User Warnings**: In the background runner (`frontend/main.py`), the system monitors the terminal logs for ADK's checkpoint keyword (`Resume with: agents-cli`). If a session is suspended due to an API quota block before reaching the `[synthesiser]:` completion stage, the dashboard intercepts the exit state and appends a friendly, explanatory error warning to the logs, letting the user know whether they hit a minute-level cooldown or daily limit.

---

## 4. Key Concepts Demonstrated (Rubric Compliance)

This project implements **5 out of 6** key concepts from the Kaggle/Google Intensive course:
1. **Multi-Agent System (ADK)**: Built entirely on the ADK Python SDK utilizing `SequentialAgent` orchestrators and `CallbackContext` state management.
2. **MCP Server**: Implements a standalone FastMCP server in `mcp_server.py` exposing our quantitative/qualitative data tools over the Model Context Protocol.
3. **Antigravity**: Built using the Antigravity agentic IDE (demonstrating AI pair programming workflows).
4. **Security Features**: No hardcoded API keys. Environment variables are loaded securely via `load_dotenv`. All tool payloads are typed and validated using Pydantic models. We implement a local 1-hour cache layer to prevent API key exhaustion.
5. **Deployability**: Built to run serverlessly, deploying the frontend dashboard to Google Cloud Run and the agent execution to GitHub Actions cron.
6. **Agent Skills (Agents CLI)**: Developed, installed, and evaluated using standard `agents-cli` commands.

---

## 5. Local Setup & Installation (Reviewer Quick-Start)

### Prerequisites
* Python 3.11+
* [Astral uv](https://github.com/astral-sh/uv) (recommended) or standard `pip`

### Step 1: Install Dependencies
Install packages and sync virtual environment dependencies:
```bash
cd conflict-econ-tracker

# Option A: Using agents-cli (Recommended)
agents-cli install

# Option B: Using pip
pip install -e .
```

### Step 2: Configure Environment Variables
Create a `.env` file in the root directory:
```bash
# Disable Vertex AI defaults to route calls to Google AI Studio
GOOGLE_GENAI_USE_VERTEXAI=False
GEMINI_API_KEY=your_google_ai_studio_api_key
```
> [!IMPORTANT]
> **Zero API Key Friction**: You **do not** need a NewsAPI key. The dashboard is configured to use Google News RSS search feeds natively out-of-the-box. Your `GEMINI_API_KEY` is the only credential required to run the entire live system.

### Step 3: Run the Agent Pipeline (CLI)
Execute the pipeline from the command line to generate your first briefing:
```bash
agents-cli run "Generate the briefing"
```
*This command runs the sequential agents, computes deltas, and saves the output to `history/briefings.json`.*

### Step 4: Run Evaluations
Run the automated quality and schema checks against our test dataset:
```bash
export GOOGLE_CLOUD_PROJECT=your_project_id
agents-cli eval run
```
*Evaluations run locally and grade response quality on a 1-5 scale using model-graded judges.*

---

## 6. Running the Web Dashboard

We host a FastAPI web server in the `frontend/` directory to serve the interactive UI.

### Launch Uvicorn
Start the local web server:
```bash
uv run uvicorn frontend.main:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser.

### Interactive Features
* **Interactive Charting**: Switch between Crude (Brent/WTI) and Gold prices. Chart.js automatically scales the Y-axis range limits dynamically based on the current values to highlight small price fluctuations.
* **Lead Analyst Focus View**: Click the **"🔍 Expand View"** button on the analyst commentary panel to reveal a fullscreen, dark-themed focus modal. It renders the full synthesised report in a readable serif font. If you click a news article to inspect details, clicking "Expand View" will pop up the detailed News Impact Assessment.
* **Live Run Console**: Click "TRIGGER LIVE RUN" to execute the agent pipeline in the background and watch terminal logs stream in real-time in the dashboard.
* **"Ask the Analyst" Chat**: Submit questions about the economic briefing. The app uses Gemini to answer questions based on the latest cache.

---

## 7. Deployment Guide

### Deployment 1: Dashboard Frontend (Google Cloud Run)
FastAPI is containerized and deployed to Cloud Run using a single command:
```bash
gcloud run deploy conflict-econ-dashboard \
    --source . \
    --env-vars-file .env.yaml \
    --allow-unauthenticated
```
*(Cloud Run is serverless, scaling down to 0 instances when idle, incurring $0.00 in hosting costs).*

### Deployment 2: Agent Scheduler (GitHub Actions Cron)
To update briefings automatically without running a server, set up a GitHub Actions workflow `.github/workflows/daily_briefing.yml`:
```yaml
name: Generate Daily Economic Briefing
on:
  schedule:
    - cron: '0 */2 * * *' # Executes every 2 hours
jobs:
  run-agent:
    runs-allowed: write
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
      - name: Install dependencies
        run: pip install uv && uv pip install -e .
      - name: Execute Agent
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: uv run agents-cli run "Generate the briefing"
      - name: Commit Updated History
        run: |
          git config --global user.name "Briefing Bot"
          git config --global user.email "bot@briefings.com"
          git add history/briefings.json
          git commit -m "update daily briefing data [skip ci]" || echo "No changes"
          git push
```
