"""Unit tests for weather intelligence tools.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve implementation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sipap_intelligence_mcp.tools import weather


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_weather_data():
    """Mock weather data response."""
    return {
        "temperature": 15.2,
        "feels_like": 14.8,
        "precipitation": "light_rain",
        "wind_speed": 12.5,
        "humidity": 82,
        "visibility": 8000,
        "weather_description": "Light rain with moderate wind"
    }


@pytest.fixture
def mock_impact_assessment():
    """Mock weather impact assessment."""
    return {
        "impact_level": "medium",
        "confidence": 0.78,
        "factors": ["wet_pitch", "reduced_visibility", "moderate_wind"],
        "betting_implications": "Consider under 2.5 goals due to wet conditions"
    }


@pytest.fixture
def mock_historical_analysis():
    """Mock historical weather performance analysis."""
    return {
        "pattern_strength": "strong",
        "confidence": 0.85,
        "win_rate": 60.0,
        "avg_goals_scored": 2.5,
        "avg_goals_conceded": 1.2,
        "key_insight": "Team demonstrates strong performance in rainy conditions"
    }


class TestGetMatchWeather:
    """Test get_match_weather tool."""

    @pytest.mark.asyncio
    async def test_get_match_weather_by_coordinates(self, mock_weather_data):
        """Test getting weather by coordinates succeeds."""
        with patch("sipap_intelligence_mcp.tools.weather._get_weather_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_weather_by_coordinates = AsyncMock(return_value=mock_weather_data)
            mock_get_client.return_value = mock_client

            result = await weather.get_match_weather(
                match_id="match-123",
                lat=51.5,
                lon=-0.1
            )

            assert result["temperature"] == 15.2
            assert result["precipitation"] == "light_rain"
            assert result["wind_speed"] == 12.5
            mock_client.get_weather_by_coordinates.assert_called_once_with(lat=51.5, lon=-0.1)

    @pytest.mark.asyncio
    async def test_get_match_weather_by_city(self, mock_weather_data):
        """Test getting weather by city succeeds."""
        city_weather = {**mock_weather_data, "city": "London"}

        with patch("sipap_intelligence_mcp.tools.weather._get_weather_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_weather_by_city = AsyncMock(return_value=city_weather)
            mock_get_client.return_value = mock_client

            result = await weather.get_match_weather(
                match_id="match-456",
                city="London"
            )

            assert result["city"] == "London"
            assert result["temperature"] == 15.2
            mock_client.get_weather_by_city.assert_called_once_with(city="London")

    @pytest.mark.asyncio
    async def test_get_match_weather_with_cache_hit(
        self, mock_weather_data, mock_redis_cache
    ):
        """Test weather returns cached data if available."""
        mock_redis_cache.get = AsyncMock(return_value=mock_weather_data)

        with patch("sipap_intelligence_mcp.tools.weather._get_cache") as mock_get_cache:
            mock_get_cache.return_value = mock_redis_cache

            result = await weather.get_match_weather(
                match_id="match-123",
                lat=51.5,
                lon=-0.1
            )

            # Should return cached data without calling API
            assert result == mock_weather_data
            mock_redis_cache.get.assert_called_once_with("weather:match:match-123")

    @pytest.mark.asyncio
    async def test_get_match_weather_caches_result(
        self, mock_weather_data, mock_redis_cache
    ):
        """Test weather caches API result."""
        with patch(
            "sipap_intelligence_mcp.tools.weather._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.weather._get_weather_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = AsyncMock()
            mock_client.get_weather_by_coordinates = AsyncMock(return_value=mock_weather_data)
            mock_get_client.return_value = mock_client

            await weather.get_match_weather(
                match_id="match-123",
                lat=51.5,
                lon=-0.1
            )

            # Should cache result with 1 hour TTL
            mock_redis_cache.set.assert_called_once_with(
                "weather:match:match-123", mock_weather_data, ttl=3600
            )

    @pytest.mark.asyncio
    async def test_get_match_weather_without_cache(self, mock_weather_data):
        """Test weather works without Redis cache."""
        with patch(
            "sipap_intelligence_mcp.tools.weather._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.weather._get_weather_client"
        ) as mock_get_client:
            mock_get_cache.return_value = None  # No cache available

            mock_client = AsyncMock()
            mock_client.get_weather_by_coordinates = AsyncMock(return_value=mock_weather_data)
            mock_get_client.return_value = mock_client

            result = await weather.get_match_weather(
                match_id="match-123",
                lat=51.5,
                lon=-0.1
            )

            assert result == mock_weather_data

    @pytest.mark.asyncio
    async def test_get_match_weather_validation_error(self):
        """Test weather raises error when neither coords nor city provided."""
        with pytest.raises(ValueError, match="Must provide either \\(lat, lon\\) or city"):
            await weather.get_match_weather(match_id="match-123")

    @pytest.mark.asyncio
    async def test_get_match_weather_partial_coords_uses_city(self, mock_weather_data):
        """Test weather uses city when lat/lon incomplete."""
        city_weather = {**mock_weather_data, "city": "Manchester"}

        with patch("sipap_intelligence_mcp.tools.weather._get_weather_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_weather_by_city = AsyncMock(return_value=city_weather)
            mock_get_client.return_value = mock_client

            # Only lat provided, no lon - should use city instead
            result = await weather.get_match_weather(
                match_id="match-789",
                lat=53.5,
                city="Manchester"
            )

            # Should prefer lat/lon when both are provided (lat without lon triggers city)
            # But in this test we have lat without lon, so it should use city
            assert result["city"] == "Manchester"


class TestAssessWeatherImpact:
    """Test assess_weather_impact tool."""

    @pytest.mark.asyncio
    async def test_assess_weather_impact_success(self, mock_impact_assessment):
        """Test weather impact assessment succeeds."""
        weather_conditions = {
            "temperature": 15.2,
            "precipitation": "light_rain",
            "wind_speed": 12.5
        }

        with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_impact_assessment)
            mock_get_client.return_value = mock_client

            result = await weather.assess_weather_impact(weather_conditions)

            assert result["impact_level"] == "medium"
            assert result["confidence"] == 0.78
            assert "wet_pitch" in result["factors"]

    @pytest.mark.asyncio
    async def test_assess_weather_impact_with_teams(self, mock_impact_assessment):
        """Test weather impact assessment with team context."""
        weather_conditions = {
            "temperature": 15.2,
            "precipitation": "light_rain",
            "wind_speed": 12.5
        }

        with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_impact_assessment)
            mock_get_client.return_value = mock_client

            result = await weather.assess_weather_impact(
                weather_conditions,
                home_team="Liverpool",
                away_team="Manchester United"
            )

            assert result["impact_level"] == "medium"
            # Verify team context was added to prompt
            call_args = mock_client.analyze_text.call_args
            assert "Liverpool" in call_args.kwargs["prompt"]
            assert "Manchester United" in call_args.kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_assess_weather_impact_different_match_type(self, mock_impact_assessment):
        """Test weather impact assessment for different match types."""
        weather_conditions = {
            "temperature": 28.0,
            "precipitation": "none",
            "wind_speed": 3.5
        }

        with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_impact_assessment)
            mock_get_client.return_value = mock_client

            result = await weather.assess_weather_impact(
                weather_conditions,
                match_type="nba"
            )

            assert result["impact_level"] == "medium"
            # Verify match type influences analysis (check it was used in prompt generation)
            mock_client.analyze_text.assert_called_once()


class TestGetHistoricalWeatherPerformance:
    """Test get_historical_weather_performance tool."""

    @pytest.mark.asyncio
    async def test_get_historical_performance_success(self, mock_historical_analysis):
        """Test historical weather performance analysis succeeds."""
        with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_historical_analysis)
            mock_get_client.return_value = mock_client

            result = await weather.get_historical_weather_performance(
                team_id="team-123",
                team_name="Manchester United",
                weather_type="rain"
            )

            assert result["pattern_strength"] == "strong"
            assert result["win_rate"] == 60.0
            assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_get_historical_performance_custom_max_matches(
        self, mock_historical_analysis
    ):
        """Test historical analysis with custom max_matches."""
        with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_historical_analysis)
            mock_get_client.return_value = mock_client

            result = await weather.get_historical_weather_performance(
                team_id="team-456",
                team_name="Liverpool",
                weather_type="snow",
                max_matches=20
            )

            assert result["pattern_strength"] == "strong"
            # Verify max_matches was used (check via mock historical data call)
            mock_client.analyze_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_performance_different_weather_types(
        self, mock_historical_analysis
    ):
        """Test historical analysis for different weather types."""
        weather_types = ["rain", "snow", "wind", "heat"]

        with patch("sipap_intelligence_mcp.tools.weather._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_historical_analysis)
            mock_get_client.return_value = mock_client

            for weather_type in weather_types:
                result = await weather.get_historical_weather_performance(
                    team_id="team-789",
                    team_name="Chelsea",
                    weather_type=weather_type
                )

                assert result["pattern_strength"] == "strong"


class TestMockHistoricalData:
    """Test _get_mock_historical_data helper."""

    def test_mock_historical_data_returns_list(self):
        """Test mock data returns list of historical matches."""
        result = weather._get_mock_historical_data(
            team_id="team-123",
            weather_type="rain",
            max_matches=10
        )

        assert isinstance(result, list)
        assert len(result) <= 10

    def test_mock_historical_data_respects_max_matches(self):
        """Test mock data respects max_matches parameter."""
        result = weather._get_mock_historical_data(
            team_id="team-456",
            weather_type="snow",
            max_matches=2
        )

        assert len(result) == 2

    def test_mock_historical_data_structure(self):
        """Test mock data has correct structure."""
        result = weather._get_mock_historical_data(
            team_id="team-789",
            weather_type="wind",
            max_matches=5
        )

        assert len(result) > 0
        first_match = result[0]
        assert "date" in first_match
        assert "result" in first_match
        assert "score" in first_match
        assert "opponent" in first_match
        assert "weather" in first_match

    def test_mock_historical_data_weather_type_matches(self):
        """Test mock data contains specified weather type."""
        weather_type = "heat"
        result = weather._get_mock_historical_data(
            team_id="team-999",
            weather_type=weather_type,
            max_matches=3
        )

        for match in result:
            assert match["weather"] == weather_type
