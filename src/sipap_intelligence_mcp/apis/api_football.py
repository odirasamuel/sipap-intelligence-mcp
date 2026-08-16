"""API-Football Intelligence Client.

Provides access to API-Football intelligence endpoints for:
- Predictions (algorithm-based match predictions)
- Sidelined (injured/suspended players and coaches)
- Transfers (player transfer information)
- Timezone (timezone data for accurate scheduling)
- Fixtures (live and completed match results with scores)

Free tier: 100 requests/day
Documentation: https://www.api-football.com/documentation-v3
"""

import asyncio
import logging
from typing import Any

import httpx

from sipap_intelligence_mcp.exceptions import IntelligenceMCPException

logger = logging.getLogger(__name__)


class APIFootballIntelligenceClient:
    """
    API-Football client for intelligence data.

    Focused on 5 intelligence endpoints:
    1. Predictions - AI predictions for fixtures
    2. Sidelined - Player/coach availability
    3. Transfers - Transfer news and history
    4. Timezone - Timezone information
    5. Fixtures - Live and completed match results (real-time scores)

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

    async def _request_with_retry(
        self,
        url: str,
        params: dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> dict[str, Any]:
        """
        Make API request with rate limit handling and exponential backoff.

        Args:
            url: API endpoint URL
            params: Query parameters
            max_retries: Maximum number of retries on rate limit
            base_delay: Base delay in seconds for backoff

        Returns:
            JSON response data

        Raises:
            IntelligenceMCPException: If request fails after retries
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = await self._client.get(
                    url, headers=self._get_headers(), params=params
                )
                response.raise_for_status()
                data = response.json()

                # Check for API-level errors
                errors = data.get("errors", {})
                if errors:
                    # Check for rate limit error
                    if "rateLimit" in errors:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(
                                f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise IntelligenceMCPException(f"Rate limit exceeded after {max_retries} retries")
                    raise IntelligenceMCPException(f"API-Football error: {errors}")

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"HTTP 429 rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                last_error = e
            except httpx.HTTPError as e:
                last_error = e
                break

        raise IntelligenceMCPException(f"Request failed: {last_error}")

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

    async def get_fixtures(
        self,
        date: str | None = None,
        league_id: int | None = None,
        season: int | None = None,
        team_id: int | None = None,
        status: str | None = None,
        last: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get fixtures with live scores and results.

        Returns real-time match data including scores for live and completed fixtures.
        This is the primary method for fetching actual match results, not predictions.

        API Endpoint: GET /fixtures
        Update Frequency: Real-time (live matches), immediate after FT
        Recommended Calls: As needed for user requests

        Status values:
            - "LIVE" - All live match statuses (1H, HT, 2H, ET, BT, P, SUSP, INT)
            - "FT" - Finished after 90 minutes
            - "AET" - Finished after extra time
            - "PEN" - Finished after penalty shootout
            - "NS" - Not started (scheduled)
            - "CANC" - Cancelled
            - "PST" - Postponed
            - "ABD" - Abandoned

        Args:
            date: Date in YYYY-MM-DD format (returns all fixtures on this date)
            league_id: API-Football league ID (filter by competition)
            season: Season year (e.g., 2026)
            team_id: API-Football team ID (filter by team)
            status: Match status filter (e.g., "FT", "LIVE")
            last: Get last N fixtures (for a team/league)

        Returns:
            List of fixtures with:
                - fixture: Match info (id, date, status, venue)
                - league: Competition info
                - teams: Home/away team info
                - goals: Scores (home, away)
                - score: Detailed scores (halftime, fulltime, extratime, penalty)

        Raises:
            IntelligenceMCPException: If API request fails

        Examples:
            >>> # Get all live matches
            >>> fixtures = await client.get_fixtures(status="LIVE")

            >>> # Get finished matches for today
            >>> from datetime import datetime, UTC
            >>> today = datetime.now(UTC).date().isoformat()
            >>> fixtures = await client.get_fixtures(date=today, status="FT")

            >>> # Get last 10 matches for a team
            >>> fixtures = await client.get_fixtures(team_id=33, last=10)

            >>> # Get all fixtures for a league on a specific date
            >>> fixtures = await client.get_fixtures(
            ...     date="2026-08-09",
            ...     league_id=39,  # Premier League
            ...     season=2026
            ... )
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/fixtures"
        params: dict[str, str | int] = {}

        # Build query parameters (only include provided filters)
        if date is not None:
            params["date"] = date
        if league_id is not None:
            params["league"] = league_id
        if season is not None:
            params["season"] = season
        if team_id is not None:
            params["team"] = team_id
        if status is not None:
            params["status"] = status
        if last is not None:
            params["last"] = last

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            result: list[dict[str, Any]] = data.get("response", [])
            return result

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching fixtures: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching fixtures: {str(e)}") from e

    async def get_odds(
        self,
        fixture_id: int | None = None,
        league_id: int | None = None,
        season: int | None = None,
        date: str | None = None,
        bookmaker_id: int | None = None,
        bet_id: int = 1,  # 1 = Match Winner (1X2)
    ) -> list[dict[str, Any]]:
        """
        Get betting odds for fixtures.

        Returns odds from various bookmakers for specified fixtures.
        Default bet type is Match Winner (1X2) - Home/Draw/Away.

        API Endpoint: GET /odds
        Update Frequency: Several times a day (on match days more frequently)
        Recommended Calls: 1 per request

        Bet IDs (common):
            - 1: Match Winner (1X2) - Home/Draw/Away
            - 2: Home/Away (no draw)
            - 3: Second Half Winner
            - 5: Goals Over/Under
            - 6: Goals Over/Under First Half

        Args:
            fixture_id: Specific fixture ID to get odds for
            league_id: League ID (requires season)
            season: Season year (required with league_id)
            date: Date in YYYY-MM-DD format
            bookmaker_id: Specific bookmaker ID (optional)
            bet_id: Type of bet (default: 1 = Match Winner)

        Returns:
            List of odds records with:
                - fixture: Fixture info
                - bookmakers: List of bookmaker odds
                  - Each bookmaker contains bets with values (odd value)

        Raises:
            IntelligenceMCPException: If API request fails

        Examples:
            >>> # Get odds for a specific fixture
            >>> odds = await client.get_odds(fixture_id=12345)

            >>> # Get odds for all fixtures on a date
            >>> odds = await client.get_odds(date="2026-08-15")

            >>> # Get odds for a league
            >>> odds = await client.get_odds(league_id=39, season=2026)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/odds"
        params: dict[str, str | int] = {"bet": bet_id}

        # Build query parameters (at least one filter required)
        if fixture_id is not None:
            params["fixture"] = fixture_id
        if league_id is not None:
            params["league"] = league_id
        if season is not None:
            params["season"] = season
        if date is not None:
            params["date"] = date
        if bookmaker_id is not None:
            params["bookmaker"] = bookmaker_id

        try:
            # Handle pagination - API returns 10 results per page
            all_results: list[dict[str, Any]] = []
            page = 1
            max_pages = 20  # Safety limit to prevent infinite loops

            while page <= max_pages:
                params["page"] = page
                response = await self._client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("errors") and len(data["errors"]) > 0:
                    raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

                page_results = data.get("response", [])
                all_results.extend(page_results)

                # Check if there are more pages
                paging = data.get("paging", {})
                current_page = paging.get("current", page)
                total_pages = paging.get("total", 1)

                if current_page >= total_pages:
                    break  # No more pages

                page += 1

            return all_results

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching odds: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching odds: {str(e)}") from e

    async def get_odds_mapping(
        self,
        page: int = 1,
    ) -> dict[str, Any]:
        """
        Get mapping of fixture IDs that have odds available.

        Use this endpoint to discover which fixtures have odds data before
        making individual odds requests. Returns fixture IDs with pagination.

        API Endpoint: GET /odds/mapping
        Update Frequency: Continuous (as odds become available)

        Args:
            page: Page number for pagination (default: 1)

        Returns:
            Dictionary with:
                - fixture_ids: List of fixture IDs with available odds
                - paging: Pagination info (current, total)

        Example:
            >>> mapping = await client.get_odds_mapping()
            >>> 12345 in mapping['fixture_ids']
            True
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/odds/mapping"
        params: dict[str, int] = {"page": page}

        try:
            response = await self._client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors") and len(data["errors"]) > 0:
                raise IntelligenceMCPException(f"API-Football error: {data['errors']}")

            # Extract fixture IDs from response
            fixture_ids = [
                item.get("fixture")
                for item in data.get("response", [])
                if item.get("fixture")
            ]

            return {
                "fixture_ids": fixture_ids,
                "paging": data.get("paging", {}),
            }

        except httpx.HTTPError as e:
            raise IntelligenceMCPException(f"HTTP error fetching odds mapping: {str(e)}") from e
        except Exception as e:
            raise IntelligenceMCPException(f"Error fetching odds mapping: {str(e)}") from e

    async def get_odds_for_fixtures(
        self,
        fixture_ids: list[int],
        bet_id: int = 1,
        batch_size: int = 5,
        delay_between_batches: float = 0.5,
    ) -> dict[int, dict[str, Any]]:
        """
        Get odds for multiple fixtures efficiently with rate limiting.

        Fetches odds for specific fixture IDs in batches to avoid rate limiting.
        Much more efficient than fetching all odds for a date and filtering.

        Args:
            fixture_ids: List of fixture IDs to get odds for
            bet_id: Type of bet (default: 1 = Match Winner)
            batch_size: Number of fixtures per batch (default: 5)
            delay_between_batches: Delay in seconds between batches

        Returns:
            Dictionary mapping fixture_id -> odds data
            {
                12345: {"home": 1.5, "draw": 3.5, "away": 6.0, "bookmaker": "Bet365"},
                12346: {"home": 2.0, "draw": 3.2, "away": 3.5, "bookmaker": "Unibet"},
            }
        """
        if not self._client:
            raise RuntimeError("Client not initialized")

        if not fixture_ids:
            return {}

        url = f"{self.BASE_URL}/odds"
        results: dict[int, dict[str, Any]] = {}

        # Process in batches to avoid rate limiting
        for i in range(0, len(fixture_ids), batch_size):
            batch = fixture_ids[i:i + batch_size]

            # Add delay between batches (except for first batch)
            if i > 0:
                await asyncio.sleep(delay_between_batches)

            # Fetch odds for each fixture in batch concurrently
            for fixture_id in batch:
                try:
                    params: dict[str, Any] = {"fixture": fixture_id, "bet": bet_id}
                    data = await self._request_with_retry(url, params, max_retries=2, base_delay=0.5)

                    response_data = data.get("response", [])
                    if response_data:
                        # Extract best odds from first bookmaker
                        odds_info = self._extract_best_odds_from_response(response_data[0])
                        if odds_info:
                            results[fixture_id] = odds_info

                except IntelligenceMCPException as e:
                    logger.warning(f"Failed to fetch odds for fixture {fixture_id}: {e}")
                    continue

        logger.info(f"Fetched odds for {len(results)}/{len(fixture_ids)} fixtures")
        return results

    def _extract_best_odds_from_response(self, odds_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Extract best odds from an odds response.

        Args:
            odds_data: Single odds response from API

        Returns:
            Dictionary with home/draw/away odds and bookmaker name, or None
        """
        bookmakers = odds_data.get("bookmakers", [])
        if not bookmakers:
            return None

        # Use first bookmaker (usually most reliable)
        bookmaker = bookmakers[0]
        bookmaker_name = bookmaker.get("name", "Unknown")
        bets = bookmaker.get("bets", [])

        # Find Match Winner (1X2) bet
        for bet in bets:
            if bet.get("id") == 1 or bet.get("name") == "Match Winner":
                values = bet.get("values", [])
                odds = {"bookmaker": bookmaker_name}
                for v in values:
                    value_name = v.get("value", "").lower()
                    odd = v.get("odd")
                    if odd:
                        try:
                            odd_float = float(odd)
                            if value_name == "home":
                                odds["home"] = odd_float
                            elif value_name == "draw":
                                odds["draw"] = odd_float
                            elif value_name == "away":
                                odds["away"] = odd_float
                        except (ValueError, TypeError):
                            continue

                if "home" in odds and "draw" in odds and "away" in odds:
                    return odds

        return None

    async def get_all_odds_mapping(self, max_pages: int = 50) -> set[int]:
        """
        Get all fixture IDs that have odds available.

        Fetches all pages of the odds mapping endpoint to build a complete
        set of fixture IDs with available odds.

        Args:
            max_pages: Maximum pages to fetch (safety limit)

        Returns:
            Set of fixture IDs that have odds available
        """
        all_fixture_ids: set[int] = set()
        page = 1

        while page <= max_pages:
            try:
                result = await self.get_odds_mapping(page=page)
                fixture_ids = result.get("fixture_ids", [])

                if not fixture_ids:
                    break

                all_fixture_ids.update(fixture_ids)

                # Check pagination
                paging = result.get("paging", {})
                current = paging.get("current", page)
                total = paging.get("total", 1)

                if current >= total:
                    break

                page += 1

                # Small delay between pages
                await asyncio.sleep(0.1)

            except IntelligenceMCPException as e:
                logger.warning(f"Failed to fetch odds mapping page {page}: {e}")
                break

        logger.info(f"Found {len(all_fixture_ids)} fixtures with odds available")
        return all_fixture_ids
