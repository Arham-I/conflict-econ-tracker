import os
import json
import subprocess
import asyncio
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
            model='gemini-3.1-flash-lite',
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
        
        log_str = "\n".join(run_logs)
        is_suspended = "Resume with: agents-cli" in log_str and "[synthesiser]:" not in log_str
        
        if process.returncode != 0 or is_suspended:
            if "RESOURCE_EXHAUSTED" in log_str or "Quota exceeded" in log_str or "429" in log_str or is_suspended:
                run_logs.append("")
                run_logs.append("⚠️ API RATE LIMIT EXCEEDED (Gemini Free Tier 429):")
                run_logs.append("The Google AI Studio free tier enforces both Requests Per Minute (RPM) limits and daily quotas (Requests Per Day).")
                run_logs.append("Please wait for your quota to reset (this could be a 60-second RPM cooldown or a 24-hour daily quota reset) before triggering a run again.")
            else:
                run_logs.append(f"Agent execution completed with status code: {process.returncode}")
        else:
            run_logs.append("Agent execution completed successfully (Status Code: 0).")
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

async def auto_run_scheduler():
    """Runs the agent pipeline every 2 hours automatically as long as the server is online."""
    # 2 hours interval (7200 seconds)
    interval = 7200
    while True:
        await asyncio.sleep(interval)
        if not is_running:
            # Execute in a separate thread pool thread to avoid blocking uvicorn's event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_agent_process)

@app.on_event("startup")
async def startup_event():
    # Start the background task scheduler loop upon server startup
    asyncio.create_task(auto_run_scheduler())
    
    # If briefings history file is missing or empty, fetch real news and data immediately
    if not os.path.exists(BRIEFINGS_FILE) or os.path.getsize(BRIEFINGS_FILE) == 0:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, run_agent_process)

@app.post("/api/email")
async def email_report(payload: Dict[str, str]):
    email_to = payload.get("email", "").strip()
    if not email_to:
        return JSONResponse(content={"error": "Recipient email address is required"}, status_code=400)
        
    # Get latest briefing to compile the report
    if not os.path.exists(BRIEFINGS_FILE):
        return JSONResponse(content={"error": "No briefing report available to email"}, status_code=400)
        
    try:
        with open(BRIEFINGS_FILE, "r") as f:
            briefings = json.load(f)
        if not briefings:
            return JSONResponse(content={"error": "No briefing report available to email"}, status_code=400)
        latest = briefings[-1]
    except Exception as e:
        return JSONResponse(content={"error": f"Failed to load latest briefing: {str(e)}"}, status_code=500)
        
    # Compile the formal email report
    sentiment = latest.get("sentiment_index", 5.0)
    risk_tier = "High Risk" if sentiment >= 8 else "Moderate Caution" if sentiment >= 5 else "Stable"
    commentary = latest.get("oil_market", {}).get("analyst_commentary", "No commentary available.")
    
    subject = f"CONFLICT ECONOMICS BRIEFING REPORT - Synthesised Risk: {sentiment}/10 ({risk_tier})"
    
    body = f"""======================================================================
CONFLICT ECONOMICS INTELLIGENCE BRIEFING REPORT
Generated: {latest.get('timestamp')} (UTC)
Risk Rating: {sentiment}/10 ({risk_tier})
======================================================================

LEAD ANALYST COMMENTARY & SYNTHESIS:
----------------------------------------------------------------------
{commentary}

CRUDE ENERGY BENCHMARKS:
----------------------------------------------------------------------
Brent Crude: ${latest.get('oil_market', {}).get('Brent', {}).get('price', 0.0):.2f} ({latest.get('oil_market', {}).get('Brent', {}).get('pct_change', 0.0):+.2f}%)
WTI Crude:   ${latest.get('oil_market', {}).get('WTI', {}).get('price', 0.0):.2f} ({latest.get('oil_market', {}).get('WTI', {}).get('pct_change', 0.0):+.2f}%)

TRANSMISSION CHANNELS (EQUITY INDICES):
----------------------------------------------------------------------
TADAWUL (Saudi):  {latest.get('regional_indices', {}).get('TADAWUL', {}).get('level', 0.0):,.2f} ({latest.get('regional_indices', {}).get('TADAWUL', {}).get('pct_change', 0.0):+.2f}%)
TA-35 (Israel):   {latest.get('regional_indices', {}).get('TA_35', {}).get('level', 0.0):,.2f} ({latest.get('regional_indices', {}).get('TA_35', {}).get('pct_change', 0.0):+.2f}%)
EGX-30 (Egypt):   {latest.get('regional_indices', {}).get('EGX_30', {}).get('level', 0.0):,.2f} ({latest.get('regional_indices', {}).get('EGX_30', {}).get('pct_change', 0.0):+.2f}%)
QE-Index (Qatar): {latest.get('regional_indices', {}).get('QE_Index', {}).get('level', 0.0):,.2f} ({latest.get('regional_indices', {}).get('QE_Index', {}).get('pct_change', 0.0):+.2f}%)

SAFE HAVENS:
----------------------------------------------------------------------
Gold (Spot): ${latest.get('global_indicators', {}).get('Gold', {}).get('level', 0.0):,.2f} ({latest.get('global_indicators', {}).get('Gold', {}).get('pct_change', 0.0):+.2f}%)
USD Index:   {latest.get('global_indicators', {}).get('USD_Index', {}).get('level', 0.0):.2f} ({latest.get('global_indicators', {}).get('USD_Index', {}).get('pct_change', 0.0):+.2f}%)

----------------------------------------------------------------------
This briefing was generated automatically by the Conflict Economics
Multi-Agent Geopolitical Financial Tracker using the Google ADK Framework.
"""
    
    # Save the email draft locally to history/emails/ for verification/debugging
    email_dir = os.path.join(BASE_DIR, "history", "emails")
    os.makedirs(email_dir, exist_ok=True)
    draft_file = os.path.join(email_dir, f"briefing_email_{latest.get('timestamp').replace(':', '-')}.txt")
    with open(draft_file, "w") as f:
        f.write(f"To: {email_to}\nSubject: {subject}\n\n{body}")
        
    # Attempt to send email via SMTP if configured in environmental variables
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USERNAME")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    
    sent_via_smtp = False
    error_msg = ""
    
    if smtp_server and smtp_user and smtp_pass:
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = smtp_user
            msg['To'] = email_to
            
            with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [email_to], msg.as_string())
            sent_via_smtp = True
        except Exception as e:
            error_msg = str(e)
            
    return JSONResponse(content={
        "status": "success",
        "sent_via_smtp": sent_via_smtp,
        "draft_saved_to": draft_file,
        "smtp_error": error_msg
    })
