"""Weather intelligence tools for MCP server.

Provides weather data and AI-powered impact analysis for matches.
"""

import os
from typing import Any

from sipap_common.cache import RedisCache  # type: ignore[import-untyped]

from sipap_intelligence_mcp.ai.claude import ClaudeBedrockClient
from sipap_intelligence_mcp.ai.prompts import PromptTemplates
from sipap_intelligence_mcp.apis.weather import OpenWeatherMapClient

# Global clients for Lambda warm start optimization (Sentinel Pattern #19)
_weather_client: OpenWeatherMapClient | None = None
_claude_client: ClaudeBedrockClient | None = None
_cache: RedisCache | None = None


def _get_weather_client() -> OpenWeatherMapClient:
    """Get or create weather API client (cached for warm starts)."""
    global _weather_client
    if _weather_client is None:
        api_key = os.getenv("OPENWEATHER_API_KEY", "")
        _weather_client = OpenWeatherMapClient(api_key=api_key)
    return _weather_client


def _get_claude_client() -> ClaudeBedrockClient:
    """Get or create Claude/Bedrock client (cached for warm starts)."""
    global _claude_client
    if _claude_client is None:
        region = os.getenv("AWS_REGION", "us-east-1")
        _claude_client = ClaudeBedrockClient(region=region)
    return _claude_client


def _get_cache() -> RedisCache | None:
    """Get or create Redis cache (cached for warm starts)."""
    global _cache
    if _cache is None:
        redis_endpoint = os.getenv("REDIS_ENDPOINT")
        if redis_endpoint:
            _cache = RedisCache(endpoint=redis_endpoint)
    return _cache


async def get_match_weather(
    match_id: str,
    lat: float | None = None,
    lon: float | None = None,
    city: str | None = None
) -> dict[str, Any]:
    """Get weather forecast for match location.

    MCP Tool: Fetches current weather or forecast for match venue.

    Args:
        match_id: Match identifier for caching
        lat: Latitude of match venue
        lon: Longitude of match venue
        city: City name (alternative to lat/lon)

    Returns:
        Weather data with:
            - temperature: Temperature in Celsius
            - precipitation: Precipitation type
            - wind_speed: Wind speed in m/s
            - humidity: Humidity percentage
            - visibility: Visibility in meters
            - weather_description: Human-readable description

    Raises:
        ValueError: If neither (lat, lon) nor city provided
    """
    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    if cache:
        cache_key = f"weather:match:{match_id}"
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch weather
    weather_client = _get_weather_client()

    if lat is not None and lon is not None:
        weather = await weather_client.get_weather_by_coordinates(lat=lat, lon=lon)
    elif city:
        weather = await weather_client.get_weather_by_city(city=city)
    else:
        raise ValueError("Must provide either (lat, lon) or city")

    # Cache result (1 hour TTL)
    if cache:
        await cache.set(cache_key, weather, ttl=3600)

    return weather


async def assess_weather_impact(
    weather_conditions: dict[str, Any],
    match_type: str = "soccer",
    home_team: str | None = None,
    away_team: str | None = None
) -> dict[str, Any]:
    """Assess weather impact on match using AI analysis.

    MCP Tool: Uses Claude to analyze how weather affects match outcome.

    Args:
        weather_conditions: Weather data from get_match_weather()
        match_type: Type of match (soccer, nba, nfl)
        home_team: Home team name (for contextualized analysis)
        away_team: Away team name (for contextualized analysis)

    Returns:
        Impact assessment with:
            - impact_level: low, medium, high
            - confidence: 0.0-1.0
            - factors: List of weather factors affecting play
            - betting_implications: Specific betting insights
    """
    # Generate AI analysis prompt
    prompt = PromptTemplates.weather_impact_prompt(weather_conditions, match_type)
    system_prompt = PromptTemplates.weather_impact_system_prompt()
    schema = PromptTemplates.get_response_schema("weather")

    # Add team context if provided
    if home_team and away_team:
        context = f"Match: {home_team} vs {away_team}"
        prompt = f"{context}\n\n{prompt}"

    # Get Claude analysis
    claude = _get_claude_client()
    result = await claude.analyze_text(
        prompt=prompt,
        system_prompt=system_prompt,
        response_schema=schema,
        max_tokens=400,
        temperature=0.6
    )

    return result


async def get_historical_weather_performance(
    team_id: str,
    team_name: str,
    weather_type: str,
    max_matches: int = 10
) -> dict[str, Any]:
    """Analyze team's historical performance in specific weather.

    MCP Tool: Uses historical data + AI to identify performance patterns.

    Args:
        team_id: Team identifier
        team_name: Team name for display
        weather_type: Type of weather (rain, snow, wind, heat)
        max_matches: Maximum historical matches to analyze

    Returns:
        Historical analysis with:
            - pattern_strength: weak, moderate, strong
            - confidence: 0.0-1.0
            - win_rate: Percentage (0-100)
            - avg_goals_scored: Average goals scored
            - avg_goals_conceded: Average goals conceded
            - key_insight: Main betting takeaway
    """
    # TODO: In production, fetch from database
    # For MVP, use mock historical data
    historical_data = _get_mock_historical_data(team_id, weather_type, max_matches)

    # Generate AI analysis prompt
    prompt = PromptTemplates.historical_weather_performance_prompt(
        team_name=team_name,
        weather_type=weather_type,
        historical_data=historical_data
    )
    system_prompt = PromptTemplates.historical_weather_performance_system_prompt()
    schema = PromptTemplates.get_response_schema("historical")

    # Get Claude analysis
    claude = _get_claude_client()
    result = await claude.analyze_text(
        prompt=prompt,
        system_prompt=system_prompt,
        response_schema=schema,
        max_tokens=500,
        temperature=0.5
    )

    return result


def _get_mock_historical_data(
    team_id: str,
    weather_type: str,
    max_matches: int
) -> list[dict[str, Any]]:
    """Get mock historical data (placeholder for database query).

    Args:
        team_id: Team identifier
        weather_type: Weather condition
        max_matches: Maximum matches to return

    Returns:
        List of historical match data
    """
    # Mock data for development/testing
    return [
        {
            "date": "2024-01-15",
            "result": "W",
            "score": "2-1",
            "opponent": "Team A",
            "weather": weather_type
        },
        {
            "date": "2024-01-08",
            "result": "D",
            "score": "1-1",
            "opponent": "Team B",
            "weather": weather_type
        },
        {
            "date": "2023-12-20",
            "result": "L",
            "score": "0-2",
            "opponent": "Team C",
            "weather": weather_type
        }
    ][:max_matches]
