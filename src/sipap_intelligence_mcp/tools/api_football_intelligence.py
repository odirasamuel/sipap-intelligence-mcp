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


def _get_canonical_league_name(league_name: str, user_query: str | None = None) -> tuple[str | None, str | None]:
    """Map user-provided league name to canonical name and extract country.

    Uses sipap-common's comprehensive league mappings (380 competitions, 77 countries).
    Extracts country context to disambiguate leagues with same names (e.g., "Premier League").

    UNIVERSAL MATCHING STRATEGY:
    When user_query is provided, uses intelligent context-aware matching:
    1. Extract country from FULL query context
    2. Look up that country's specific leagues in sipap-common's COUNTRY_TO_LEAGUES
    3. Match league name portion ONLY against that country's leagues
    4. Eliminates "Belarus league" → "Premier League (England)" false matches

    IMPORTANT: International/continental tournaments (UEFA, FIFA, CONMEBOL, etc.) are labeled
    as country="World" by API-Football, NOT the host country. We detect these and return
    country=None to avoid filtering by host country.

    Args:
        league_name: User-provided league name (e.g., "Armenia Premier League", "Austria league")
        user_query: FULL user query for context-aware matching (RECOMMENDED)

    Returns:
        Tuple of (canonical_league_name, country_name) or (None, None) if not found
        For international tournaments, country_name is ALWAYS None (labeled as "World" in API-Football)

    Examples:
        >>> _get_canonical_league_name("Belarus league", "Belarus league results yesterday")
        ("Premier League", "Belarus")  # Correctly matches Belarus Premier League
        >>> _get_canonical_league_name("Spanish LaLiga", "Spanish LaLiga fixtures today")
        ("LaLiga", "Spain")  # Correctly matches Spain's LaLiga
        >>> _get_canonical_league_name("EPL")
        ("Premier League", "England")
        >>> _get_canonical_league_name("World Cup in Qatar")
        ("World Cup", None)  # Ignore "Qatar" - it's the host, not country classification
        >>> _get_canonical_league_name("Champions League")
        ("UEFA Champions League", None)  # International tournament
    """
    from sipap_common.data import (
        COUNTRY_TO_LEAGUES,
        COUNTRY_VARIANTS,
        INTERNATIONAL_TOURNAMENTS,
        find_league_matches,
    )

    # UNIVERSAL MATCHING: Use full user query if provided for better context
    query_to_analyze = user_query if user_query else league_name
    query_lower = query_to_analyze.lower()

    # Extract country from query (prioritize full query context)
    country = None
    for variant, official_name in COUNTRY_VARIANTS.items():
        if variant in query_lower:
            country = official_name
            break

    # IMPROVED MATCHING STRATEGY:
    # 1. Use find_league_matches() to leverage comprehensive alias system (handles "laliga" → "La Liga")
    # 2. If country is known, validate that the canonical name is in that country's leagues
    # 3. This combines alias resolution with country filtering

    import logging
    logger = logging.getLogger(__name__)

    canonical_names = find_league_matches(league_name)
    canonical_league_name = canonical_names[0] if canonical_names else None

    logger.info(
        f"Alias resolution: '{league_name}' → canonical={canonical_names}, country={country}",
        extra={"league_name": league_name, "canonical": canonical_names, "country": country}
    )

    # If country found, validate the canonical name is in that country's leagues
    if country and canonical_league_name and country.lower() in COUNTRY_TO_LEAGUES:
        country_leagues = COUNTRY_TO_LEAGUES[country.lower()]

        # Check if canonical name is in this country's leagues (case-insensitive)
        country_leagues_lower = [cl.lower() for cl in country_leagues]
        if canonical_league_name.lower() not in country_leagues_lower:
            # Canonical name doesn't belong to this country - likely wrong match
            # Example: "Spanish League" → "Premier League" (generic fallback) → not in Spain's leagues
            logger.warning(
                f"Country mismatch: '{canonical_league_name}' not in {country}'s leagues {country_leagues}",
                extra={"canonical": canonical_league_name, "country": country, "country_leagues": country_leagues}
            )
            canonical_league_name = None

    if not canonical_league_name:
        # No match found - return None
        logger.info(f"No valid match found for '{league_name}' in country '{country}'")
        return (None, country)

    # Check if this is an international tournament
    # API-Football labels these as country="World", NOT the host country
    # Override country to None to avoid filtering by host (e.g., "World Cup in Qatar")
    if canonical_league_name.lower() in INTERNATIONAL_TOURNAMENTS:
        country = None  # Force None - these are country="World" in API-Football

    return (canonical_league_name, country)


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

    # Default to today if no date provided
    if date is None:
        date = datetime.now(UTC).date().isoformat()

    # Map league name to canonical name + country using sipap-common comprehensive mappings
    # UNIVERSAL MATCHING: Pass full user_query for context-aware matching
    # This ensures "Belarus league" matches "Premier League (Belarus)", not "Premier League (England)"
    canonical_league_name = None
    country_filter = None
    if league_name:
        canonical_league_name, country_filter = _get_canonical_league_name(
            league_name, user_query=user_query
        )
        # DEBUG: Log what we extracted
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"League mapping: '{league_name}' (query='{user_query}') → "
            f"canonical='{canonical_league_name}', country='{country_filter}'"
        )

    # Build cache key
    cache_filter = f"{canonical_league_name or 'all'}-{country_filter or 'all'}"
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
    api_client = _get_api_football_client()
    async with api_client as client:
        # Handle status filter
        # NOTE: We fetch all fixtures for the date, then filter by exact league name
        # This avoids the "Armenia Premier League" → "Premier League" false match issue
        if status == "ALL":
            # Fetch both live and finished
            # NOTE: API-Football doesn't support "ALL" status
            # We need to make 2 calls and merge results
            live_fixtures = await client.get_fixtures(date=date, status="LIVE")
            finished_fixtures = await client.get_fixtures(date=date, status="FT")
            fixtures = live_fixtures + finished_fixtures
        else:
            fixtures = await client.get_fixtures(date=date, status=status)

    # Filter by canonical league name + country if provided (EXACT MATCH, not substring)
    # This fixes "Armenia Premier League" matching "Premier League" (England)
    import logging
    logger = logging.getLogger(__name__)

    if canonical_league_name:
        # DEBUG: Log first 3 fixture league names for debugging
        if fixtures:
            sample_leagues = [
                f"{f.get('league', {}).get('name', 'N/A')} ({f.get('league', {}).get('country', 'N/A')})"
                for f in fixtures[:3]
            ]
            logger.info(f"Sample API-Football leagues: {sample_leagues}")

        original_count = len(fixtures)
        if country_filter:
            # Filter by BOTH league name AND country for precise matching
            fixtures = [
                f for f in fixtures
                if (f.get("league", {}).get("name", "") == canonical_league_name
                    and f.get("league", {}).get("country", "") == country_filter)
            ]
            logger.info(
                f"Filtered {original_count} → {len(fixtures)} fixtures "
                f"(name='{canonical_league_name}', country='{country_filter}')"
            )
        else:
            # Filter by league name only (fallback if no country detected)
            fixtures = [
                f for f in fixtures
                if f.get("league", {}).get("name", "") == canonical_league_name
            ]
            logger.info(
                f"Filtered {original_count} → {len(fixtures)} fixtures "
                f"(name='{canonical_league_name}' only, no country)"
            )
    elif country_filter:
        # Fallback: Filter by country only if league name not recognized
        # This handles cases like "Wales Championship" where "Championship" isn't in mappings
        # but we can still filter by country to show all Welsh competitions
        original_count = len(fixtures)
        fixtures = [
            f for f in fixtures
            if f.get("league", {}).get("country", "") == country_filter
        ]
        logger.info(
            f"Filtered {original_count} → {len(fixtures)} fixtures "
            f"(country='{country_filter}' only, league name not recognized)"
        )

    # Filter by team name if provided (case-insensitive substring match for home or away)
    if team_name:
        team_lower = team_name.lower()
        fixtures = [
            f for f in fixtures
            if (team_lower in f.get("teams", {}).get("home", {}).get("name", "").lower()
                or team_lower in f.get("teams", {}).get("away", {}).get("name", "").lower())
        ]

    # Package response
    response = {
        "matches": fixtures,
        "count": len(fixtures),
        "date": date,
        "status_filter": status,
        "league_filter": league_name,
        "team_filter": team_name,
    }

    # Cache result
    if cache:
        await cache.set(cache_key, response, ttl=cache_ttl)

    return response
