"""Unit tests for weather intelligence tools."""

from unittest.mock import AsyncMock, patch

import pytest

from sipap_intelligence_mcp.tools.weather import (
    assess_weather_impact,
    get_historical_weather_performance,
    get_match_weather,
)


@pytest.mark.asyncio
async def test_get_match_weather_by_coordinates():
    """Test getting weather by coordinates."""
    with patch("sipap_intelligence_mcp.tools.weather._get_weather_client") as mock_client:
        mock_weather = AsyncMock()
        mock_weather.get_weather_by_coordinates.return_value = {
            "temperature": 15.2,
            "precipitation": "light_rain",
            "wind_speed": 12.5
        }
        mock_client.return_value = mock_weather

        result = await get_match_weather(
            match_id="match-123",
            lat=51.5,
            lon=-0.1
        )

        assert result["temperature"] == 15.2
        assert result["precipitation"] == "light_rain"


@pytest.mark.asyncio
async def test_get_match_weather_by_city():
    """Test getting weather by city."""
    with patch("sipap_intelligence_mcp.tools.weather._get_weather_client") as mock_client:
        mock_weather = AsyncMock()
        mock_weather.get_weather_by_city.return_value = {
            "temperature": 20.0,
            "city": "London"
        }
        mock_client.return_value = mock_weather

        result = await get_match_weather(
            match_id="match-456",
            city="London"
        )

        assert result["city"] == "London"


@pytest.mark.asyncio
async def test_assess_weather_impact():
    """Test weather impact assessment."""
    weather_conditions = {
        "temperature": 15.2,
        "precipitation": "light_rain",
        "wind_speed": 12.5
    }

    with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_client:
        mock_claude = AsyncMock()
        mock_claude.analyze_text.return_value = {
            "impact_level": "medium",
            "confidence": 0.78,
            "factors": ["wet_pitch", "wind"],
            "betting_implications": "Consider under 2.5 goals"
        }
        mock_client.return_value = mock_claude

        result = await assess_weather_impact(weather_conditions)

        assert result["impact_level"] == "medium"
        assert result["confidence"] == 0.78


@pytest.mark.asyncio
async def test_get_historical_weather_performance():
    """Test historical weather performance analysis."""
    with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_client:
        mock_claude = AsyncMock()
        mock_claude.analyze_text.return_value = {
            "pattern_strength": "strong",
            "confidence": 0.85,
            "win_rate": 60.0,
            "avg_goals_scored": 2.5,
            "key_insight": "Team performs well in rain"
        }
        mock_client.return_value = mock_claude

        result = await get_historical_weather_performance(
            team_id="team-123",
            team_name="Manchester United",
            weather_type="rain"
        )

        assert result["pattern_strength"] == "strong"
        assert result["win_rate"] == 60.0
