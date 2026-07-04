# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

import datetime
import json
import os
import time
from typing import Dict, Any, List
import requests
import yfinance as yf
from google.adk.tools import ToolContext

# Directories for persistence
CACHE_DIR = "cache"
HISTORY_DIR = "history"
BRIEFINGS_FILE = os.path.join(HISTORY_DIR, "briefings.json")

# 1 hour cache TTL (in seconds)
CACHE_TTL = 1 * 3600

def _ensure_dirs():
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)

def _read_cache(cache_file: str) -> Any:
    _ensure_dirs()
    path = os.path.join(CACHE_DIR, cache_file)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            # Check TTL
            if time.time() - data.get("timestamp", 0) < CACHE_TTL:
                return data.get("payload")
        except Exception:
            pass
    return None

def _write_cache(cache_file: str, payload: Any):
    _ensure_dirs()
    path = os.path.join(CACHE_DIR, cache_file)
    try:
        with open(path, "w") as f:
            json.dump({"timestamp": time.time(), "payload": payload}, f, indent=2)
    except Exception:
        pass

def fetch_news_impact(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Queries NewsAPI and search engines for conflict-related economic news.
    
    Args:
        query: Search term for filtering news.
        
    Returns:
        A dictionary containing news headlines, sources, publish dates, and impact metadata.
    """
    cache_name = f"news_{query.replace(' ', '_').lower()}.json"
    cached = _read_cache(cache_name)
    if cached:
        tool_context.state["raw_news_data"] = cached
        return cached

    news_api_key = os.environ.get("NEWS_API_KEY")
    articles = []
    is_mock = False

    if news_api_key:
        try:
            url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&pageSize=10&apiKey={news_api_key}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for art in data.get("articles", []):
                    articles.append({
                        "title": art.get("title"),
                        "source": art.get("source", {}).get("name"),
                        "published_at": art.get("publishedAt"),
                        "url": art.get("url"),
                        "description": art.get("description"),
                        "impact_rating": "Medium"
                    })
            else:
                is_mock = True
        except Exception:
            is_mock = True
    else:
        is_mock = True

    if is_mock or not articles:
        is_mock = True
        current_time = datetime.datetime.utcnow().isoformat() + "Z"
        articles = [
            {
                "title": "Red Sea Shipping Halts: Insurance Premiums Jump 50% for Commercial Vessels",
                "source": "Global Maritime Finance",
                "published_at": current_time,
                "url": "https://example.com/shipping-insurance",
                "description": "Insurance underwriters raise premiums significantly as shipping lines divert around the Cape of Good Hope, increasing transit times by 10-14 days.",
                "impact_rating": "High"
            },
            {
                "title": "Strait of Hormuz Alert: Oil Tanker Transit Slows Under Increased Security Audits",
                "source": "Energy & Geopolitics Weekly",
                "published_at": current_time,
                "url": "https://example.com/hormuz-transit",
                "description": "Maritime authorities confirm a 12% drop in oil tanker speeds through the Strait of Hormuz due to heightened inspection protocols and military escorts.",
                "impact_rating": "High"
            },
            {
                "title": "Saudi Aramco Shares Show Resilience Despite Regional Crude Volatility",
                "source": "Middle East Markets Report",
                "published_at": current_time,
                "url": "https://example.com/aramco-shares",
                "description": "Aramco shares held steady at 31.20 SAR as oil price volatility balances against state dividend assurances.",
                "impact_rating": "Medium"
            },
            {
                "title": "Regional Air Freight Costs Spike as Flight Paths Rerouted to Avoid Airspace",
                "source": "Logistics Insider",
                "published_at": current_time,
                "url": "https://example.com/air-freight",
                "description": "Commercial carriers avoid regional airspace, forcing longer paths that add 15-20% fuel surcharges to Asia-Europe cargo routes.",
                "impact_rating": "Medium"
            },
            {
                "title": "Sovereign Bond Yields Rise Across Emerging Market Energy Importers",
                "source": "MacroDebt Analysis",
                "published_at": current_time,
                "url": "https://example.com/bond-yields",
                "description": "Bond yields for regional energy importers like Egypt and Jordan widen by 45 basis points as debt refinancing fears grow.",
                "impact_rating": "Medium"
            }
        ]

    payload = {
        "query": query,
        "articles": articles,
        "is_mock": is_mock,
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    _write_cache(cache_name, payload)
    tool_context.state["raw_news_data"] = payload
    return payload

def fetch_oil_markets(tool_context: ToolContext) -> Dict[str, Any]:
    """Pulls Brent and WTI crude prices, daily changes, and trends.
    
    Returns:
        A dictionary containing Brent and WTI market metrics.
    """
    cached = _read_cache("oil_markets.json")
    if cached:
        tool_context.state["raw_oil_data"] = cached
        return cached

    data = {}
    is_mock = False

    try:
        wti_ticker = yf.Ticker("CL=F")
        wti_history = wti_ticker.history(period="5d")
        
        brent_ticker = yf.Ticker("BZ=F")
        brent_history = brent_ticker.history(period="5d")

        if len(wti_history) >= 2 and len(brent_history) >= 2:
            wti_price = float(wti_history["Close"].iloc[-1])
            wti_prev = float(wti_history["Close"].iloc[-2])
            wti_change = wti_price - wti_prev
            wti_pct_change = (wti_change / wti_prev) * 100

            brent_price = float(brent_history["Close"].iloc[-1])
            brent_prev = float(brent_history["Close"].iloc[-2])
            brent_change = brent_price - brent_prev
            brent_pct_change = (brent_change / brent_prev) * 100

            wti_sma = float(wti_history["Close"].mean())
            brent_sma = float(brent_history["Close"].mean())

            data = {
                "WTI": {
                    "price": round(wti_price, 2),
                    "change": round(wti_change, 2),
                    "pct_change": round(wti_pct_change, 2),
                    "sma_5": round(wti_sma, 2),
                    "trend": "Bullish" if wti_price > wti_sma else "Bearish"
                },
                "Brent": {
                    "price": round(brent_price, 2),
                    "change": round(brent_change, 2),
                    "pct_change": round(brent_pct_change, 2),
                    "sma_5": round(brent_sma, 2),
                    "trend": "Bullish" if brent_price > brent_sma else "Bearish"
                }
            }
        else:
            is_mock = True
    except Exception:
        is_mock = True

    if is_mock or not data:
        is_mock = True
        data = {
            "WTI": {
                "price": 78.45,
                "change": 1.25,
                "pct_change": 1.62,
                "sma_5": 77.90,
                "trend": "Bullish"
            },
            "Brent": {
                "price": 83.10,
                "change": 1.45,
                "pct_change": 1.78,
                "sma_5": 82.35,
                "trend": "Bullish"
            }
        }

    payload = {
        "markets": data,
        "is_mock": is_mock,
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    _write_cache("oil_markets.json", payload)
    tool_context.state["raw_oil_data"] = payload
    return payload

def fetch_regional_indices(tool_context: ToolContext) -> Dict[str, Any]:
    """Pulls stock indices for Middle East markets and safe haven commodities.
    
    Returns:
        A dictionary containing regional stock indices and safe haven assets.
    """
    cached = _read_cache("regional_indices.json")
    if cached:
        tool_context.state["raw_regional_data"] = cached
        return cached

    tickers = {
        "TADAWUL": "^TASI",
        "TA-35": "^TA35.TA",
        "EGX-30": "^EGX30",
        "QE-Index": "^QSI",
        "Gold": "GC=F",
        "USD-Index": "DX-Y.NYB"
    }

    data = {}
    is_mock = False

    try:
        for name, symbol in tickers.items():
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if len(hist) >= 2:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                change = price - prev
                pct_change = (change / prev) * 100
                data[name] = {
                    "level": round(price, 2),
                    "change": round(change, 2),
                    "pct_change": round(pct_change, 2)
                }
            else:
                raise ValueError(f"Insufficient history for {name}")
    except Exception:
        is_mock = True

    if is_mock or len(data) < len(tickers):
        is_mock = True
        data = {
            "TADAWUL": {"level": 11724.80, "change": -45.20, "pct_change": -0.38},
            "TA-35": {"level": 1948.15, "change": -22.40, "pct_change": -1.14},
            "EGX-30": {"level": 28410.20, "change": 120.50, "pct_change": 0.43},
            "QE-Index": {"level": 9812.50, "change": -15.10, "pct_change": -0.15},
            "Gold": {"level": 2345.80, "change": 18.50, "pct_change": 0.79},
            "USD-Index": {"level": 105.42, "change": 0.31, "pct_change": 0.29}
        }

    payload = {
        "indices": data,
        "is_mock": is_mock,
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    _write_cache("regional_indices.json", payload)
    tool_context.state["raw_regional_data"] = payload
    return payload

def calculate_deltas(current_data: Dict[str, Any]) -> Dict[str, Any]:
    """Reads past briefings from history and calculates delta changes.
    
    Saves the current run into history list.
    """
    _ensure_dirs()
    history = []
    
    if os.path.exists(BRIEFINGS_FILE):
        try:
            with open(BRIEFINGS_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass

    deltas = {
        "brent_change_pct": 0.0,
        "wti_change_pct": 0.0,
        "tadawul_change_pct": 0.0,
        "ta35_change_pct": 0.0,
        "gold_change_pct": 0.0,
        "sentiment_shift": 0.0,
        "days_since_last_briefing": 1
    }

    if history:
        last = history[-1]
        try:
            if "markets" in current_data.get("oil_market", {}):
                wti_now = current_data["oil_market"]["markets"]["WTI"]["price"]
                brent_now = current_data["oil_market"]["markets"]["Brent"]["price"]
            else:
                wti_now = current_data["oil_market"]["WTI"]["price"]
                brent_now = current_data["oil_market"]["Brent"]["price"]

            if "indices" in current_data.get("regional_indices", {}):
                t_now = current_data["regional_indices"]["indices"]["TADAWUL"]["level"]
                ta_now = current_data["regional_indices"]["indices"]["TA-35"]["level"]
                g_now = current_data["regional_indices"]["indices"]["Gold"]["level"]
            else:
                t_now = current_data["regional_indices"]["TADAWUL"]["level"]
                ta_now = current_data["regional_indices"].get("TA_35", {}).get("level") or current_data["regional_indices"].get("TA-35", {}).get("level")
                g_now = current_data["global_indicators"]["Gold"]["level"]

            wti_prev = last["oil_market"]["WTI"]["price"]
            deltas["wti_change_pct"] = round(((wti_now - wti_prev) / wti_prev) * 100, 2)
            
            brent_prev = last["oil_market"]["Brent"]["price"]
            deltas["brent_change_pct"] = round(((brent_now - brent_prev) / brent_prev) * 100, 2)
            
            t_prev = last["regional_indices"]["TADAWUL"]["level"]
            deltas["tadawul_change_pct"] = round(((t_now - t_prev) / t_prev) * 100, 2)
            
            ta_prev = last["regional_indices"].get("TA_35", {}).get("level") or last["regional_indices"].get("TA-35", {}).get("level")
            if ta_prev:
                deltas["ta35_change_pct"] = round(((ta_now - ta_prev) / ta_prev) * 100, 2)
            
            g_prev = last["global_indicators"]["Gold"]["level"]
            deltas["gold_change_pct"] = round(((g_now - g_prev) / g_prev) * 100, 2)

            s_now = current_data.get("sentiment_index", 5.0)
            s_prev = last.get("sentiment_index", 5.0)
            deltas["sentiment_shift"] = round(s_now - s_prev, 1)

            t1 = datetime.datetime.fromisoformat(current_data["timestamp"].replace("Z", "+00:00"))
            t0 = datetime.datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00"))
            deltas["days_since_last_briefing"] = max((t1 - t0).days, 1)
        except Exception:
            pass

    return deltas

def save_to_history(full_briefing: Dict[str, Any]):
    """Appends a fully generated briefing to local history files."""
    _ensure_dirs()
    history = []
    if os.path.exists(BRIEFINGS_FILE):
        try:
            with open(BRIEFINGS_FILE, "r") as f:
                history = json.load(f)
        except Exception:
            pass

    history.append(full_briefing)
    
    if len(history) > 30:
        history = history[-30:]
        
    try:
        with open(BRIEFINGS_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass
