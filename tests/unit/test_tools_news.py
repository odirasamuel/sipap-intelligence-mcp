"""Unit tests for news intelligence tools.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve implementation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sipap_intelligence_mcp.tools import news


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_news_articles():
    """Mock news articles from NewsAPI."""
    return [
        {
            "title": "Team wins crucial match 3-0",
            "source": "ESPN",
            "published_at": "2024-07-10T14:30:00Z",
            "description": "Dominant performance secures top spot",
            "content": "The team delivered an outstanding performance...",
            "url": "https://espn.com/article1"
        },
        {
            "title": "Star player signs contract extension",
            "source": "BBC Sport",
            "published_at": "2024-07-09T10:15:00Z",
            "description": "Five-year deal confirmed",
            "content": "The club announced today...",
            "url": "https://bbc.com/article2"
        },
        {
            "title": "Manager praises team spirit",
            "source": "Sky Sports",
            "published_at": "2024-07-08T18:45:00Z",
            "description": "Post-match interview highlights",
            "content": "The manager was delighted...",
            "url": "https://skysports.com/article3"
        }
    ]


@pytest.fixture
def mock_sentiment_analysis():
    """Mock sentiment analysis result."""
    return {
        "sentiment": "positive",
        "confidence": 0.90,
        "key_topics": ["winning_streak", "player_morale", "contract_extension"],
        "impact_summary": "Team confidence is high with recent wins and player commitment"
    }


@pytest.fixture
def mock_injury_impact():
    """Mock injury impact assessment."""
    return {
        "impact_level": "high",
        "confidence": 0.85,
        "factors": ["star_player_missing", "defensive_weakness"],
        "recommendation": "Significant impact expected on offensive capabilities"
    }


class TestFetchAndAnalyzeTeamNews:
    """Test fetch_and_analyze_team_news tool."""

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_success(
        self, mock_news_articles, mock_sentiment_analysis
    ):
        """Test fetching and analyzing news succeeds."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news.analyze_team_news"
        ) as mock_analyze:
            # Mock NewsAPI client
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.search_team_news = AsyncMock(return_value=mock_news_articles)
            mock_get_news.return_value = mock_client

            # Mock sentiment analysis
            mock_analyze.return_value = mock_sentiment_analysis

            result = await news.fetch_and_analyze_team_news(
                team_id="team-123",
                team_name="Liverpool"
            )

            assert result["sentiment"] == "positive"
            assert result["confidence"] == 0.90
            assert result["articles_analyzed"] == 3
            assert len(result["news_sources"]) == 3
            assert result["news_sources"][0]["title"] == "Team wins crucial match 3-0"

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_no_articles(self):
        """Test handling when no articles found."""
        with patch("sipap_intelligence_mcp.tools.news._get_news_client") as mock_get_news:
            # Mock NewsAPI client returning empty list
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.search_team_news = AsyncMock(return_value=[])
            mock_get_news.return_value = mock_client

            result = await news.fetch_and_analyze_team_news(
                team_id="team-456",
                team_name="Chelsea"
            )

            assert result["sentiment"] == "neutral"
            assert result["confidence"] == 0.5
            assert result["articles_analyzed"] == 0
            assert result["key_topics"] == []
            assert "No recent news found" in result["impact_summary"]

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_with_cache_hit(
        self, mock_sentiment_analysis, mock_redis_cache
    ):
        """Test news returns cached data if available."""
        cached_result = {
            **mock_sentiment_analysis,
            "articles_analyzed": 5,
            "news_sources": []
        }
        mock_redis_cache.get = AsyncMock(return_value=cached_result)

        with patch("sipap_intelligence_mcp.tools.news._get_cache") as mock_get_cache:
            mock_get_cache.return_value = mock_redis_cache

            result = await news.fetch_and_analyze_team_news(
                team_id="team-123",
                team_name="Liverpool"
            )

            # Should return cached data without calling NewsAPI
            assert result == cached_result
            mock_redis_cache.get.assert_called_once_with("news:full:team-123:7")

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_caches_result(
        self, mock_news_articles, mock_sentiment_analysis, mock_redis_cache
    ):
        """Test news caches API result."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news.analyze_team_news"
        ) as mock_analyze:
            mock_get_cache.return_value = mock_redis_cache

            # Mock NewsAPI client
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.search_team_news = AsyncMock(return_value=mock_news_articles)
            mock_get_news.return_value = mock_client

            # Mock sentiment analysis
            mock_analyze.return_value = mock_sentiment_analysis

            await news.fetch_and_analyze_team_news(
                team_id="team-123",
                team_name="Liverpool",
                days_back=7
            )

            # Should cache result with 6 hour TTL
            assert mock_redis_cache.set.called
            call_args = mock_redis_cache.set.call_args
            assert call_args[0][0] == "news:full:team-123:7"
            assert call_args[1]["ttl"] == 21600

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_without_cache(
        self, mock_news_articles, mock_sentiment_analysis
    ):
        """Test news works without Redis cache."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news.analyze_team_news"
        ) as mock_analyze:
            mock_get_cache.return_value = None  # No cache available

            # Mock NewsAPI client
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.search_team_news = AsyncMock(return_value=mock_news_articles)
            mock_get_news.return_value = mock_client

            # Mock sentiment analysis
            mock_analyze.return_value = mock_sentiment_analysis

            result = await news.fetch_and_analyze_team_news(
                team_id="team-789",
                team_name="Arsenal"
            )

            assert result["sentiment"] == "positive"
            assert result["articles_analyzed"] == 3

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_custom_parameters(
        self, mock_news_articles, mock_sentiment_analysis
    ):
        """Test news with custom days_back and max_articles."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news.analyze_team_news"
        ) as mock_analyze:
            # Mock NewsAPI client
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.search_team_news = AsyncMock(return_value=mock_news_articles)
            mock_get_news.return_value = mock_client

            # Mock sentiment analysis
            mock_analyze.return_value = mock_sentiment_analysis

            result = await news.fetch_and_analyze_team_news(
                team_id="team-999",
                team_name="Manchester United",
                days_back=14,
                max_articles=20
            )

            # Verify custom parameters were used
            mock_client.search_team_news.assert_called_once_with(
                team_name="Manchester United",
                days_back=14,
                max_results=20
            )
            assert result["sentiment"] == "positive"

    @pytest.mark.asyncio
    async def test_fetch_and_analyze_limits_news_sources(
        self, mock_sentiment_analysis
    ):
        """Test news sources limited to top 5."""
        # Create 10 mock articles
        many_articles = [
            {
                "title": f"Article {i}",
                "source": f"Source {i}",
                "published_at": f"2024-07-{10-i:02d}T12:00:00Z",
                "description": f"Description {i}",
                "content": f"Content {i}",
                "url": f"https://example.com/article{i}"
            }
            for i in range(10)
        ]

        with patch(
            "sipap_intelligence_mcp.tools.news._get_news_client"
        ) as mock_get_news, patch(
            "sipap_intelligence_mcp.tools.news.analyze_team_news"
        ) as mock_analyze:
            # Mock NewsAPI client
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.search_team_news = AsyncMock(return_value=many_articles)
            mock_get_news.return_value = mock_client

            # Mock sentiment analysis
            mock_analyze.return_value = mock_sentiment_analysis

            result = await news.fetch_and_analyze_team_news(
                team_id="team-555",
                team_name="Tottenham"
            )

            # Should only return top 5 sources
            assert result["articles_analyzed"] == 10
            assert len(result["news_sources"]) == 5


class TestAnalyzeTeamNews:
    """Test analyze_team_news tool."""

    @pytest.mark.asyncio
    async def test_analyze_team_news_success(self, mock_sentiment_analysis):
        """Test news sentiment analysis succeeds."""
        with patch("sipap_intelligence_mcp.tools.news._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_sentiment_analysis)
            mock_get_client.return_value = mock_client

            result = await news.analyze_team_news(
                team_id="team-123",
                team_name="Arsenal",
                news_text="Arsenal wins 3-0 in dominant performance"
            )

            assert result["sentiment"] == "positive"
            assert result["confidence"] == 0.90
            assert "winning_streak" in result["key_topics"]

    @pytest.mark.asyncio
    async def test_analyze_team_news_with_cache_hit(
        self, mock_sentiment_analysis, mock_redis_cache
    ):
        """Test sentiment analysis returns cached data if available."""
        mock_redis_cache.get = AsyncMock(return_value=mock_sentiment_analysis)

        with patch("sipap_intelligence_mcp.tools.news._get_cache") as mock_get_cache:
            mock_get_cache.return_value = mock_redis_cache

            result = await news.analyze_team_news(
                team_id="team-456",
                team_name="Chelsea",
                news_text="Chelsea draws 1-1"
            )

            # Should return cached data without calling Claude
            assert result == mock_sentiment_analysis
            mock_redis_cache.get.assert_called_once_with("news:sentiment:team-456:7")

    @pytest.mark.asyncio
    async def test_analyze_team_news_caches_result(
        self, mock_sentiment_analysis, mock_redis_cache
    ):
        """Test sentiment analysis caches result."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_sentiment_analysis)
            mock_get_client.return_value = mock_client

            await news.analyze_team_news(
                team_id="team-789",
                team_name="Liverpool",
                news_text="Liverpool wins Premier League",
                days_back=7
            )

            # Should cache result with 6 hour TTL
            mock_redis_cache.set.assert_called_once_with(
                "news:sentiment:team-789:7", mock_sentiment_analysis, ttl=21600
            )

    @pytest.mark.asyncio
    async def test_analyze_team_news_without_cache(self, mock_sentiment_analysis):
        """Test sentiment analysis works without Redis cache."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_client:
            mock_get_cache.return_value = None  # No cache available

            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_sentiment_analysis)
            mock_get_client.return_value = mock_client

            result = await news.analyze_team_news(
                team_id="team-999",
                team_name="Manchester City",
                news_text="Manchester City advances to finals"
            )

            assert result == mock_sentiment_analysis


class TestGetInjuryReports:
    """Test get_injury_reports tool."""

    @pytest.mark.asyncio
    async def test_get_injury_reports_all_severity(self, mock_injury_impact):
        """Test injury reports with all severity filter."""
        with patch("sipap_intelligence_mcp.tools.news._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_injury_impact)
            mock_get_client.return_value = mock_client

            result = await news.get_injury_reports(
                team_id="team-123",
                team_name="Chelsea",
                severity_filter="all"
            )

            assert "injuries" in result
            assert "overall_impact" in result
            assert result["overall_impact"]["impact_level"] == "high"
            assert len(result["injuries"]) == 2  # Mock has 2 injuries

    @pytest.mark.asyncio
    async def test_get_injury_reports_major_only(self, mock_injury_impact):
        """Test injury reports filtered by major severity."""
        with patch("sipap_intelligence_mcp.tools.news._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_injury_impact)
            mock_get_client.return_value = mock_client

            result = await news.get_injury_reports(
                team_id="team-456",
                team_name="Liverpool",
                severity_filter="major"
            )

            assert len(result["injuries"]) == 1  # Only major injuries
            assert result["injuries"][0]["severity"] == "major"

    @pytest.mark.asyncio
    async def test_get_injury_reports_minor_only(self, mock_injury_impact):
        """Test injury reports filtered by minor severity."""
        with patch("sipap_intelligence_mcp.tools.news._get_claude_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_injury_impact)
            mock_get_client.return_value = mock_client

            result = await news.get_injury_reports(
                team_id="team-789",
                team_name="Arsenal",
                severity_filter="minor"
            )

            assert len(result["injuries"]) == 1  # Only minor injuries
            assert result["injuries"][0]["severity"] == "minor"

    @pytest.mark.asyncio
    async def test_get_injury_reports_with_cache_hit(
        self, mock_injury_impact, mock_redis_cache
    ):
        """Test injury reports returns cached data if available."""
        cached_result = {
            "injuries": [],
            "overall_impact": mock_injury_impact
        }
        mock_redis_cache.get = AsyncMock(return_value=cached_result)

        with patch("sipap_intelligence_mcp.tools.news._get_cache") as mock_get_cache:
            mock_get_cache.return_value = mock_redis_cache

            result = await news.get_injury_reports(
                team_id="team-123",
                team_name="Chelsea"
            )

            # Should return cached data without calling Claude
            assert result == cached_result
            mock_redis_cache.get.assert_called_once_with("injuries:team-123:all")

    @pytest.mark.asyncio
    async def test_get_injury_reports_caches_result(
        self, mock_injury_impact, mock_redis_cache
    ):
        """Test injury reports caches result."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_client:
            mock_get_cache.return_value = mock_redis_cache

            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_injury_impact)
            mock_get_client.return_value = mock_client

            await news.get_injury_reports(
                team_id="team-456",
                team_name="Liverpool",
                severity_filter="major"
            )

            # Should cache result with 24 hour TTL
            assert mock_redis_cache.set.called
            call_args = mock_redis_cache.set.call_args
            assert call_args[0][0] == "injuries:team-456:major"
            assert call_args[1]["ttl"] == 86400

    @pytest.mark.asyncio
    async def test_get_injury_reports_without_cache(self, mock_injury_impact):
        """Test injury reports works without Redis cache."""
        with patch(
            "sipap_intelligence_mcp.tools.news._get_cache"
        ) as mock_get_cache, patch(
            "sipap_intelligence_mcp.tools.news._get_claude_client"
        ) as mock_get_client:
            mock_get_cache.return_value = None  # No cache available

            mock_client = AsyncMock()
            mock_client.analyze_text = AsyncMock(return_value=mock_injury_impact)
            mock_get_client.return_value = mock_client

            result = await news.get_injury_reports(
                team_id="team-999",
                team_name="Manchester United"
            )

            assert "injuries" in result
            assert result["overall_impact"] == mock_injury_impact


class TestMockInjuryData:
    """Test _get_mock_injury_data helper."""

    def test_mock_injury_data_all_severity(self):
        """Test mock data returns all injuries."""
        result = news._get_mock_injury_data(
            team_id="team-123",
            severity_filter="all"
        )

        assert isinstance(result, list)
        assert len(result) == 2  # Mock has 2 injuries

    def test_mock_injury_data_major_only(self):
        """Test mock data filters major injuries."""
        result = news._get_mock_injury_data(
            team_id="team-456",
            severity_filter="major"
        )

        assert len(result) == 1
        assert result[0]["severity"] == "major"
        assert "ACL tear" in result[0]["injury_type"]

    def test_mock_injury_data_minor_only(self):
        """Test mock data filters minor injuries."""
        result = news._get_mock_injury_data(
            team_id="team-789",
            severity_filter="minor"
        )

        assert len(result) == 1
        assert result[0]["severity"] == "minor"
        assert "Hamstring" in result[0]["injury_type"]

    def test_mock_injury_data_structure(self):
        """Test mock data has correct structure."""
        result = news._get_mock_injury_data(
            team_id="team-999",
            severity_filter="all"
        )

        assert len(result) > 0
        first_injury = result[0]
        assert "player" in first_injury
        assert "position" in first_injury
        assert "injury_type" in first_injury
        assert "severity" in first_injury
        assert "timeline" in first_injury
        assert "return_date" in first_injury
