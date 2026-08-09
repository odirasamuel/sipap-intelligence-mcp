"""MCP tools for AI-powered intelligence analysis."""

from sipap_intelligence_mcp.tools.api_football_intelligence import (
    get_available_timezones,
    get_match_predictions,
    get_player_transfers,
    get_sidelined_players,
)
from sipap_intelligence_mcp.tools.news import (
    analyze_team_news,
    fetch_and_analyze_team_news,
    get_injury_reports,
)
from sipap_intelligence_mcp.tools.weather import (
    assess_weather_impact,
    get_historical_weather_performance,
    get_match_weather,
)

__all__ = [
    # Weather intelligence tools
    "get_match_weather",
    "assess_weather_impact",
    "get_historical_weather_performance",
    # News intelligence tools
    "fetch_and_analyze_team_news",
    "analyze_team_news",
    "get_injury_reports",
    # API-Football intelligence tools
    "get_match_predictions",
    "get_sidelined_players",
    "get_player_transfers",
    "get_available_timezones",
]
