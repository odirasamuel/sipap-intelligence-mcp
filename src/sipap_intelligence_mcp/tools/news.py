"""News intelligence tools for MCP server.

Provides news sentiment analysis and injury impact assessment.
"""

import os
from typing import Any

from sipap_common.cache import RedisCache  # type: ignore[import-untyped]

from sipap_intelligence_mcp.ai.claude import ClaudeBedrockClient
from sipap_intelligence_mcp.ai.prompts import PromptTemplates

# Global clients for Lambda warm start optimization
_claude_client: ClaudeBedrockClient | None = None
_cache: RedisCache | None = None


def _get_claude_client() -> ClaudeBedrockClient:
    """Get or create Claude/Bedrock client (cached for warm starts)."""
    global _claude_client
    if _claude_client is None:
        region = os.getenv("AWS_REGION", "us-east-1")
        _claude_client = ClaudeBedrockClient(region=region)
    return _claude_client


def _get_cache() -> RedisCache | None:
    """Get or create Redis cache (cached for warm starts)."""
    global _cache
    if _cache is None:
        redis_endpoint = os.getenv("REDIS_ENDPOINT")
        if redis_endpoint:
            _cache = RedisCache(endpoint=redis_endpoint)
    return _cache


async def analyze_team_news(
    team_id: str,
    team_name: str,
    news_text: str,
    days_back: int = 7
) -> dict[str, Any]:
    """Analyze sentiment of recent team news using AI.

    MCP Tool: Uses Claude for sentiment analysis of sports news.

    Args:
        team_id: Team identifier for caching
        team_name: Team name for contextualized analysis
        news_text: News articles/headlines to analyze
        days_back: Number of days of news analyzed (for context)

    Returns:
        Sentiment analysis with:
            - sentiment: positive, negative, neutral
            - confidence: 0.0-1.0
            - key_topics: Main topics discussed
            - impact_summary: Potential match impact
    """
    # Try cache first (6 hour TTL - news changes less frequently)
    cache = _get_cache()
    if cache:
        cache_key = f"news:sentiment:{team_id}:{days_back}"
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # Generate AI analysis prompt
    prompt = PromptTemplates.news_sentiment_prompt(
        news_text=news_text,
        team_name=team_name
    )
    system_prompt = PromptTemplates.news_sentiment_system_prompt()
    schema = PromptTemplates.get_response_schema("sentiment")

    # Get Claude analysis
    claude = _get_claude_client()
    result = await claude.analyze_text(
        prompt=prompt,
        system_prompt=system_prompt,
        response_schema=schema,
        max_tokens=400,
        temperature=0.5
    )

    # Cache result (6 hour TTL)
    if cache:
        await cache.set(cache_key, result, ttl=21600)

    return result


async def get_injury_reports(
    team_id: str,
    team_name: str,
    severity_filter: str = "all"
) -> dict[str, Any]:
    """Get injury reports with AI-powered impact assessment.

    MCP Tool: Fetches injuries and uses Claude to assess impact.

    Args:
        team_id: Team identifier
        team_name: Team name
        severity_filter: Filter by severity (all, major, minor)

    Returns:
        Injury report with:
            - injuries: List of current injuries
            - overall_impact: Combined impact assessment
                - impact_level: low, medium, high
                - confidence: 0.0-1.0
                - factors: Key factors
                - recommendation: Betting implications
    """
    # Try cache first (24 hour TTL - injuries don't change often)
    cache = _get_cache()
    if cache:
        cache_key = f"injuries:{team_id}:{severity_filter}"
        cached = await cache.get(cache_key)
        if cached:
            result: dict[str, Any] = cached
            return result

    # TODO: In production, fetch from database
    # For MVP, use mock injury data
    injuries = _get_mock_injury_data(team_id, severity_filter)

    # Generate combined injury context for AI analysis
    injury_summary = "\n".join([
        f"- {injury['player']}: {injury['injury_type']} ({injury['severity']}) - {injury['timeline']}"
        for injury in injuries
    ])

    if not injury_summary:
        injury_summary = "No significant injuries reported"

    # Get AI impact assessment
    prompt = PromptTemplates.injury_impact_prompt(
        injury_details=injury_summary,
        team_name=team_name
    )
    system_prompt = PromptTemplates.injury_impact_system_prompt()
    schema = PromptTemplates.get_response_schema("injury")

    claude = _get_claude_client()
    impact_assessment = await claude.analyze_text(
        prompt=prompt,
        system_prompt=system_prompt,
        response_schema=schema,
        max_tokens=400,
        temperature=0.6
    )

    result = {
        "injuries": injuries,
        "overall_impact": impact_assessment
    }

    # Cache result (24 hour TTL)
    if cache:
        await cache.set(cache_key, result, ttl=86400)

    return result


def _get_mock_injury_data(
    team_id: str,
    severity_filter: str
) -> list[dict[str, Any]]:
    """Get mock injury data (placeholder for database query).

    Args:
        team_id: Team identifier
        severity_filter: Severity filter

    Returns:
        List of injury records
    """
    # Mock data for development/testing
    all_injuries = [
        {
            "player": "Star Striker",
            "position": "Forward",
            "injury_type": "ACL tear",
            "severity": "major",
            "timeline": "Out 6 months",
            "return_date": "2024-09-01"
        },
        {
            "player": "Backup Defender",
            "position": "Defender",
            "injury_type": "Hamstring strain",
            "severity": "minor",
            "timeline": "Out 2 weeks",
            "return_date": "2024-03-15"
        }
    ]

    if severity_filter == "all":
        return all_injuries
    else:
        return [inj for inj in all_injuries if inj["severity"] == severity_filter]
