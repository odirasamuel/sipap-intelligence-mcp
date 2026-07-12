"""Example: MCP Client Usage.

Demonstrates full MCP protocol usage (JSON-RPC 2.0) for all tools.
"""

import asyncio
import json
from sipap_intelligence_mcp.server import IntelligenceMCPServer


async def main():
    """Run MCP client example."""
    print("=" * 80)
    print("SIPAP Intelligence MCP - Full Protocol Example")
    print("=" * 80)

    server = IntelligenceMCPServer()

    # Example 1: List available tools
    print("\n1. Listing available tools...")
    list_request = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/list'
    }
    list_response = await server.handle_request(list_request)
    print(f"   Available tools: {len(list_response['result']['tools'])}")
    for tool in list_response['result']['tools']:
        print(f"   - {tool['name']}: {tool['description']}")

    # Example 2: Call get_match_weather tool
    print("\n2. Calling get_match_weather tool...")
    weather_request = {
        'jsonrpc': '2.0',
        'id': 2,
        'method': 'tools/call',
        'params': {
            'name': 'get_match_weather',
            'arguments': {
                'match_id': 'match-123',
                'city': 'London'
            }
        }
    }
    weather_response = await server.handle_request(weather_request)
    weather_data = json.loads(weather_response['result']['content'][0]['text'])
    print(f"   Temperature: {weather_data.get('temperature', 'N/A')}°C")
    print(f"   Precipitation: {weather_data.get('precipitation', 'N/A')}")

    # Example 3: Call assess_weather_impact tool
    print("\n3. Calling assess_weather_impact tool...")
    impact_request = {
        'jsonrpc': '2.0',
        'id': 3,
        'method': 'tools/call',
        'params': {
            'name': 'assess_weather_impact',
            'arguments': {
                'weather_conditions': weather_data,
                'match_type': 'soccer',
                'home_team': 'Arsenal',
                'away_team': 'Chelsea'
            }
        }
    }
    impact_response = await server.handle_request(impact_request)
    impact_data = json.loads(impact_response['result']['content'][0]['text'])
    print(f"   Impact Level: {impact_data.get('impact_level', 'N/A')}")
    print(f"   Confidence: {impact_data.get('confidence', 0):.2f}")

    # Example 4: Call analyze_team_news tool
    print("\n4. Calling analyze_team_news tool...")
    news_request = {
        'jsonrpc': '2.0',
        'id': 4,
        'method': 'tools/call',
        'params': {
            'name': 'analyze_team_news',
            'arguments': {
                'team_id': 'arsenal',
                'team_name': 'Arsenal',
                'news_text': 'Arsenal wins 3-0 in dominant performance'
            }
        }
    }
    news_response = await server.handle_request(news_request)
    news_data = json.loads(news_response['result']['content'][0]['text'])
    print(f"   Sentiment: {news_data.get('sentiment', 'N/A')}")
    print(f"   Confidence: {news_data.get('confidence', 0):.2f}")

    print("\n" + "=" * 80)
    print("All MCP protocol examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
