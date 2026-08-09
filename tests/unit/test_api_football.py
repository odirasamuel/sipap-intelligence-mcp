"""Unit tests for API-Football Intelligence client.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve implementation
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from sipap_intelligence_mcp.apis.api_football import APIFootballIntelligenceClient
from sipap_intelligence_mcp.exceptions import IntelligenceMCPException


@pytest.fixture
def api_football_client():
    """Create API-Football client for testing."""
    return APIFootballIntelligenceClient(api_key="test_api_key_12345")


@pytest.fixture
def mock_predictions_response():
    """Mock API-Football predictions response."""
    return {
        "errors": [],
        "response": [
            {
                "predictions": {
                    "winner": {"id": 42, "name": "Liverpool", "comment": "Win or draw"},
                    "win_or_draw": True,
                    "under_over": "Over 2.5",
                    "goals": {"home": "2.5", "away": "1.5"},
                    "advice": "Combo bet: Liverpool to win and Over 2.5 goals",
                    "percent": {"home": "63%", "draw": "22%", "away": "15%"}
                },
                "league": {
                    "id": 39,
                    "name": "Premier League",
                    "country": "England",
                    "logo": "https://media.api-sports.io/football/leagues/39.png",
                    "flag": "https://media.api-sports.io/flags/gb.svg",
                    "season": 2024
                },
                "teams": {
                    "home": {"id": 42, "name": "Liverpool", "logo": "https://media.api-sports.io/football/teams/42.png"},
                    "away": {"id": 33, "name": "Manchester United", "logo": "https://media.api-sports.io/football/teams/33.png"}
                },
                "comparison": {
                    "form": {"home": "85%", "away": "60%"},
                    "att": {"home": "90%", "away": "70%"},
                    "def": {"home": "80%", "away": "65%"},
                    "poisson_distribution": {"home": "58%", "away": "18%"},
                    "h2h": {"home": "55%", "away": "45%"},
                    "goals": {"home": "2.5", "away": "1.5"},
                    "total": {"home": "78%", "away": "48%"}
                }
            }
        ]
    }


@pytest.fixture
def mock_sidelined_response():
    """Mock API-Football sidelined response."""
    return {
        "errors": [],
        "response": [
            {
                "type": "Missing Fixture",
                "start": "2024-07-01",
                "end": "2024-07-15",
                "player": {
                    "id": 306,
                    "name": "M. Salah"
                },
                "team": {
                    "id": 42,
                    "name": "Liverpool"
                }
            }
        ]
    }


@pytest.fixture
def mock_transfers_response():
    """Mock API-Football transfers response."""
    return {
        "errors": [],
        "response": [
            {
                "player": {
                    "id": 306,
                    "name": "M. Salah"
                },
                "update": "2024-07-12T10:30:00+00:00",
                "transfers": [
                    {
                        "date": "2017-07-01",
                        "type": "€",
                        "teams": {
                            "in": {"id": 42, "name": "Liverpool", "logo": "https://media.api-sports.io/football/teams/42.png"},
                            "out": {"id": 518, "name": "Roma", "logo": "https://media.api-sports.io/football/teams/518.png"}
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_timezones_response():
    """Mock API-Football timezones response."""
    return {
        "errors": [],
        "response": [
            "Africa/Abidjan",
            "Africa/Accra",
            "Africa/Algiers",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Paris",
            "Asia/Tokyo"
        ]
    }


class TestAPIFootballIntelligenceClient:
    """Test API-Football Intelligence client."""

    def test_client_initialization(self, api_football_client):
        """Test client initializes with API key."""
        assert api_football_client.api_key == "test_api_key_12345"
        assert api_football_client.BASE_URL == "https://v3.football.api-sports.io"
        assert api_football_client.timeout == 30.0

    def test_client_custom_timeout(self):
        """Test client accepts custom timeout."""
        client = APIFootballIntelligenceClient(api_key="test_key", timeout=60.0)
        assert client.timeout == 60.0

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self, api_football_client):
        """Test async context manager creates httpx client."""
        async with api_football_client as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_get_predictions_success(
        self, api_football_client, mock_predictions_response
    ):
        """Test fetching predictions succeeds."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = mock_predictions_response
            mock_get.return_value = mock_response

            async with api_football_client as client:
                result = await client.get_predictions(fixture_id=198772)

            assert result["predictions"]["winner"]["name"] == "Liverpool"
            assert result["predictions"]["percent"]["home"] == "63%"
            assert result["league"]["name"] == "Premier League"
            assert result["teams"]["home"]["name"] == "Liverpool"
            assert result["comparison"]["total"]["home"] == "78%"

    @pytest.mark.asyncio
    async def test_get_predictions_no_results(self, api_football_client):
        """Test predictions with no results raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {"errors": [], "response": []}
            mock_get.return_value = mock_response

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="No predictions found for fixture 198772"
                ):
                    await client.get_predictions(fixture_id=198772)

    @pytest.mark.asyncio
    async def test_get_predictions_api_error(self, api_football_client):
        """Test predictions with API error raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "errors": {"requests": "Too many requests"},
                "response": []
            }
            mock_get.return_value = mock_response

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="API-Football error"
                ):
                    await client.get_predictions(fixture_id=198772)

    @pytest.mark.asyncio
    async def test_get_predictions_http_error(self, api_football_client):
        """Test predictions HTTP error raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection timeout")

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="Error fetching predictions"
                ):
                    await client.get_predictions(fixture_id=198772)

    @pytest.mark.asyncio
    async def test_get_predictions_without_context_manager(self, api_football_client):
        """Test using client without context manager raises error."""
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await api_football_client.get_predictions(fixture_id=198772)

    @pytest.mark.asyncio
    async def test_get_sidelined_by_player_success(
        self, api_football_client, mock_sidelined_response
    ):
        """Test fetching sidelined players succeeds."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = mock_sidelined_response
            mock_get.return_value = mock_response

            async with api_football_client as client:
                result = await client.get_sidelined_by_player(player_id=306)

            assert len(result) == 1
            assert result[0]["type"] == "Missing Fixture"
            assert result[0]["player"]["name"] == "M. Salah"
            assert result[0]["start"] == "2024-07-01"

    @pytest.mark.asyncio
    async def test_get_sidelined_by_coach_success(self, api_football_client):
        """Test fetching sidelined coaches succeeds."""
        mock_coach_response = {
            "errors": [],
            "response": [
                {
                    "type": "Suspended",
                    "start": "2024-07-01",
                    "end": "2024-07-08",
                    "coach": {"id": 1, "name": "J. Klopp"}
                }
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = mock_coach_response
            mock_get.return_value = mock_response

            async with api_football_client as client:
                result = await client.get_sidelined_by_coach(coach_id=1)

            assert len(result) == 1
            assert result[0]["type"] == "Suspended"

    @pytest.mark.asyncio
    async def test_get_sidelined_api_error(self, api_football_client):
        """Test sidelined with API error raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "errors": {"player": "Player not found"},
                "response": []
            }
            mock_get.return_value = mock_response

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="API-Football error"
                ):
                    await client.get_sidelined_by_player(player_id=999999)

    @pytest.mark.asyncio
    async def test_get_transfers_by_player_success(
        self, api_football_client, mock_transfers_response
    ):
        """Test fetching player transfers succeeds."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = mock_transfers_response
            mock_get.return_value = mock_response

            async with api_football_client as client:
                result = await client.get_transfers_by_player(player_id=306)

            assert len(result) == 1
            assert result[0]["player"]["name"] == "M. Salah"
            assert len(result[0]["transfers"]) == 1
            assert result[0]["transfers"][0]["teams"]["in"]["name"] == "Liverpool"

    @pytest.mark.asyncio
    async def test_get_transfers_by_team_success(self, api_football_client):
        """Test fetching team transfers succeeds."""
        mock_team_transfers = {
            "errors": [],
            "response": [
                {
                    "player": {"id": 306, "name": "M. Salah"},
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
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = mock_team_transfers
            mock_get.return_value = mock_response

            async with api_football_client as client:
                result = await client.get_transfers_by_team(team_id=42)

            assert len(result) == 1
            assert result[0]["player"]["name"] == "M. Salah"

    @pytest.mark.asyncio
    async def test_get_transfers_http_error(self, api_football_client):
        """Test transfers HTTP error raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="Error fetching transfers"
                ):
                    await client.get_transfers_by_player(player_id=306)

    @pytest.mark.asyncio
    async def test_get_timezones_success(
        self, api_football_client, mock_timezones_response
    ):
        """Test fetching timezones succeeds."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = mock_timezones_response
            mock_get.return_value = mock_response

            async with api_football_client as client:
                result = await client.get_timezones()

            assert len(result) == 8
            assert "Europe/London" in result
            assert "America/New_York" in result
            assert "Asia/Tokyo" in result

    @pytest.mark.asyncio
    async def test_get_timezones_api_error(self, api_football_client):
        """Test timezones with API error raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "errors": {"endpoint": "Not available"},
                "response": []
            }
            mock_get.return_value = mock_response

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="API-Football error"
                ):
                    await client.get_timezones()

    @pytest.mark.asyncio
    async def test_get_timezones_http_error(self, api_football_client):
        """Test timezones HTTP error raises exception."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Request failed")

            async with api_football_client as client:
                with pytest.raises(
                    IntelligenceMCPException,
                    match="Error fetching timezones"
                ):
                    await client.get_timezones()

    def test_get_headers_includes_api_key(self, api_football_client):
        """Test headers include x-apisports-key."""
        headers = api_football_client._get_headers()
        assert "x-apisports-key" in headers
        assert headers["x-apisports-key"] == "test_api_key_12345"
