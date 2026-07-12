"""Unit tests for news intelligence tools."""

from unittest.mock import AsyncMock, patch

import pytest

from sipap_intelligence_mcp.tools.news import analyze_team_news, get_injury_reports


@pytest.mark.asyncio
async def test_analyze_team_news():
    """Test news sentiment analysis."""
    with patch("sipap_intelligence_mcp.tools.news._get_claude_client") as mock_client:
        mock_claude = AsyncMock()
        mock_claude.analyze_text.return_value = {
            "sentiment": "positive",
            "confidence": 0.90,
            "key_topics": ["winning_streak", "morale"],
            "impact_summary": "Team confidence high"
        }
        mock_client.return_value = mock_claude

        result = await analyze_team_news(
            team_id="team-123",
            team_name="Arsenal",
            news_text="Arsenal wins 3-0 in dominant performance"
        )

        assert result["sentiment"] == "positive"
        assert result["confidence"] == 0.90
        assert "winning_streak" in result["key_topics"]


@pytest.mark.asyncio
async def test_get_injury_reports():
    """Test injury reports with AI assessment."""
    with patch("sipap_intelligence_mcp.tools.news._get_claude_client") as mock_client:
        mock_claude = AsyncMock()
        mock_claude.analyze_text.return_value = {
            "impact_level": "high",
            "confidence": 0.85,
            "factors": ["star_player_missing"],
            "recommendation": "Significant impact expected"
        }
        mock_client.return_value = mock_claude

        result = await get_injury_reports(
            team_id="team-123",
            team_name="Chelsea",
            severity_filter="all"
        )

        assert "injuries" in result
        assert "overall_impact" in result
        assert result["overall_impact"]["impact_level"] == "high"
