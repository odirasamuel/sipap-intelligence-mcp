"""API-Football Intelligence Tools for MCP server.

Provides 5 intelligence tools using API-Football data:
1. get_match_predictions - AI predictions for fixtures
2. get_sidelined_players - Player/coach availability status
3. get_player_transfers - Transfer history and news
4. get_available_timezones - Timezone data for accurate scheduling
5. get_match_results - Live and completed match results with scores (REAL-TIME)
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
        redis_host = os.getenv("REDIS_HOST")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        if redis_host:
            try:
                _cache = RedisCache(host=redis_host, port=redis_port, db=0)
            except Exception:
                # If Redis initialization fails, gracefully degrade (no caching)
                _cache = None
    return _cache


def _resolve_league_to_id(league_name: str, user_query: str | None = None) -> tuple[int | None, str | None, str | None]:
    """Resolve user-provided league name to API-Football ID using ID-first architecture.

    Uses sipap-common's league_reference.py for unambiguous resolution via API-Football IDs.
    This eliminates string matching ambiguity (e.g., "Premier League" exists in multiple countries).

    ID-FIRST ARCHITECTURE:
    - Returns API-Football league ID (e.g., 140 for La Liga, 39 for Premier League England)
    - ID is used directly in API calls: `get_fixtures(league_id=140)`
    - No more client-side string filtering needed

    Args:
        league_name: User-provided league name (e.g., "Armenia Premier League", "Austria league")
        user_query: FULL user query for context-aware matching (RECOMMENDED)

    Returns:
        Tuple of (league_id, canonical_name, country) or (None, None, None) if not found
        - league_id: API-Football competition ID (e.g., 140)
        - canonical_name: Official league name (e.g., "La Liga")
        - country: Country name or None for international tournaments

    Examples:
        >>> _resolve_league_to_id("Belarus league", "Belarus league results yesterday")
        (117, "Premier League", "Belarus")  # Belarus Premier League ID
        >>> _resolve_league_to_id("Spanish LaLiga", "Spanish LaLiga fixtures today")
        (140, "La Liga", "Spain")  # La Liga ID
        >>> _resolve_league_to_id("EPL")
        (39, "Premier League", "England")  # Premier League England ID
        >>> _resolve_league_to_id("Champions League")
        (2, "UEFA Champions League", None)  # International tournament
    """
    from sipap_common.data.league_reference import resolve_league_query

    import logging
    logger = logging.getLogger(__name__)

    # Use full user query for better context if provided
    query_to_resolve = user_query if user_query else league_name

    # ID-FIRST: Resolve to API-Football IDs
    resolved = resolve_league_query(query_to_resolve)

    if not resolved:
        # Fallback: Try resolving just the league_name
        resolved = resolve_league_query(league_name)

    if not resolved:
        logger.info(f"No league match found for '{league_name}' (query='{user_query}')")
        return (None, None, None)

    # Take the first match (highest priority)
    league = resolved[0]
    league_id = league["id"]
    canonical_name = league["name"]
    country = league.get("country")

    # International tournaments have country="World" - set to None for API filtering
    if country == "World":
        country = None

    logger.info(
        f"ID-first resolution: '{league_name}' → ID {league_id} ({canonical_name}, {country})",
        extra={"league_name": league_name, "league_id": league_id, "canonical": canonical_name, "country": country}
    )

    return (league_id, canonical_name, country)


# Legacy wrapper for backwards compatibility
def _get_canonical_league_name(league_name: str, user_query: str | None = None) -> tuple[str | None, str | None]:
    """DEPRECATED: Use _resolve_league_to_id() for ID-first architecture.

    This wrapper exists for backwards compatibility but internally uses ID-first resolution.
    """
    _, canonical_name, country = _resolve_league_to_id(league_name, user_query)
    return (canonical_name, country)


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


async def get_match_results(
    date: str | None = None,
    league_name: str | None = None,
    team_name: str | None = None,
    status: str = "FT",
    user_query: str | None = None,
) -> dict[str, Any]:
    """Get live or completed match results from API-Football (REAL-TIME DATA).

    MCP Tool: Fetches actual match scores and status directly from API-Football.
    This provides LIVE, REAL-TIME data, not cached database data.

    Use this tool when user asks for:
    - "What are the results for...?"
    - "What's the score of...?"
    - "How did [team] do...?"
    - "Show me live matches"
    - "What's happening in [competition]?"

    Status values:
        - "FT" - Finished matches (90 minutes, default)
        - "LIVE" - All live matches (1H, HT, 2H, ET, etc.)
        - "AET" - Finished after extra time
        - "PEN" - Finished after penalty shootout
        - "ALL" - All statuses (FT + LIVE + AET + PEN)

    Args:
        date: Date in YYYY-MM-DD format (default: today)
        league_name: League/competition name (DEPRECATED - use user_query instead)
        team_name: Team name filter
        status: Match status filter
        user_query: FULL user query for intelligent league matching (RECOMMENDED)

    Caching Strategy:
    - Cache TTL: 2 minutes for LIVE (fast-changing)
    - Cache TTL: 1 hour for FT (static after full-time)
    - Cache key: match_results:{date}:{status}:{league_name}:{team_name}

    Args:
        date: Date in YYYY-MM-DD format (default: today)
        league_name: League/competition name (e.g., "Premier League", "Armenia Premier League")
        team_name: Team name filter (e.g., "Arsenal", "Liverpool")
        status: Match status - "FT" (finished), "LIVE" (live), "ALL" (both)

    Returns:
        Match results with:
            - matches: List of fixtures with scores
            - count: Number of matches found
            - status_filter: Applied status filter
            - Each match contains:
                - fixture: Match info (id, date, status, venue, referee)
                - league: Competition info (id, name, country, season)
                - teams: Home/away team info (id, name, logo)
                - goals: Scores (home, away)
                - score: Detailed scores (halftime, fulltime, extratime, penalty)

    Examples:
        >>> # Get all finished matches today
        >>> result = await get_match_results()
        >>> result['count']
        45

        >>> # Get live matches
        >>> result = await get_match_results(status="LIVE")

        >>> # Get results for Armenia Premier League
        >>> result = await get_match_results(league_name="Armenia Premier League")

        >>> # Get Arsenal's recent results
        >>> result = await get_match_results(team_name="Arsenal", status="FT")

        >>> # Get all matches (live + finished) for Premier League today
        >>> result = await get_match_results(
        ...     league_name="Premier League",
        ...     status="ALL"
        ... )
    """
    from datetime import UTC, datetime
    import logging
    logger = logging.getLogger(__name__)

    # Default to today if no date provided
    if date is None:
        date = datetime.now(UTC).date().isoformat()

    # ID-FIRST ARCHITECTURE: Resolve league to API-Football ID
    # This eliminates string matching ambiguity and enables efficient server-side filtering
    league_id: int | None = None
    canonical_league_name: str | None = None
    country_filter: str | None = None

    if league_name:
        league_id, canonical_league_name, country_filter = _resolve_league_to_id(
            league_name, user_query=user_query
        )
        logger.info(
            f"ID-first resolution: '{league_name}' → ID {league_id} "
            f"(canonical='{canonical_league_name}', country='{country_filter}')"
        )

    # Build cache key (include league_id for uniqueness)
    cache_filter = f"{league_id or 'all'}-{canonical_league_name or 'all'}-{country_filter or 'all'}"
    cache_key = f"match_results:{date}:{status}:{cache_filter}:{team_name or 'all'}"

    # Determine cache TTL based on status
    # LIVE data changes fast (2 min), finished data is static (1 hour)
    if status == "LIVE":
        cache_ttl = 120  # 2 minutes
    else:
        cache_ttl = 3600  # 1 hour

    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch from API-Football (REAL-TIME)
    # ID-FIRST: Pass league_id directly to API for efficient server-side filtering
    api_client = _get_api_football_client()
    async with api_client as client:
        # Handle status filter
        # NOTE: With ID-first architecture, API handles league filtering - no client-side needed
        if status == "ALL":
            # Fetch both live and finished
            # NOTE: API-Football doesn't support "ALL" status
            # We need to make 2 calls and merge results
            live_fixtures = await client.get_fixtures(date=date, league_id=league_id, status="LIVE")
            finished_fixtures = await client.get_fixtures(date=date, league_id=league_id, status="FT")
            fixtures = live_fixtures + finished_fixtures
        else:
            fixtures = await client.get_fixtures(date=date, league_id=league_id, status=status)

        logger.info(f"API-Football returned {len(fixtures)} fixtures (league_id={league_id})")

    # ID-FIRST: API already filtered by league_id - minimal client-side filtering needed
    # Only filter by country if league_id wasn't resolved (fallback for generic queries)
    if not league_id and country_filter:
        # Fallback: Filter by country only if league_id not resolved
        # This handles cases like "[Country] league results" without specific league
        original_count = len(fixtures)
        fixtures = [
            f for f in fixtures
            if f.get("league", {}).get("country", "") == country_filter
        ]
        logger.info(
            f"Fallback country filter: {original_count} → {len(fixtures)} fixtures "
            f"(country='{country_filter}', no league_id resolved)"
        )

    # Filter by team name if provided (case-insensitive substring match for home or away)
    if team_name:
        team_lower = team_name.lower()
        fixtures = [
            f for f in fixtures
            if (team_lower in f.get("teams", {}).get("home", {}).get("name", "").lower()
                or team_lower in f.get("teams", {}).get("away", {}).get("name", "").lower())
        ]

    # Package response (include league_id for debugging/tracing)
    response = {
        "matches": fixtures,
        "count": len(fixtures),
        "date": date,
        "status_filter": status,
        "league_filter": league_name,
        "league_id": league_id,  # API-Football ID used for filtering
        "team_filter": team_name,
    }

    # Cache result
    if cache:
        await cache.set(cache_key, response, ttl=cache_ttl)

    return response
