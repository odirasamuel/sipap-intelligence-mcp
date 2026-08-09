"""NewsAPI client for sports news fetching.

Provides news data for team sentiment analysis and match intelligence.
Free tier: 100 requests/day (sufficient for MVP)
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from sipap_intelligence_mcp.exceptions import NewsAPIException


class NewsAPIClient:
    """
    Client for NewsAPI.org.

    Fetches sports news articles for team sentiment analysis.
    Used to get recent news about teams and matches.

    API Documentation: https://newsapi.org/docs
    """

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: str, timeout: float = 10.0):
        """
        Initialize NewsAPI client.

        Args:
            api_key: NewsAPI.org API key
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NewsAPIClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def search_team_news(
        self,
        team_name: str,
        days_back: int = 7,
        language: str = "en",
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for recent news about a specific team.

        Args:
            team_name: Team name to search for (e.g., "Arsenal", "Chelsea")
            days_back: How many days back to search (max 30 for free tier)
            language: Language code (default: "en")
            max_results: Maximum number of articles to return (max 100)

        Returns:
            List of news articles, each with:
                - title: Article title
                - description: Article description
                - content: Article content (may be truncated)
                - url: Article URL
                - published_at: Publication timestamp
                - source: News source name
                - author: Article author (if available)

        Raises:
            NewsAPIException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        # Calculate date range (NewsAPI free tier: max 30 days back)
        if days_back > 30:
            days_back = 30

        to_date = datetime.now(UTC)
        from_date = to_date - timedelta(days=days_back)

        # Everything endpoint (searches title + description + content)
        url = f"{self.BASE_URL}/everything"
        params: dict[str, str | int] = {
            "q": team_name,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "language": language,
            "sortBy": "publishedAt",  # Most recent first
            "pageSize": min(max_results, 100),  # Max 100 per request
            "apiKey": self.api_key,
        }

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                error_message = data.get("message", "Unknown error")
                raise NewsAPIException(f"NewsAPI error: {error_message}")

            articles = data.get("articles", [])

            # Transform to consistent format
            return [
                {
                    "title": article["title"],
                    "description": article.get("description", ""),
                    "content": article.get("content", ""),
                    "url": article["url"],
                    "published_at": article["publishedAt"],
                    "source": article["source"]["name"],
                    "author": article.get("author"),
                }
                for article in articles
            ]

        except httpx.HTTPError as e:
            raise NewsAPIException(f"HTTP error fetching news: {str(e)}") from e
        except Exception as e:
            raise NewsAPIException(f"Error fetching team news: {str(e)}") from e

    async def get_top_headlines(
        self,
        sport: str = "sports",
        country: str = "us",
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Get top sports headlines for a country.

        Args:
            sport: Category (default: "sports")
            country: Country code (e.g., "us", "gb", "de")
            max_results: Maximum number of headlines (max 100)

        Returns:
            List of news articles (same format as search_team_news)

        Raises:
            NewsAPIException: If API request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        url = f"{self.BASE_URL}/top-headlines"
        params: dict[str, str | int] = {
            "category": sport,
            "country": country,
            "pageSize": min(max_results, 100),
            "apiKey": self.api_key,
        }

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                error_message = data.get("message", "Unknown error")
                raise NewsAPIException(f"NewsAPI error: {error_message}")

            articles = data.get("articles", [])

            # Transform to consistent format
            return [
                {
                    "title": article["title"],
                    "description": article.get("description", ""),
                    "content": article.get("content", ""),
                    "url": article["url"],
                    "published_at": article["publishedAt"],
                    "source": article["source"]["name"],
                    "author": article.get("author"),
                }
                for article in articles
            ]

        except httpx.HTTPError as e:
            raise NewsAPIException(f"HTTP error fetching headlines: {str(e)}") from e
        except Exception as e:
            raise NewsAPIException(f"Error fetching top headlines: {str(e)}") from e

    async def search_match_news(
        self,
        home_team: str,
        away_team: str,
        days_back: int = 3,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for news about a specific match.

        Convenience method that searches for both teams combined.

        Args:
            home_team: Home team name
            away_team: Away team name
            days_back: How many days back to search
            max_results: Maximum number of articles

        Returns:
            List of news articles (same format as search_team_news)

        Raises:
            NewsAPIException: If API request fails
        """
        # Search for "Team A vs Team B" or "Team A Team B"
        query = f'"{home_team}" AND "{away_team}"'

        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager")

        to_date = datetime.now(UTC)
        from_date = to_date - timedelta(days=days_back)

        url = f"{self.BASE_URL}/everything"
        params: dict[str, str | int] = {
            "q": query,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(max_results, 100),
            "apiKey": self.api_key,
        }

        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                error_message = data.get("message", "Unknown error")
                raise NewsAPIException(f"NewsAPI error: {error_message}")

            articles = data.get("articles", [])

            return [
                {
                    "title": article["title"],
                    "description": article.get("description", ""),
                    "content": article.get("content", ""),
                    "url": article["url"],
                    "published_at": article["publishedAt"],
                    "source": article["source"]["name"],
                    "author": article.get("author"),
                }
                for article in articles
            ]

        except httpx.HTTPError as e:
            raise NewsAPIException(f"HTTP error fetching match news: {str(e)}") from e
        except Exception as e:
            raise NewsAPIException(f"Error fetching match news: {str(e)}") from e
