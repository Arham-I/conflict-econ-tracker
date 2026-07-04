import os
import json
import subprocess
from typing import Dict, Any, List
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from google import genai

# Load environmental variables
load_dotenv()

app = FastAPI(title="Conflict Economics Intelligence Dashboard")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFINGS_FILE = os.path.join(BASE_DIR, "history", "briefings.json")

# Templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "frontend", "templates"))

# Global runner state
is_running = False
run_logs: List[str] = []

# GenAI client
client = genai.Client()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/api/briefings")
async def get_briefings():
    if not os.path.exists(BRIEFINGS_FILE):
        return JSONResponse(content=[])
    try:
        with open(BRIEFINGS_FILE, "r") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/chat")
async def chat_analyst(payload: Dict[str, str]):
    question = payload.get("question", "")
    if not question:
        return JSONResponse(content={"error": "Question is required"}, status_code=400)
        
    briefing_text = "No briefing data available."
    if os.path.exists(BRIEFINGS_FILE):
        try:
            with open(BRIEFINGS_FILE, "r") as f:
                data = json.load(f)
            if data:
                # Use latest briefing for context
                latest = data[-1]
                briefing_text = json.dumps(latest, indent=2)
        except Exception:
            pass
            
    try:
        prompt = f"""You are the Lead Geopolitical Economics Analyst for the Conflict Economics Intelligence Dashboard. 
You have compiled the following latest daily economic briefing:

{briefing_text}

A user is asking the following question about this economic briefing:
"{question}"

Answer the question professionally, drawing only from the metrics, sentiment scores, and facts provided in the briefing. 
If the information is not present in the briefing, explain that it is outside the scope of the current daily briefing data. 
Keep the answer concise (2-3 paragraphs max) and focus on economic and market transmission impacts. Do not speculate on military actions or make political opinions.
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return JSONResponse(content={"answer": response.text})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

def run_agent_process():
    global is_running, run_logs
    is_running = True
    run_logs.clear()
    run_logs.append("Initializing Agentic Execution...")
    
    try:
        # Run command using uv run
        process = subprocess.Popen(
            ["uv", "run", "agents-cli", "run", "Generate the briefing"],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Read output line by line
        for line in iter(process.stdout.readline, ""):
            if line:
                run_logs.append(line.strip())
                
        process.stdout.close()
        process.wait()
        run_logs.append(f"Agent execution completed with status code: {process.returncode}")
    except Exception as e:
        run_logs.append(f"Execution Error: {str(e)}")
    finally:
        is_running = False

@app.post("/api/run")
async def trigger_run(background_tasks: BackgroundTasks):
    global is_running
    if is_running:
        return JSONResponse(content={"status": "already_running", "logs": run_logs})
        
    background_tasks.add_task(run_agent_process)
    return JSONResponse(content={"status": "started"})

@app.get("/api/run-status")
async def get_run_status():
    global is_running, run_logs
    return JSONResponse(content={"is_running": is_running, "logs": run_logs})
