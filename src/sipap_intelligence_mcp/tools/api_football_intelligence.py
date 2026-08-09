"""API-Football Intelligence Tools for MCP server.

Provides 4 intelligence tools using API-Football data:
1. get_match_predictions - AI predictions for fixtures
2. get_sidelined_players - Player/coach availability status
3. get_player_transfers - Transfer history and news
4. get_available_timezones - Timezone data for accurate scheduling
"""

import os
from typing import Any

from sipap_common.cache import RedisCache  # type: ignore[import-untyped]

from sipap_intelligence_mcp.apis.api_football import APIFootballIntelligenceClient

# Global clients for Lambda warm start optimization (Sentinel Pattern #19)
_api_football_client: APIFootballIntelligenceClient | None = None
_cache: RedisCache | None = None


def _get_api_football_client() -> APIFootballIntelligenceClient:
    """Get or create API-Football client (cached for warm starts)."""
    global _api_football_client
    if _api_football_client is None:
        api_key = os.getenv("API_FOOTBALL_KEY", "")
        _api_football_client = APIFootballIntelligenceClient(api_key=api_key)
    return _api_football_client


def _get_cache() -> RedisCache | None:
    """Get or create Redis cache (cached for warm starts)."""
    global _cache
    if _cache is None:
        redis_endpoint = os.getenv("REDIS_ENDPOINT")
        if redis_endpoint:
            _cache = RedisCache(endpoint=redis_endpoint)
    return _cache


async def get_match_predictions(fixture_id: int) -> dict[str, Any]:
    """Get AI predictions for a match from API-Football.

    MCP Tool: Fetches API-Football's algorithm-based predictions including:
    - Match winner probabilities
    - Win/Draw/Loss percentages
    - Over/Under goals predictions
    - Goals per team predictions
    - Comparative team statistics (strength, attack, defense)
    - Advice based on poisson distribution and team analysis

    Caching Strategy:
    - Cache TTL: 6 hours (predictions update hourly for live, daily for scheduled)
    - Cache key: predictions:{fixture_id}

    Args:
        fixture_id: API-Football fixture ID

    Returns:
        Predictions data with:
            - predictions: Match winner, win_or_draw, under_over, goals, advice
            - league: League information
            - teams: Home/away team details
            - comparison: Team strength comparisons (form, att, def, h2h, goals, total)

    Example:
        >>> result = await get_match_predictions(198772)
        >>> result['predictions']['winner']['name']
        'Liverpool'
        >>> result['predictions']['percent']['home']
        '63%'
    """
    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    if cache:
        cache_key = f"predictions:{fixture_id}"
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch from API-Football
    api_client = _get_api_football_client()
    async with api_client as client:
        predictions = await client.get_predictions(fixture_id)

    # Cache result (6 hour TTL - predictions update hourly for live matches)
    if cache:
        await cache.set(cache_key, predictions, ttl=21600)

    return predictions


async def get_sidelined_players(
    player_id: int | None = None,
    coach_id: int | None = None,
) -> dict[str, Any]:
    """Get sidelined information for players or coaches.

    MCP Tool: Fetches injury/suspension data from API-Football.
    Returns detailed sidelined status including:
    - Type of absence (injury, suspension, etc.)
    - Start and end dates
    - Player/coach details

    Caching Strategy:
    - Cache TTL: 24 hours (updated several times a week)
    - Cache key: sidelined:player:{player_id} or sidelined:coach:{coach_id}

    Args:
        player_id: API-Football player ID (optional, mutually exclusive with coach_id)
        coach_id: API-Football coach ID (optional, mutually exclusive with player_id)

    Returns:
        Sidelined data with:
            - type: Type of sidelined status
            - start: Start date
            - end: End date
            - player: Player details (if player_id provided)
            - team: Team details

    Raises:
        ValueError: If neither player_id nor coach_id provided, or both provided
    """
    if not player_id and not coach_id:
        raise ValueError("Must provide either player_id or coach_id")
    if player_id and coach_id:
        raise ValueError("Cannot provide both player_id and coach_id")

    # Determine cache key and fetch type
    if player_id:
        cache_key = f"sidelined:player:{player_id}"
        fetch_id = player_id
        fetch_type = "player"
    else:
        cache_key = f"sidelined:coach:{coach_id}"
        fetch_id = coach_id  # type: ignore[assignment]
        fetch_type = "coach"

    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch from API-Football
    api_client = _get_api_football_client()
    async with api_client as client:
        if fetch_type == "player":
            sidelined_data = await client.get_sidelined_by_player(fetch_id)
        else:
            sidelined_data = await client.get_sidelined_by_coach(fetch_id)

    # Package response
    response = {
        "type": fetch_type,
        "id": fetch_id,
        "sidelined": sidelined_data
    }

    # Cache result (24 hour TTL - updated several times a week)
    if cache:
        await cache.set(cache_key, response, ttl=86400)

    return response


async def get_player_transfers(
    player_id: int | None = None,
    team_id: int | None = None,
) -> dict[str, Any]:
    """Get transfer history for a player or team.

    MCP Tool: Fetches transfer data from API-Football.
    Returns comprehensive transfer history including:
    - Transfer dates
    - Teams involved (from/to)
    - Transfer type (Free, Loan, €, N/A)
    - Player details

    Caching Strategy:
    - Cache TTL: 24 hours (updated several times a week)
    - Cache key: transfers:player:{player_id} or transfers:team:{team_id}

    Args:
        player_id: API-Football player ID (optional, mutually exclusive with team_id)
        team_id: API-Football team ID (optional, mutually exclusive with player_id)

    Returns:
        Transfer data with:
            - player: Player information
            - update: Last update timestamp
            - transfers: List of transfers with date, teams_in/out, type

    Raises:
        ValueError: If neither player_id nor team_id provided, or both provided
    """
    if not player_id and not team_id:
        raise ValueError("Must provide either player_id or team_id")
    if player_id and team_id:
        raise ValueError("Cannot provide both player_id and team_id")

    # Determine cache key and fetch type
    if player_id:
        cache_key = f"transfers:player:{player_id}"
        fetch_id = player_id
        fetch_type = "player"
    else:
        cache_key = f"transfers:team:{team_id}"
        fetch_id = team_id  # type: ignore[assignment]
        fetch_type = "team"

    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch from API-Football
    api_client = _get_api_football_client()
    async with api_client as client:
        if fetch_type == "player":
            transfers_data = await client.get_transfers_by_player(fetch_id)
        else:
            transfers_data = await client.get_transfers_by_team(fetch_id)

    # Package response
    response = {
        "type": fetch_type,
        "id": fetch_id,
        "transfers": transfers_data
    }

    # Cache result (24 hour TTL - updated several times a week)
    if cache:
        await cache.set(cache_key, response, ttl=86400)

    return response


async def get_available_timezones() -> dict[str, Any]:
    """Get list of available timezones from API-Football.

    MCP Tool: Fetches all available timezone strings.
    Critical for accurate weather data retrieval - use this to:
    1. Get the correct timezone for a fixture
    2. Convert fixture times to local time
    3. Fetch weather for the correct match time

    Caching Strategy:
    - Cache TTL: 7 days (static data, doesn't change)
    - Cache key: timezones:all

    Returns:
        Timezone data with:
            - timezones: List of timezone strings (e.g., "America/New_York", "Europe/London")
            - count: Number of available timezones

    Example:
        >>> result = await get_available_timezones()
        >>> "Europe/London" in result['timezones']
        True
        >>> result['count']
        419
    """
    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    cache_key = "timezones:all"
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch from API-Football
    api_client = _get_api_football_client()
    async with api_client as client:
        timezones = await client.get_timezones()

    # Package response
    response = {
        "timezones": timezones,
        "count": len(timezones)
    }

    # Cache result (7 day TTL - static data)
    if cache:
        await cache.set(cache_key, response, ttl=604800)

    return response
