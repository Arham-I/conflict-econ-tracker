# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# Model Context Protocol (MCP) Server for Conflict Economics Tools
# This server wraps our custom data collection tools, making them discoverable
# and executable by any MCP-compliant client (e.g., Gemini Enterprise, Claude Desktop).

import os
import sys
from mcp.server.fastmcp import FastMCP

# Ensure the root directory is in the path so we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.tools import fetch_news_impact, fetch_oil_markets, fetch_regional_indices

# Initialize FastMCP Server
mcp = FastMCP("Conflict Economics Tools Server")

@mcp.tool()
def get_news_impact(query: str = "Middle East economic impact") -> str:
    """
    Fetch recent geopolitical news articles and assess their economic impact.
    
    Args:
        query: The search query to locate news articles (default: 'Middle East economic impact').
        
    Returns:
        A JSON string containing the title, source, impact rating (High/Medium/Low),
        and summary of recent news events.
    """
    try:
        data = fetch_news_impact(query)
        import json
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error fetching news: {str(e)}"

@mcp.tool()
def get_oil_markets() -> str:
    """
    Fetch current Brent and WTI crude futures prices, daily percentage changes,
    and 5-day Simple Moving Average (SMA) trends.
    
    Returns:
        A JSON string containing benchmarks details, daily performance, and trend direction.
    """
    try:
        data = fetch_oil_markets()
        import json
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error fetching oil metrics: {str(e)}"

@mcp.tool()
def get_regional_indices() -> str:
    """
    Fetch regional stock index levels (TADAWUL, TA-35, EGX-30, QE-Index)
    along with safe-haven assets (Gold and USD Index).
    
    Returns:
        A JSON string containing index levels, daily changes, and percentage changes.
    """
    try:
        data = fetch_regional_indices()
        import json
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error fetching regional indices: {str(e)}"

if __name__ == "__main__":
    # Run the FastMCP server (default mode is standard input/output transport layer)
    mcp.run()
