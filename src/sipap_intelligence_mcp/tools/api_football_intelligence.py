"""API-Football Intelligence Tools for MCP server.

Provides 5 intelligence tools using API-Football data:
1. get_match_predictions - AI predictions for fixtures
2. get_sidelined_players - Player/coach availability status
3. get_player_transfers - Transfer history and news
4. get_available_timezones - Timezone data for accurate scheduling
5. get_match_results - Live and completed match results with scores (REAL-TIME)
"""

import os
from datetime import datetime
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


def _extract_best_odds(odds_data: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    """Extract best odds (highest) for each fixture from API-Football odds response.

    API-Football odds structure:
    {
        "fixture": {"id": 12345},
        "bookmakers": [
            {
                "id": 8,
                "name": "Bet365",
                "bets": [
                    {
                        "id": 1,  # Match Winner
                        "name": "Match Winner",
                        "values": [
                            {"value": "Home", "odd": "2.50"},
                            {"value": "Draw", "odd": "3.20"},
                            {"value": "Away", "odd": "2.80"}
                        ]
                    }
                ]
            }
        ]
    }

    Returns:
        Dict mapping fixture_id to best odds: {fixture_id: {"home": 2.50, "draw": 3.20, "away": 2.80}}
    """
    best_odds: dict[int, dict[str, float]] = {}

    for odds_entry in odds_data:
        fixture_id = odds_entry.get("fixture", {}).get("id")
        if not fixture_id:
            continue

        # Initialize with zeros
        home_odds: float = 0.0
        draw_odds: float = 0.0
        away_odds: float = 0.0

        # Iterate through all bookmakers to find best odds
        bookmakers = odds_entry.get("bookmakers", [])
        for bookmaker in bookmakers:
            bets = bookmaker.get("bets", [])
            for bet in bets:
                # Only process Match Winner (bet_id=1)
                if bet.get("id") != 1:
                    continue

                values = bet.get("values", [])
                for value in values:
                    try:
                        odd_value = float(value.get("odd", 0))
                        outcome = value.get("value", "")

                        # Track highest odds for each outcome
                        if outcome == "Home" and odd_value > home_odds:
                            home_odds = odd_value
                        elif outcome == "Draw" and odd_value > draw_odds:
                            draw_odds = odd_value
                        elif outcome == "Away" and odd_value > away_odds:
                            away_odds = odd_value
                    except (ValueError, TypeError):
                        continue

        # Only add if we found at least one valid odd
        if home_odds > 0 or draw_odds > 0 or away_odds > 0:
            best_odds[fixture_id] = {
                "home": home_odds,
                "draw": draw_odds,
                "away": away_odds,
            }

    return best_odds


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
    league_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Get live or completed match results from API-Football (REAL-TIME DATA).

    MCP Tool: Fetches actual match scores and status directly from API-Football.
    This provides LIVE, REAL-TIME data, not cached database data.

    PREFERRED: Pass league_ids directly for accurate filtering.
    This bypasses name resolution and uses API-Football IDs directly.

    Use this tool when user asks for:
    - "What are the results for...?"
    - "What's the score of...?"
    - "How did [team] do...?"
    - "Show me live matches"
    - "What's happening in [competition]?"
    - "Show fixtures for [country/league] tomorrow"

    Status values:
        - "NS" - Not Started (upcoming fixtures)
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

    # ID-FIRST ARCHITECTURE: Use league_ids directly if provided (PREFERRED)
    # This bypasses name resolution completely - orchestrator passes IDs from NLU
    resolved_league_ids: list[int] = []
    canonical_league_name: str | None = None
    country_filter: str | None = None

    if league_ids:
        # Direct ID-first path: Use the provided API-Football IDs
        resolved_league_ids = league_ids
        logger.info(f"Using provided league_ids directly: {league_ids}")
    elif league_name:
        # Legacy path: Resolve league name to ID
        league_id, canonical_league_name, country_filter = _resolve_league_to_id(
            league_name, user_query=user_query
        )
        if league_id:
            resolved_league_ids = [league_id]
        logger.info(
            f"ID-first resolution: '{league_name}' → ID {league_id} "
            f"(canonical='{canonical_league_name}', country='{country_filter}')"
        )

    # Build cache key (include league_ids for uniqueness)
    league_ids_str = "-".join(str(lid) for lid in sorted(resolved_league_ids)) if resolved_league_ids else "all"
    cache_filter = f"{league_ids_str}-{canonical_league_name or 'all'}-{country_filter or 'all'}"
    cache_key = f"match_results:{date}:{status}:{cache_filter}:{team_name or 'all'}"

    # Determine cache TTL based on status
    # LIVE data changes fast (2 min), NS/finished data is more static (30 min for NS, 1 hour for FT)
    if status == "LIVE":
        cache_ttl = 120  # 2 minutes
    elif status == "NS":
        cache_ttl = 1800  # 30 minutes for upcoming fixtures
    else:
        cache_ttl = 3600  # 1 hour for finished

    # Try cache first (Sentinel Pattern #20: Cache-Aside)
    cache = _get_cache()
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Fetch from API-Football (REAL-TIME)
    # ID-FIRST: Pass league_ids directly to API for efficient server-side filtering
    api_client = _get_api_football_client()
    async with api_client as client:
        # Determine season from date (API-Football requires season when league_id is provided)
        # Football seasons typically span Aug-May, so:
        # - Jan-Jul: use previous year as season start (e.g., Jan 2026 → season 2025)
        # - Aug-Dec: use current year as season start (e.g., Aug 2026 → season 2026)
        date_obj = datetime.fromisoformat(date)
        season = date_obj.year if date_obj.month >= 8 else date_obj.year - 1

        fixtures: list[dict[str, Any]] = []

        # Fetch fixtures for each league ID (or all leagues if no IDs specified)
        if resolved_league_ids:
            # Fetch fixtures for each specified league ID
            for league_id in resolved_league_ids:
                if status == "ALL":
                    # Fetch both live and finished for this league
                    live = await client.get_fixtures(date=date, league_id=league_id, season=season, status="LIVE")
                    finished = await client.get_fixtures(date=date, league_id=league_id, season=season, status="FT")
                    fixtures.extend(live)
                    fixtures.extend(finished)
                else:
                    league_fixtures = await client.get_fixtures(date=date, league_id=league_id, season=season, status=status)
                    fixtures.extend(league_fixtures)
            logger.info(f"API-Football returned {len(fixtures)} fixtures for {len(resolved_league_ids)} leagues: {resolved_league_ids}")
        else:
            # No league IDs specified - fetch all fixtures for date
            if status == "ALL":
                live_fixtures = await client.get_fixtures(date=date, season=season, status="LIVE")
                finished_fixtures = await client.get_fixtures(date=date, season=season, status="FT")
                fixtures = live_fixtures + finished_fixtures
            else:
                fixtures = await client.get_fixtures(date=date, season=season, status=status)
            logger.info(f"API-Football returned {len(fixtures)} fixtures (no league filter)")

        # Fetch odds for upcoming fixtures (NS status only - odds not needed for finished matches)
        # Uses efficient fixture ID-based fetching with rate limit handling
        if status == "NS" and fixtures:
            try:
                # Get fixture IDs for odds lookup
                fixture_ids = [f.get("fixture", {}).get("id") for f in fixtures if f.get("fixture", {}).get("id")]

                if fixture_ids:
                    logger.info(f"Fetching odds for {len(fixture_ids)} fixtures using fixture ID-based approach")

                    # Use the new efficient fixture-based odds fetching
                    # This fetches odds by fixture ID with rate limiting and batching
                    best_odds = await client.get_odds_for_fixtures(
                        fixture_ids=fixture_ids,
                        bet_id=1,  # Match Winner (1X2)
                        batch_size=5,  # 5 fixtures per batch
                        delay_between_batches=0.3,  # 300ms between batches
                    )

                    if best_odds:
                        # Merge odds into fixtures
                        odds_count = 0
                        for fixture in fixtures:
                            fixture_id = fixture.get("fixture", {}).get("id")
                            if fixture_id and fixture_id in best_odds:
                                odds = best_odds[fixture_id]
                                # Add odds to fixture in format expected by orchestrator
                                fixture["best_home_odds"] = odds.get("home", 0)
                                fixture["best_draw_odds"] = odds.get("draw", 0)
                                fixture["best_away_odds"] = odds.get("away", 0)
                                odds_count += 1

                        logger.info(f"Added odds to {odds_count}/{len(fixtures)} fixtures")
                    else:
                        logger.info("No odds data returned for fixtures")
            except Exception as e:
                # Odds fetching is optional - don't fail the whole request if it fails
                logger.warning(f"Failed to fetch odds (continuing without odds): {e}")

    # SAFETY FILTER: Verify fixtures match requested league IDs AND countries
    # API-Football sometimes returns fixtures with mismatched data
    if resolved_league_ids:
        # Get expected countries from our league reference
        from sipap_common.data.league_reference import get_league_by_id
        expected_countries = set()
        for lid in resolved_league_ids:
            league_info = get_league_by_id(lid)
            if league_info and league_info.get("country"):
                expected_countries.add(league_info["country"])

        logger.info(f"Safety filter setup: expected_countries={expected_countries} for league_ids={resolved_league_ids}")

        original_count = len(fixtures)

        # Debug: Log all fixture countries before filtering
        fixture_countries = set(f.get("league", {}).get("country", "UNKNOWN") for f in fixtures)
        fixture_leagues = [(f.get("league", {}).get("id"), f.get("league", {}).get("name"), f.get("league", {}).get("country")) for f in fixtures[:5]]
        logger.info(f"Before filter: {len(fixtures)} fixtures, countries={fixture_countries}, sample leagues={fixture_leagues}")

        # Filter by BOTH league ID AND country to catch data inconsistencies
        if expected_countries:
            fixtures = [
                f for f in fixtures
                if (f.get("league", {}).get("id") in resolved_league_ids
                    and f.get("league", {}).get("country") in expected_countries)
            ]
        else:
            # Fallback to ID-only filter if no country info
            fixtures = [
                f for f in fixtures
                if f.get("league", {}).get("id") in resolved_league_ids
            ]

        if len(fixtures) != original_count:
            logger.warning(
                f"Safety filter: {original_count} → {len(fixtures)} fixtures "
                f"(requested IDs: {resolved_league_ids}, expected countries: {expected_countries})"
            )
        else:
            logger.info(f"Safety filter: All {len(fixtures)} fixtures passed (no mismatches found)")
    elif country_filter:
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

    # Package response (include league_ids for debugging/tracing)
    response = {
        "matches": fixtures,
        "count": len(fixtures),
        "date": date,
        "status_filter": status,
        "league_filter": league_name,
        "league_ids": resolved_league_ids,  # API-Football IDs used for filtering
        "team_filter": team_name,
    }

    # Cache result
    if cache:
        await cache.set(cache_key, response, ttl=cache_ttl)

    return response
