# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# ==============================================================================
# CONFLICT ECONOMICS INTELLIGENCE TRACKER - CORE AGENTS & PIPELINE
# ==============================================================================
# Architecture Design:
# This file implements a multi-agent delegation system using a SequentialAgent pipeline.
#
# Why a Sequential Agent?
# 1. Determinism: Geopolitical economic reporting requires a structured analysis flow
#    (News -> Oil -> Regional Stock Indices -> Synthesis). Cyclic loops or conversational
#    chatter would introduce unnecessary latency, increase LLM tokens, and risk hallucination.
# 2. Pipeline Dependency: The Synthesiser Agent requires raw quantitative data from
#    Yahoo Finance/Alpha Vantage and qualitative summaries from NewsAPI to connect the dots.
#    A sequential flow guarantees that when the Synthesiser runs, all context is fully populated.
#
# State Management:
# Session state is managed through the ADK's CallbackContext. State variables are shared
# across agents, allowing us to decoupled data extraction tools from the final synthesis.
#
# Security & Rate Limits:
# 1. No hardcoded API keys. All keys are loaded from .env or system environment.
# 2. Rate-Limit Protection: Google AI Studio Free Tier has a strict 5 RPM limit.
#    We register a delay callback before each agent executes to space out calls.

import datetime
import os
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environmental variables from the project root .env file
load_dotenv()

from google.adk.agents import Agent, SequentialAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

import google.auth
import json

# ==============================================================================
# GCP / VERTEX AI / GOOGLE AI STUDIO CREDENTIAL RESOLUTION
# ==============================================================================
# Since this agent is built to run on both Vertex AI (GCP) and Google AI Studio (Free Tier),
# we implement a robust project ID and API routing resolution system.
use_vertex = True
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")

if not project_id:
    # Attempt to extract project ID from Application Default Credentials (ADC)
    try:
        _, project_id = google.auth.default()
    except Exception:
        pass

if not project_id:
    # Read locally cached quota project ID from local gcloud config
    adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if os.path.exists(adc_path):
        try:
            with open(adc_path, "r") as f:
                adc_data = json.load(f)
                project_id = adc_data.get("quota_project_id") or adc_data.get("project_id")
        except Exception:
            pass

# Default fallback project ID for verification runs
if not project_id:
    project_id = "adkagentdeployment-500020"

# If a Gemini API Key is found, bypass Vertex AI and route model calls to Google AI Studio
if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
    use_vertex = False

if use_vertex:
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

# Define the shared Gemini model instance (utilizing 3 attempts for transient HTTP error retries)
model_instance = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# ==============================================================================
# PYDANTIC SCHEMAS FOR STRUCTURED JSON OUTPUT
# ==============================================================================
# To ensure our generated briefing can be easily consumed by our dashboard frontend,
# we enforce a strict nested Pydantic schema on the Synthesiser's output.

class Headline(BaseModel):
    title: str = Field(description="Title of the news article")
    source: str = Field(description="News source name")
    impact_rating: str = Field(description="Impact rating: High, Medium, or Low")
    summary: str = Field(description="Short summary of the economic/market impact")

class OilMarketStatus(BaseModel):
    price: float = Field(description="Current price of Brent/WTI crude")
    pct_change: float = Field(description="Daily percentage change")
    trend: str = Field(description="Bullish or Bearish trend descriptor")

class OilMarketsBriefing(BaseModel):
    WTI: OilMarketStatus
    Brent: OilMarketStatus
    analyst_commentary: str = Field(description="Market concerns and analyst sentiment commentary")

class IndexStatus(BaseModel):
    level: float = Field(description="Current level of the stock index or commodity")
    change: float = Field(description="Daily absolute change")
    pct_change: float = Field(description="Daily percentage change")

class RegionalIndicesBriefing(BaseModel):
    TADAWUL: IndexStatus
    TA_35: IndexStatus = Field(description="Tel Aviv stock index status")
    EGX_30: IndexStatus = Field(description="Egypt EGX 30 index status")
    QE_Index: IndexStatus = Field(description="Qatar QE Index status")

class GlobalIndicatorsBriefing(BaseModel):
    Gold: IndexStatus
    USD_Index: IndexStatus = Field(description="US Dollar Index status")

class DeltaMetrics(BaseModel):
    brent_change_pct: float = Field(description="Percentage change since last briefing")
    wti_change_pct: float = Field(description="Percentage change since last briefing")
    tadawul_change_pct: float = Field(description="Percentage change since last briefing")
    ta35_change_pct: float = Field(description="Percentage change since last briefing")
    gold_change_pct: float = Field(description="Percentage change since last briefing")
    sentiment_shift: float = Field(description="Change in sentiment index since last briefing")
    days_since_last_briefing: int = Field(description="Number of days elapsed since the last stored briefing")

class ConflictBriefing(BaseModel):
    timestamp: str = Field(description="UTC timestamp of the briefing run in ISO format")
    news_summary: List[Headline] = Field(description="List of major economic headlines and assessments")
    oil_market: OilMarketsBriefing = Field(description="Brent and WTI crude market metrics and analysis")
    regional_indices: RegionalIndicesBriefing = Field(description="Regional index levels and changes")
    global_indicators: GlobalIndicatorsBriefing = Field(description="Safe haven assets gold and USD index changes")
    sentiment_index: float = Field(description="Consolidated concern score from 1 to 10 (10 is highest market concern/disruption)")
    deltas: DeltaMetrics = Field(description="Computed changes compared to the previous daily run")


# ==============================================================================
# PIPELINE CALLBACKS & RUNTIME LIFE-CYCLE HOOKS
# ==============================================================================

async def init_state_callback(callback_context: CallbackContext):
    """
    Orchestration Hook: Initializes empty structures in session state before execution.
    This prevents dynamic Jinja template errors during agent instructions generation.
    """
    keys = {
        "raw_news_data": {},
        "raw_oil_data": {},
        "raw_regional_data": {},
        "news_analysis": "",
        "oil_analysis": "",
        "regional_analysis": "",
        "deltas": {
            "brent_change_pct": 0.0,
            "wti_change_pct": 0.0,
            "tadawul_change_pct": 0.0,
            "ta35_change_pct": 0.0,
            "gold_change_pct": 0.0,
            "sentiment_shift": 0.0,
            "days_since_last_briefing": 1
        }
    }
    for k, v in keys.items():
        if k not in callback_context.state:
            callback_context.state[k] = v

async def rate_limit_delay_callback(callback_context: CallbackContext):
    """
    Orchestration Hook: Runs before sub-agents execute.
    Applies a 16-second delay only when utilizing Google AI Studio (Free Tier)
    to space out requests and avoid hitting the 5 Requests-Per-Minute (RPM) limit.
    """
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "False":
        await asyncio.sleep(16)

async def pre_synthesiser_callback(callback_context: CallbackContext):
    """
    Orchestration Hook: Runs immediately before the Synthesiser Agent executes.
    Computes intermediate market price deltas comparing retrieved values against
    our local database (history/briefings.json) and registers them into the state.
    """
    await rate_limit_delay_callback(callback_context)
    current_data = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "oil_market": callback_context.state.get("raw_oil_data", {}),
        "regional_indices": callback_context.state.get("raw_regional_data", {}),
        "sentiment_index": 5.0  # Temporary baseline for initial delta calculations
    }
    # Calculate initial deltas against history
    deltas = calculate_deltas(current_data)
    callback_context.state["deltas"] = deltas

async def post_synthesiser_callback(callback_context: CallbackContext):
    """
    Orchestration Hook: Runs immediately after the Synthesiser Agent finishes.
    
    Why run deltas here?
    Since the Synthesiser dynamically decides the consolidated 'sentiment_index'
    based on qualitative analysis, the final 'sentiment_shift' (current - previous)
    can only be calculated AFTER the Synthesiser completes.
    
    This callback:
    1. Grabs the completed structured briefing from session state.
    2. Runs calculate_deltas using the actual generated sentiment index.
    3. Re-injects the accurate delta metrics back into the final briefing schema.
    4. Persists the updated briefing to history/briefings.json.
    """
    final_briefing = callback_context.state.get("final_briefing")
    if final_briefing:
        if hasattr(final_briefing, "model_dump"):
            briefing_dict = final_briefing.model_dump()
        else:
            briefing_dict = final_briefing
            
        # Re-run delta calculator using the actual synthesised briefing data
        actual_deltas = calculate_deltas(briefing_dict)
        
        # Update the Pydantic state model in-place so the final tool response is accurate
        if hasattr(final_briefing, "model_dump"):
            final_briefing.deltas = DeltaMetrics(**actual_deltas)
            briefing_dict = final_briefing.model_dump()
        else:
            final_briefing["deltas"] = actual_deltas
            briefing_dict = final_briefing
            
        # Write to the local history database
        save_to_history(briefing_dict)


# ==============================================================================
# AGENT DEFINITIONS & INSTRUCTIONS
# ==============================================================================

# 1. News Analyst Specialist
# Purposed with scraping and rating the severity of geopolitical headlines.
news_analyst = Agent(
    name="news_analyst",
    model=model_instance,
    instruction="""You are the News Analyst Specialist. Your purpose is to track Middle East conflict news and assess its economic impact.
    
    1. Call the fetch_news_impact tool with the query 'Middle East economic impact'.
    2. Extract key headlines related to shipping disruptions (e.g. Red Sea), supply chains, energy infrastructure, or sanctions.
    3. Focus strictly on measurable economic facts, avoiding military strategy or political opinions.
    4. Write a summarized assessment of each article to explain why it has a High, Medium, or Low impact rating on markets.
    """,
    tools=[fetch_news_impact],
    output_key="news_analysis"
)

# 2. Oil Markets Specialist
# Purposed with tracking global crude oil pricing and technical SMAs.
oil_analyst = Agent(
    name="oil_analyst",
    model=model_instance,
    instruction="""You are the Oil Markets Specialist. Your purpose is to analyze Brent and WTI crude futures.
    
    1. Call the fetch_oil_markets tool.
    2. Analyze the latest Brent and WTI prices, daily changes, and their relation to the 5-day SMA.
    3. Provide a concise analyst commentary framing findings as market sentiment and geopolitical concerns.
    4. Do not make future price predictions (e.g. 'oil will hit $100'). Keep it objective and analytical.
    """,
    tools=[fetch_oil_markets],
    output_key="oil_analysis",
    before_agent_callback=rate_limit_delay_callback
)

# 3. Regional Markets Specialist
# Purposed with gathering regional indices, gold spot, and USD index changes.
regional_analyst = Agent(
    name="regional_analyst",
    model=model_instance,
    instruction="""You are the Regional Markets Specialist. Your purpose is to monitor Middle East stock indices and safe havens.
    
    1. Call the fetch_regional_indices tool.
    2. Analyze the current levels and daily percentage changes for TADAWUL, TA-35, EGX-30, and QE-Index.
    3. Note movements in Gold (safe haven) and the USD Index.
    4. Write a concise assessment of regional market sentiment based on this data.
    """,
    tools=[fetch_regional_indices],
    output_key="regional_analysis",
    before_agent_callback=rate_limit_delay_callback
)

# 4. Synthesiser Agent
# Connects qualitative news triggers to quantitative market metrics, outputting JSON.
synthesiser = Agent(
    name="synthesiser",
    model=model_instance,
    instruction="""You are the Synthesiser Agent. Your purpose is to connect the dots and format the final structured JSON briefing.
    
    You must construct the output conforming to the ConflictBriefing schema.
    
    Input data from state:
    - Raw News: {raw_news_data}
    - News Analysis Commentary: {news_analysis}
    - Oil Markets: {raw_oil_data}
    - Oil Commentary: {oil_analysis}
    - Regional Indices: {raw_regional_data}
    - Regional Commentary: {regional_analysis}
    - Deltas: {deltas}
    
    Tasks:
    1. Correlate news events with crude price movement and stock market sentiment.
    2. Determine a consolidated "conflict economics sentiment score" (sentiment_index) on a 1-10 scale (where 10 is high concern/panic).
    3. Construct and populate the fields for news_summary, oil_market (including Brent and WTI details), regional_indices (TADAWUL, TA_35, EGX_30, QE_Index), global_indicators (Gold, USD_Index), and deltas exactly as defined.
    4. Set the timestamp to the current ISO format UTC time.
    5. The final output must be exactly the JSON object representing the ConflictBriefing model.
    """,
    output_schema=ConflictBriefing,
    output_key="final_briefing",
    before_agent_callback=pre_synthesiser_callback,
    after_agent_callback=post_synthesiser_callback
)

# ==============================================================================
# PIPELINE ORCHESTRATOR INITIALIZATION
# ==============================================================================

# Coordinated sequential container initiating state bindings upon boot.
orchestrator = SequentialAgent(
    name="conflict_economics_orchestrator",
    sub_agents=[news_analyst, oil_analyst, regional_analyst, synthesiser],
    before_agent_callback=init_state_callback
)

# Export the ADK app running the root orchestrator.
app = App(
    root_agent=orchestrator,
    name="app",
)
