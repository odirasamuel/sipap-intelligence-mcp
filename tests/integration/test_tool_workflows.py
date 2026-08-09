"""Integration tests for complete tool workflows.

Tests end-to-end workflows from MCP server through tools to external APIs.
Uses mocked external dependencies (OpenWeather, NewsAPI, API-Football, Claude).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sipap_intelligence_mcp.server import IntelligenceMCPServer


@pytest.fixture
def mock_weather_response():
    """Mock OpenWeather API response."""
    return {
        "temperature": 15.2,
        "feels_like": 14.8,
        "precipitation": "light_rain",
        "wind_speed": 12.5,
        "humidity": 82,
        "visibility": 8000,
        "weather_description": "Light rain",
        "city": "London"
    }


@pytest.fixture
def mock_claude_response():
    """Mock Claude/Bedrock response."""
    return {
        "impact_level": "medium",
        "confidence": 0.78,
        "factors": ["wet_pitch", "reduced_visibility"],
        "betting_implications": "Consider under 2.5 goals"
    }


@pytest.fixture
def mock_news_articles():
    """Mock NewsAPI articles."""
    return [
        {
            "title": "Team wins 3-0",
            "source": "ESPN",
            "published_at": "2024-07-10T14:30:00Z",
            "description": "Dominant win",
            "content": "Team delivered outstanding performance",
            "url": "https://espn.com/article1"
        }
    ]


@pytest.fixture
def mock_predictions_response():
    """Mock API-Football predictions response."""
    return {
        "predictions": {
            "winner": {"id": 42, "name": "Liverpool"},
            "percent": {"home": "63%", "draw": "22%", "away": "15%"}
        },
        "league": {"id": 39, "name": "Premier League"},
        "teams": {
            "home": {"id": 42, "name": "Liverpool"},
            "away": {"id": 33, "name": "Manchester United"}
        }
    }


class TestWeatherWorkflow:
    """Test complete weather intelligence workflow."""

    @pytest.mark.asyncio
    async def test_get_match_weather_workflow(self, mock_weather_response):
        """Test complete get_match_weather workflow via MCP server."""
        server = IntelligenceMCPServer()

        with patch(
            "sipap_intelligence_mcp.tools.weather._get_weather_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_weather_by_coordinates = AsyncMock(
                return_value=mock_weather_response
            )
            mock_get_client.return_value = mock_client

            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_match_weather",
                    "arguments": {
                        "match_id": "match-123",
                        "lat": 51.5,
                        "lon": -0.1
                    }
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert "result" in response
            assert "content" in response["result"]
            assert len(response["result"]["content"]) > 0
            assert response["result"]["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_assess_weather_impact_workflow(
        self, mock_weather_response, mock_claude_response
    ):
        """Test complete weather impact assessment workflow."""
        server = IntelligenceMCPServer()

        with patch(
            "sipap_intelligence_mcp.tools.weather._get_claude_client"
        ) as mock_get_claude:
            mock_claude = AsyncMock()
            mock_claude.analyze_text = AsyncMock(return_value=mock_claude_response)
            mock_get_claude.return_value = mock_claude

            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "assess_weather_impact",
                    "arguments": {
                        "weather_conditions": mock_weather_response,
                        "match_type": "soccer",
                        "home_team": "Liverpool",
                        "away_team": "Manchester United"
                    }
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            # Verify Claude was called with team context
            mock_claude.analyze_text.assert_called_once()


class TestNewsWorkflow:
    """Test complete news intelligence workflow."""

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_news_workflow(
        self, mock_news_articles, mock_claude_response
    ):
        """Test complete news fetching and analysis workflow."""
        server = IntelligenceMCPServer()

        sentiment_result = {
            "sentiment": "positive",
            "confidence": 0.90,
            "key_topics": ["winning_streak"],
            "impact_summary": "High confidence"
        }

        with patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_claude:
            # Mock NewsAPI client
            mock_news_client = MagicMock()
            mock_news_client.__aenter__ = AsyncMock(return_value=mock_news_client)
            mock_news_client.__aexit__ = AsyncMock()
            mock_news_client.search_team_news = AsyncMock(return_value=mock_news_articles)
            mock_get_news.return_value = mock_news_client

            # Mock Claude client
            mock_claude = AsyncMock()
            mock_claude.analyze_text = AsyncMock(return_value=sentiment_result)
            mock_get_claude.return_value = mock_claude

            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "fetch_and_analyze_team_news",
                    "arguments": {
                        "team_id": "team-123",
                        "team_name": "Liverpool",
                        "days_back": 7
                    }
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            # Verify both NewsAPI and Claude were called
            mock_news_client.search_team_news.assert_called_once()
            mock_claude.analyze_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_injury_reports_workflow(self, mock_claude_response):
        """Test complete injury reports workflow."""
        server = IntelligenceMCPServer()

        with patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_claude:
            mock_claude = AsyncMock()
            mock_claude.analyze_text = AsyncMock(return_value=mock_claude_response)
            mock_get_claude.return_value = mock_claude

            request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_injury_reports",
                    "arguments": {
                        "team_id": "team-456",
                        "team_name": "Chelsea",
                        "severity_filter": "all"
                    }
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            mock_claude.analyze_text.assert_called_once()


class TestAPIFootballWorkflow:
    """Test complete API-Football intelligence workflow."""

    @pytest.mark.asyncio
    async def test_get_match_predictions_workflow(self, mock_predictions_response):
        """Test complete match predictions workflow."""
        server = IntelligenceMCPServer()

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_predictions = AsyncMock(return_value=mock_predictions_response)
            mock_get_client.return_value = mock_client

            request = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_match_predictions",
                    "arguments": {
                        "fixture_id": 198772
                    }
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            mock_client.get_predictions.assert_called_once_with(198772)

    @pytest.mark.asyncio
    async def test_get_sidelined_players_workflow(self):
        """Test complete sidelined players workflow."""
        server = IntelligenceMCPServer()

        sidelined_data = [
            {
                "type": "Missing Fixture",
                "player": {"id": 306, "name": "M. Salah"},
                "start": "2024-07-01"
            }
        ]

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_sidelined_by_player = AsyncMock(return_value=sidelined_data)
            mock_get_client.return_value = mock_client

            request = {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "get_sidelined_players",
                    "arguments": {
                        "player_id": 306
                    }
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            mock_client.get_sidelined_by_player.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_available_timezones_workflow(self):
        """Test complete timezones workflow."""
        server = IntelligenceMCPServer()

        timezones = ["Europe/London", "America/New_York", "Asia/Tokyo"]

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_timezones = AsyncMock(return_value=timezones)
            mock_get_client.return_value = mock_client

            request = {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "get_available_timezones",
                    "arguments": {}
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            mock_client.get_timezones.assert_called_once()


class TestErrorHandlingWorkflow:
    """Test error handling across component boundaries."""

    @pytest.mark.asyncio
    async def test_tool_validation_error_propagates(self):
        """Test validation errors propagate correctly."""
        server = IntelligenceMCPServer()

        # Missing required match_id
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "get_match_weather",
                "arguments": {
                    "lat": 51.5,
                    "lon": -0.1
                    # Missing match_id
                }
            }
        }

        response = await server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 8
        assert "error" in response
        # Should get internal error due to missing required parameter

    @pytest.mark.asyncio
    async def test_api_error_propagates(self):
        """Test external API errors propagate correctly."""
        server = IntelligenceMCPServer()

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            # Simulate API error
            mock_client.get_predictions = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )
            mock_get_client.return_value = mock_client

            request = {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "get_match_predictions",
                    "arguments": {"fixture_id": 999999}
                }
            }

            response = await server.handle_request(request)

            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 9
            assert "error" in response
            assert response["error"]["code"] == -32603


class TestCrossComponentIntegration:
    """Test interactions between multiple components."""

    @pytest.mark.asyncio
    async def test_weather_and_news_for_same_match(
        self, mock_weather_response, mock_news_articles, mock_claude_response
    ):
        """Test fetching weather and news for the same match."""
        server = IntelligenceMCPServer()

        # First get weather
        with patch(
            "sipap_intelligence_mcp.tools.weather._get_weather_client"
        ) as mock_weather_client:
            mock_client = AsyncMock()
            mock_client.get_weather_by_city = AsyncMock(return_value=mock_weather_response)
            mock_weather_client.return_value = mock_client

            weather_request = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "get_match_weather",
                    "arguments": {
                        "match_id": "match-final",
                        "city": "London"
                    }
                }
            }

            weather_response = await server.handle_request(weather_request)
            assert "result" in weather_response

        # Then get news
        with patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_claude:
            mock_news_client = MagicMock()
            mock_news_client.__aenter__ = AsyncMock(return_value=mock_news_client)
            mock_news_client.__aexit__ = AsyncMock()
            mock_news_client.search_team_news = AsyncMock(return_value=mock_news_articles)
            mock_get_news.return_value = mock_news_client

            mock_claude = AsyncMock()
            mock_claude.analyze_text = AsyncMock(return_value=mock_claude_response)
            mock_get_claude.return_value = mock_claude

            news_request = {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "fetch_and_analyze_team_news",
                    "arguments": {
                        "team_id": "team-liverpool",
                        "team_name": "Liverpool"
                    }
                }
            }

            news_response = await server.handle_request(news_request)
            assert "result" in news_response

        # Both requests should succeed independently
        assert weather_response["id"] == 10
        assert news_response["id"] == 11
