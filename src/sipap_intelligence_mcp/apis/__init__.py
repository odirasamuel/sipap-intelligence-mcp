"""External API clients (OpenWeatherMap, NewsAPI, API-Football)."""

from sipap_intelligence_mcp.apis.api_football import APIFootballIntelligenceClient
from sipap_intelligence_mcp.apis.newsapi import NewsAPIClient
from sipap_intelligence_mcp.apis.openweather import OpenWeatherMapClient

__all__ = ["APIFootballIntelligenceClient", "NewsAPIClient", "OpenWeatherMapClient"]
