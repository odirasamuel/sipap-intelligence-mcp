"""SIPAP Intelligence MCP Server.

AI-powered intelligence tools for sports prediction:
- News sentiment analysis (Claude/Bedrock)
- Injury impact assessment (Claude/Bedrock)
- Weather intelligence (OpenWeatherMap + Claude)
- Historical weather performance analysis
"""

__version__ = "0.1.0"

from sipap_intelligence_mcp.exceptions import (
    ClaudeAPIException,
    IntelligenceMCPException,
    NewsAPIException,
    WeatherAPIException,
)

__all__ = [
    "IntelligenceMCPException",
    "WeatherAPIException",
    "NewsAPIException",
    "ClaudeAPIException",
]
