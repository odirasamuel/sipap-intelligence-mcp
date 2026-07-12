"""Example: Injury Impact Assessment.

Demonstrates getting injury reports with AI-powered impact analysis.
"""

import asyncio
from sipap_intelligence_mcp.tools.news import get_injury_reports


async def main():
    """Run injury impact assessment example."""
    print("=" * 80)
    print("SIPAP Intelligence MCP - Injury Impact Assessment Example")
    print("=" * 80)

    # Get injury reports for Chelsea
    print("\nFetching injury reports for Chelsea...")
    result = await get_injury_reports(
        team_id="chelsea",
        team_name="Chelsea",
        severity_filter="all"
    )

    # Display injuries
    print(f"\nCurrent Injuries ({len(result['injuries'])} total):")
    print("-" * 80)
    for injury in result['injuries']:
        print(f"  • {injury['player']} ({injury['position']})")
        print(f"    Injury: {injury['injury_type']}")
        print(f"    Severity: {injury['severity']}")
        print(f"    Timeline: {injury['timeline']}")
        print()

    # Display AI impact assessment
    impact = result['overall_impact']
    print("AI Impact Assessment (Claude Analysis):")
    print("-" * 80)
    print(f"  Impact Level: {impact['impact_level']}")
    print(f"  Confidence: {impact['confidence']:.2f}")
    print(f"  Key Factors: {', '.join(impact['factors'])}")
    print(f"  Recommendation: {impact['recommendation']}")

    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
