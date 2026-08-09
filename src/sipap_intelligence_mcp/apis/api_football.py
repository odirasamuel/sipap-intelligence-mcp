"""API-Football Intelligence Client.

Provides access to API-Football intelligence endpoints for:
- Predictions (algorithm-based match predictions)
- Sidelined (injured/suspended players and coaches)
- Transfers (player transfer information)
- Timezone (timezone data for accurate scheduling)

Free tier: 100 requests/day
Documentation: https://www.api-football.com/documentation-v3
"""

from typing import Any

import httpx

from sipap_intelligence_mcp.exceptions import IntelligenceMCPException


class APIFootballIntelligenceClient:
    """
    API-Football client for intelligence data.

    Focused on 4 intelligence endpoints:
    1. Predictions - AI predictions for fixtures
    2. Sidelined - Player/coach availability
    3. Transfers - Transfer news and history
    4. Timezone - Timezone information

    API Documentation: https://www.api-football.com/documentation-v3
    """

    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str, timeout: float = 30.0):
        """
        Initialize API-Football intelligence client.

        Args:
            api_key: API-Football API key from dashboard.api-football.com
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "APIFootballIntelligenceClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with API key."""
        return {
            "x-apisports-key": self.api_key,
        }

    async def get_predictions(self, fixture_id: int) -> dict[str, Any]:
        """
        Get AI predictions for a fixture.

        Uses API-Football's algorithms including poisson distribution,
        team statistics comparison, last matches analysis, etc.

        API Endpoint: GET /predictions
        Update Frequency: Every hour (for in-progress), otherwise 1/day
        Recommended Calls: 1 per hour for live fixtures, 1 per day otherwise

        Args:
            fixture_id: API-Football fixture ID

        Returns:
            Predictions data with:
                - predictions: Match winner, win/draw, under/over, goals
                - comparison: Team strength, attack, defense comparisons
                - teams: Home/away team stats

        Raises:
            IntelligenceMCPException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/predictions"
        params: dict[str, str | int] = {"fixture": fixture_id}

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            results = data.get("response", [])
            if not results:
                raise IntelligenceMCPException(f"No predictions found for fixture {fixture_id}")

            result: dict[str, Any] = results[0]  # Return first (and only) prediction
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching predictions: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching predictions: {str(e)}") from e

    async def get_sidelined_by_player(self, player_id: int) -> list[dict[str, Any]]:
        """
        Get sidelined information for a player.

        Returns injury/suspension details for a specific player.

        API Endpoint: GET /sidelined
        Update Frequency: Several times a week
        Recommended Calls: 1 per day

        Args:
            player_id: API-Football player ID

        Returns:
            List of sidelined records with:
                - type: "Missing Fixture" or other
                - start: Start date
                - end: End date

        Raises:
            IntelligenceMCPException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/sidelined"
        params: dict[str, str | int] = {"player": player_id}

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            result: list[dict[str, Any]] = data.get("response", [])
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching sidelined data: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching sidelined data: {str(e)}") from e

    async def get_sidelined_by_coach(self, coach_id: int) -> list[dict[str, Any]]:
        """
        Get sidelined information for a coach.

        API Endpoint: GET /sidelined
        Update Frequency: Several times a week
        Recommended Calls: 1 per day

        Args:
            coach_id: API-Football coach ID

        Returns:
            List of sidelined records

        Raises:
            IntelligenceMCPException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/sidelined"
        params: dict[str, str | int] = {"coach": coach_id}

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            result: list[dict[str, Any]] = data.get("response", [])
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching sidelined data: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching sidelined data: {str(e)}") from e

    async def get_transfers_by_player(self, player_id: int) -> list[dict[str, Any]]:
        """
        Get transfer history for a player.

        API Endpoint: GET /transfers
        Update Frequency: Several times a week
        Recommended Calls: 1 per day

        Args:
            player_id: API-Football player ID

        Returns:
            List of transfer records with:
                - player: Player info
                - update: Last update timestamp
                - transfers: List of transfers (date, teams, type)

        Raises:
            IntelligenceMCPException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/transfers"
        params: dict[str, str | int] = {"player": player_id}

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            result: list[dict[str, Any]] = data.get("response", [])
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching transfers: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching transfers: {str(e)}") from e

    async def get_transfers_by_team(self, team_id: int) -> list[dict[str, Any]]:
        """
        Get transfer history for a team.

        API Endpoint: GET /transfers
        Update Frequency: Several times a week
        Recommended Calls: 1 per day

        Args:
            team_id: API-Football team ID

        Returns:
            List of transfer records for all players in the team

        Raises:
            IntelligenceMCPException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/transfers"
        params: dict[str, str | int] = {"team": team_id}

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            result: list[dict[str, Any]] = data.get("response", [])
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching transfers: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching transfers: {str(e)}") from e

    async def get_timezones(self) -> list[str]:
        """
        Get list of available timezones.

        Use this to get accurate timezone information for fixtures,
        which is critical for accurate weather data retrieval.

        API Endpoint: GET /timezone
        Update Frequency: Static (not updated)
        Recommended Calls: 1 call when needed (cache result)

        Returns:
            List of timezone strings (e.g., "America/New_York", "Europe/London")

        Raises:
            IntelligenceMCPException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/timezone"

        try:
            response = await self._client.get(url, headers=self._get_headers())
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            result: list[str] = data.get("response", [])
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching timezones: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching timezones: {str(e)}") from e
