"""MCP Server for Intelligence Tools.

Implements JSON-RPC 2.0 protocol for AI-powered sports intelligence.
Exposes 9 tools via MCP protocol:

Weather Intelligence (3):
- get_match_weather: Weather forecast for match location (OpenWeatherMap)
- assess_weather_impact: AI-powered weather impact assessment (Claude)
- get_historical_weather_performance: Team performance in weather conditions (Claude)

News & Injury Intelligence (2):
- fetch_and_analyze_team_news: Fetch and analyze team news sentiment (NewsAPI + Claude)
- get_injury_reports: Injury reports with AI impact assessment (Claude)

API-Football Intelligence (4):
- get_match_predictions: AI predictions from API-Football algorithms
- get_sidelined_players: Player/coach availability status
- get_player_transfers: Transfer history and news
- get_available_timezones: Timezone data for accurate scheduling
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from sipap_intelligence_mcp.tools import api_football_intelligence, news, weather

# Tool registry mapping tool names to async functions
TOOL_REGISTRY: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
    # Weather intelligence tools
    "get_match_weather": weather.get_match_weather,
    "assess_weather_impact": weather.assess_weather_impact,
    "get_historical_weather_performance": weather.get_historical_weather_performance,
    # News & injury intelligence tools
    "fetch_and_analyze_team_news": news.fetch_and_analyze_team_news,
    "get_injury_reports": news.get_injury_reports,
    # API-Football intelligence tools
    "get_match_predictions": api_football_intelligence.get_match_predictions,
    "get_sidelined_players": api_football_intelligence.get_sidelined_players,
    "get_player_transfers": api_football_intelligence.get_player_transfers,
    "get_available_timezones": api_football_intelligence.get_available_timezones,
}


# Tool metadata for tools/list response
TOOL_METADATA = {
    "get_match_weather": {
        "name": "get_match_weather",
        "description": "Get weather forecast for match location using OpenWeatherMap API",
        "inputSchema": {
            "type": "object",
            "properties": {
                "match_id": {"type": "string", "description": "Match identifier for caching"},
                "lat": {"type": "number", "description": "Latitude of match venue"},
                "lon": {"type": "number", "description": "Longitude of match venue"},
                "city": {"type": "string", "description": "City name (alternative to lat/lon)"}
            },
            "required": ["match_id"]
        }
    },
    "assess_weather_impact": {
        "name": "assess_weather_impact",
        "description": "AI-powered assessment of weather impact on match outcome using Claude",
        "inputSchema": {
            "type": "object",
            "properties": {
                "weather_conditions": {"type": "object", "description": "Weather data from get_match_weather()"},
                "match_type": {"type": "string", "description": "Type of match (soccer, nba, nfl)", "default": "soccer"},
                "home_team": {"type": "string", "description": "Home team name"},
                "away_team": {"type": "string", "description": "Away team name"}
            },
            "required": ["weather_conditions"]
        }
    },
    "get_historical_weather_performance": {
        "name": "get_historical_weather_performance",
        "description": "Analyze team historical performance in specific weather conditions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Team identifier"},
                "team_name": {"type": "string", "description": "Team name"},
                "weather_type": {"type": "string", "description": "Weather type (rain, snow, wind, heat)"},
                "max_matches": {"type": "integer", "description": "Maximum historical matches", "default": 10}
            },
            "required": ["team_id", "team_name", "weather_type"]
        }
    },
    "fetch_and_analyze_team_news": {
        "name": "fetch_and_analyze_team_news",
        "description": "Fetch recent news via NewsAPI and analyze sentiment using Claude AI (full workflow)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Team identifier for caching"},
                "team_name": {"type": "string", "description": "Team name for news search"},
                "days_back": {"type": "integer", "description": "Days to search back (max 30)", "default": 7},
                "max_articles": {"type": "integer", "description": "Maximum articles to analyze", "default": 10}
            },
            "required": ["team_id", "team_name"]
        }
    },
    "get_injury_reports": {
        "name": "get_injury_reports",
        "description": "Get injury reports with AI-powered impact assessment using Claude",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "Team identifier"},
                "team_name": {"type": "string", "description": "Team name"},
                "severity_filter": {"type": "string", "description": "Severity filter (all, major, minor)", "default": "all"}
            },
            "required": ["team_id", "team_name"]
        }
    },
    "get_match_predictions": {
        "name": "get_match_predictions",
        "description": "Get AI predictions from API-Football algorithms (poisson, team stats, last matches)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fixture_id": {"type": "integer", "description": "API-Football fixture ID"}
            },
            "required": ["fixture_id"]
        }
    },
    "get_sidelined_players": {
        "name": "get_sidelined_players",
        "description": "Get sidelined (injured/suspended) players or coaches from API-Football",
        "inputSchema": {
            "type": "object",
            "properties": {
                "player_id": {"type": "integer", "description": "API-Football player ID (mutually exclusive with coach_id)"},
                "coach_id": {"type": "integer", "description": "API-Football coach ID (mutually exclusive with player_id)"}
            }
        }
    },
    "get_player_transfers": {
        "name": "get_player_transfers",
        "description": "Get transfer history for a player or team from API-Football",
        "inputSchema": {
            "type": "object",
            "properties": {
                "player_id": {"type": "integer", "description": "API-Football player ID (mutually exclusive with team_id)"},
                "team_id": {"type": "integer", "description": "API-Football team ID (mutually exclusive with player_id)"}
            }
        }
    },
    "get_available_timezones": {
        "name": "get_available_timezones",
        "description": "Get list of available timezones for accurate fixture scheduling and weather data",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
}


class IntelligenceMCPServer:
    """MCP Server for AI-powered sports intelligence.

    Implements JSON-RPC 2.0 protocol for tool invocation.
    """

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle JSON-RPC 2.0 request.

        Args:
            request: JSON-RPC request object

        Returns:
            JSON-RPC response object
        """
        method = request.get("method")
        request_id = request.get("id")

        try:
            if method == "tools/list":
                result = await self._list_tools()
            elif method == "tools/call":
                params = request.get("params", {})
                result = await self._call_tool(params)
            else:
                return self._error_response(request_id, -32601, f"Method not found: {method}")

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }

        except Exception as e:
            return self._error_response(request_id, -32603, f"Internal error: {str(e)}")

    async def _list_tools(self) -> dict[str, Any]:
        """List available tools.

        Returns:
            Tools list response
        """
        return {
            "tools": list(TOOL_METADATA.values())
        }

    async def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Call a tool by name.

        Args:
            params: Tool call parameters (name, arguments)

        Returns:
            Tool execution result
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_func = TOOL_REGISTRY[tool_name]
        result = await tool_func(**arguments)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }

    def _error_response(
        self,
        request_id: int | str | None,
        code: int,
        message: str
    ) -> dict[str, Any]:
        """Build JSON-RPC error response.

        Args:
            request_id: Request ID
            code: Error code
            message: Error message

        Returns:
            JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }


async def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler for MCP server.

    Implements Lambda warm start optimization (Sentinel Pattern #19).

    Args:
        event: Lambda event (JSON-RPC request)
        context: Lambda context

    Returns:
        Lambda response (JSON-RPC response)
    """
    server = IntelligenceMCPServer()

    # Handle JSON-RPC request
    request = event if isinstance(event, dict) else json.loads(event.get("body", "{}"))
    response = await server.handle_request(request)

    # Return Lambda response
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(response)
    }


# Module-level server instance for reuse across Lambda invocations
_server_instance: IntelligenceMCPServer | None = None


def get_mcp_server() -> IntelligenceMCPServer:
    """Get or create MCP server instance (Lambda warm start optimization).

    Returns:
        Cached MCP server instance
    """
    global _server_instance
    if _server_instance is None:
        _server_instance = IntelligenceMCPServer()
    return _server_instance
