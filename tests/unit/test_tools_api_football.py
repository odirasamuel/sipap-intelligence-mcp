"""Unit tests for API-Football intelligence tools.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve implementation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sipap_intelligence_mcp.tools import api_football_intelligence


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_predictions_data():
    """Mock predictions data from API-Football."""
    return {
        "predictions": {
            "winner": {"id": 42, "name": "Liverpool", "comment": "Win or draw"},
            "win_or_draw": True,
            "under_over": "Over 2.5",
            "goals": {"home": "2.5", "away": "1.5"},
            "advice": "Combo bet: Liverpool to win and Over 2.5 goals",
            "percent": {"home": "63%", "draw": "22%", "away": "15%"}
        },
        "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2024},
        "teams": {
            "home": {"id": 42, "name": "Liverpool"},
            "away": {"id": 33, "name": "Manchester United"}
        },
        "comparison": {
            "form": {"home": "85%", "away": "60%"},
            "att": {"home": "90%", "away": "70%"},
            "def": {"home": "80%", "away": "65%"},
            "total": {"home": "78%", "away": "48%"}
        }
    }


@pytest.fixture
def mock_sidelined_data():
    """Mock sidelined data from API-Football."""
    return [
        {
            "type": "Missing Fixture",
            "start": "2024-07-01",
            "end": "2024-07-15",
            "player": {"id": 306, "name": "M. Salah"},
            "team": {"id": 42, "name": "Liverpool"}
        }
    ]


@pytest.fixture
def mock_transfers_data():
    """Mock transfers data from API-Football."""
    return [
        {
            "player": {"id": 306, "name": "M. Salah"},
            "update": "2024-07-12T10:30:00+00:00",
            "transfers": [
                {
                    "date": "2017-07-01",
                    "type": "€",
                    "teams": {
                        "in": {"id": 42, "name": "Liverpool"},
                        "out": {"id": 518, "name": "Roma"}
                    }
                }
            ]
        }
    ]


@pytest.fixture
def mock_timezones_data():
    """Mock timezones data from API-Football."""
    return [
        "Africa/Abidjan",
        "America/New_York",
        "Europe/London",
        "Asia/Tokyo"
    ]


class TestGetMatchPredictions:
    """Test get_match_predictions tool."""

    @pytest.mark.asyncio
    async def test_get_match_predictions_success(self, mock_predictions_data):
        """Test fetching match predictions succeeds."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_predictions = AsyncMock(return_value=mock_predictions_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_match_predictions(fixture_id=198772)

            assert result["predictions"]["winner"]["name"] == "Liverpool"
            assert result["predictions"]["percent"]["home"] == "63%"
            assert result["league"]["name"] == "Premier League"
            assert result["teams"]["home"]["name"] == "Liverpool"

    @pytest.mark.asyncio
    async def test_get_match_predictions_with_cache_hit(
        self, mock_predictions_data, mock_redis_cache
    ):
        """Test predictions returns cached data if available."""
        mock_redis_cache.get = AsyncMock(return_value=mock_predictions_data)

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache:
            mock_get_cache.return_value = mock_redis_cache

            result = await api_football_intelligence.get_match_predictions(fixture_id=198772)

            # Should return cached data without calling API
            assert result == mock_predictions_data
            mock_redis_cache.get.assert_called_once_with("predictions:198772")

    @pytest.mark.asyncio
    async def test_get_match_predictions_caches_result(
        self, mock_predictions_data, mock_redis_cache
    ):
        """Test predictions caches API result."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_predictions = AsyncMock(return_value=mock_predictions_data)
            mock_get_client.return_value = mock_client

            await api_football_intelligence.get_match_predictions(fixture_id=198772)

            # Should cache result with 6 hour TTL
            mock_redis_cache.set.assert_called_once_with(
                "predictions:198772", mock_predictions_data, ttl=21600
            )

    @pytest.mark.asyncio
    async def test_get_match_predictions_without_cache(self, mock_predictions_data):
        """Test predictions works without Redis cache."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_get_cache.return_value = None  # No cache available

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_predictions = AsyncMock(return_value=mock_predictions_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_match_predictions(fixture_id=198772)

            assert result == mock_predictions_data


class TestGetSidelinedPlayers:
    """Test get_sidelined_players tool."""

    @pytest.mark.asyncio
    async def test_get_sidelined_by_player_success(self, mock_sidelined_data):
        """Test fetching sidelined players succeeds."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_sidelined_by_player = AsyncMock(return_value=mock_sidelined_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_sidelined_players(player_id=306)

            assert result["type"] == "player"
            assert result["id"] == 306
            assert result["sidelined"] == mock_sidelined_data

    @pytest.mark.asyncio
    async def test_get_sidelined_by_coach_success(self):
        """Test fetching sidelined coaches succeeds."""
        mock_coach_data = [
            {
                "type": "Suspended",
                "start": "2024-07-01",
                "end": "2024-07-08",
                "coach": {"id": 1, "name": "J. Klopp"}
            }
        ]

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_sidelined_by_coach = AsyncMock(return_value=mock_coach_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_sidelined_players(coach_id=1)

            assert result["type"] == "coach"
            assert result["id"] == 1
            assert result["sidelined"] == mock_coach_data

    @pytest.mark.asyncio
    async def test_get_sidelined_validation_no_ids(self):
        """Test sidelined raises error when no IDs provided."""
        with pytest.raises(ValueError, match="Must provide either player_id or coach_id"):
            await api_football_intelligence.get_sidelined_players()

    @pytest.mark.asyncio
    async def test_get_sidelined_validation_both_ids(self):
        """Test sidelined raises error when both IDs provided."""
        with pytest.raises(ValueError, match="Cannot provide both player_id and coach_id"):
            await api_football_intelligence.get_sidelined_players(player_id=306, coach_id=1)

    @pytest.mark.asyncio
    async def test_get_sidelined_caches_result(self, mock_sidelined_data, mock_redis_cache):
        """Test sidelined caches API result."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_sidelined_by_player = AsyncMock(return_value=mock_sidelined_data)
            mock_get_client.return_value = mock_client

            await api_football_intelligence.get_sidelined_players(player_id=306)

            # Should cache result with 24 hour TTL
            expected_response = {
                "type": "player",
                "id": 306,
                "sidelined": mock_sidelined_data
            }
            mock_redis_cache.set.assert_called_once_with(
                "sidelined:player:306", expected_response, ttl=86400
            )


class TestGetPlayerTransfers:
    """Test get_player_transfers tool."""

    @pytest.mark.asyncio
    async def test_get_transfers_by_player_success(self, mock_transfers_data):
        """Test fetching player transfers succeeds."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_transfers_by_player = AsyncMock(return_value=mock_transfers_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_player_transfers(player_id=306)

            assert result["type"] == "player"
            assert result["id"] == 306
            assert result["transfers"] == mock_transfers_data

    @pytest.mark.asyncio
    async def test_get_transfers_by_team_success(self):
        """Test fetching team transfers succeeds."""
        mock_team_transfers = [
            {
                "player": {"id": 306, "name": "M. Salah"},
                "transfers": [
                    {
                        "date": "2017-07-01",
                        "type": "€",
                        "teams": {"in": {"id": 42, "name": "Liverpool"}}
                    }
                ]
            }
        ]

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_transfers_by_team = AsyncMock(return_value=mock_team_transfers)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_player_transfers(team_id=42)

            assert result["type"] == "team"
            assert result["id"] == 42
            assert result["transfers"] == mock_team_transfers

    @pytest.mark.asyncio
    async def test_get_transfers_validation_no_ids(self):
        """Test transfers raises error when no IDs provided."""
        with pytest.raises(ValueError, match="Must provide either player_id or team_id"):
            await api_football_intelligence.get_player_transfers()

    @pytest.mark.asyncio
    async def test_get_transfers_validation_both_ids(self):
        """Test transfers raises error when both IDs provided."""
        with pytest.raises(ValueError, match="Cannot provide both player_id and team_id"):
            await api_football_intelligence.get_player_transfers(player_id=306, team_id=42)

    @pytest.mark.asyncio
    async def test_get_transfers_caches_result(self, mock_transfers_data, mock_redis_cache):
        """Test transfers caches API result."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_transfers_by_player = AsyncMock(return_value=mock_transfers_data)
            mock_get_client.return_value = mock_client

            await api_football_intelligence.get_player_transfers(player_id=306)

            # Should cache result with 24 hour TTL
            expected_response = {
                "type": "player",
                "id": 306,
                "transfers": mock_transfers_data
            }
            mock_redis_cache.set.assert_called_once_with(
                "transfers:player:306", expected_response, ttl=86400
            )


class TestGetAvailableTimezones:
    """Test get_available_timezones tool."""

    @pytest.mark.asyncio
    async def test_get_timezones_success(self, mock_timezones_data):
        """Test fetching timezones succeeds."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_timezones = AsyncMock(return_value=mock_timezones_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_available_timezones()

            assert result["timezones"] == mock_timezones_data
            assert result["count"] == 4

    @pytest.mark.asyncio
    async def test_get_timezones_with_cache_hit(
        self, mock_timezones_data, mock_redis_cache
    ):
        """Test timezones returns cached data if available."""
        cached_response = {
            "timezones": mock_timezones_data,
            "count": 4
        }
        mock_redis_cache.get = AsyncMock(return_value=cached_response)

        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache:
            mock_get_cache.return_value = mock_redis_cache

            result = await api_football_intelligence.get_available_timezones()

            # Should return cached data without calling API
            assert result == cached_response
            mock_redis_cache.get.assert_called_once_with("timezones:all")

    @pytest.mark.asyncio
    async def test_get_timezones_caches_result(
        self, mock_timezones_data, mock_redis_cache
    ):
        """Test timezones caches API result."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_timezones = AsyncMock(return_value=mock_timezones_data)
            mock_get_client.return_value = mock_client

            await api_football_intelligence.get_available_timezones()

            # Should cache result with 7 day TTL
            expected_response = {
                "timezones": mock_timezones_data,
                "count": 4
            }
            mock_redis_cache.set.assert_called_once_with(
                "timezones:all", expected_response, ttl=604800
            )

    @pytest.mark.asyncio
    async def test_get_timezones_without_cache(self, mock_timezones_data):
        """Test timezones works without Redis cache."""
        with patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.api_football_intelligence._get_api_football_client"
        ) as mock_get_client:
            mock_get_cache.return_value = None  # No cache available

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.get_timezones = AsyncMock(return_value=mock_timezones_data)
            mock_get_client.return_value = mock_client

            result = await api_football_intelligence.get_available_timezones()

            assert result["timezones"] == mock_timezones_data
            assert result["count"] == 4
