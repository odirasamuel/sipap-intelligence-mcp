"""Example: News Sentiment Analysis.

Demonstrates AI-powered sentiment analysis of team news using Claude.
"""

import asyncio
from sipap_intelligence_mcp.tools.news import analyze_team_news


async def main():
    """Run news sentiment analysis example."""
    print("=" * 80)
    print("SIPAP Intelligence MCP - News Sentiment Analysis Example")
    print("=" * 80)

    # Example news text (recent headlines)
    news_text = """
    Manchester United wins 3-0 in dominant performance against rivals.
    Team morale at all-time high after impressive winning streak.
    Manager praises squad depth and tactical improvements.
    Fans celebrate return to top form after difficult season start.
    """

    print("\nNews Text to Analyze:")
    print("-" * 80)
    print(news_text.strip())
    print("-" * 80)

    # Analyze sentiment
    print("\nAnalyzing sentiment using Claude AI...")
    result = await analyze_team_news(
        team_id="man-utd",
        team_name="Manchester United",
        news_text=news_text,
        days_back=7
    )

    print(f"\nSentiment Analysis Results:")
    print(f"  Sentiment: {result['sentiment']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Key Topics: {', '.join(result['key_topics'])}")
    print(f"  Impact Summary: {result['impact_summary']}")

    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
