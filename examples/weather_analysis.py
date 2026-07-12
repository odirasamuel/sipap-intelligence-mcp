"""Example: Weather Analysis for Match.

Demonstrates:
1. Fetching weather forecast for match venue
2. AI-powered impact assessment using Claude
3. Historical weather performance analysis
"""

import asyncio
from sipap_intelligence_mcp.tools.weather import (
    get_match_weather,
    assess_weather_impact,
    get_historical_weather_performance
)


async def main():
    """Run weather analysis example."""
    print("=" * 80)
    print("SIPAP Intelligence MCP - Weather Analysis Example")
    print("=" * 80)

    # Example 1: Get weather forecast for match in London
    print("\n1. Fetching weather for match in London...")
    weather = await get_match_weather(
        match_id="match-arsenal-chelsea-20240712",
        city="London",
        lat=51.5085,
        lon=-0.1257
    )
    print(f"   Temperature: {weather['temperature']}°C")
    print(f"   Precipitation: {weather['precipitation']}")
    print(f"   Wind Speed: {weather['wind_speed']} m/s")
    print(f"   Humidity: {weather['humidity']}%")

    # Example 2: Assess weather impact on match
    print("\n2. Assessing weather impact using Claude AI...")
    impact = await assess_weather_impact(
        weather_conditions=weather,
        match_type="soccer",
        home_team="Arsenal",
        away_team="Chelsea"
    )
    print(f"   Impact Level: {impact['impact_level']}")
    print(f"   Confidence: {impact['confidence']:.2f}")
    print(f"   Key Factors: {', '.join(impact['factors'])}")
    print(f"   Betting Implications: {impact['betting_implications']}")

    # Example 3: Historical weather performance
    print("\n3. Analyzing Arsenal's historical performance in rain...")
    historical = await get_historical_weather_performance(
        team_id="arsenal",
        team_name="Arsenal",
        weather_type="rain"
    )
    print(f"   Pattern Strength: {historical['pattern_strength']}")
    print(f"   Win Rate: {historical['win_rate']}%")
    print(f"   Avg Goals Scored: {historical['avg_goals_scored']}")
    print(f"   Key Insight: {historical['key_insight']}")

    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
