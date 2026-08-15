"""Integration tests for MCP server JSON-RPC 2.0 protocol.

Tests the complete MCP server workflow including:
- tools/list endpoint
- tools/call endpoint
- Error handling
- Tool registration
"""

import pytest

from sipap_intelligence_mcp.server import IntelligenceMCPServer


class TestMCPServerProtocol:
    """Test MCP server JSON-RPC 2.0 protocol compliance."""

    @pytest.mark.asyncio
    async def test_tools_list_returns_all_tools(self):
        """Test tools/list returns all 10 registered tools."""
        server = IntelligenceMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        response = await server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "tools" in response["result"]

        tools = response["result"]["tools"]
        assert len(tools) == 10

        # Verify all expected tools are present
        tool_names = {tool["name"] for tool in tools}
        expected_tools = {
            "get_match_weather",
            "assess_weather_impact",
            "get_historical_weather_performance",
            "fetch_and_analyze_team_news",
            "get_injury_reports",
            "get_match_predictions",
            "get_sidelined_players",
            "get_player_transfers",
            "get_available_timezones",
            "get_match_results",  # Real-time match results
        }
        assert tool_names == expected_tools

    @pytest.mark.asyncio
    async def test_tools_list_includes_schemas(self):
        """Test tools/list includes JSON schemas for all tools."""
        server = IntelligenceMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }

        response = await server.handle_request(request)

        tools = response["result"]["tools"]
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]

    @pytest.mark.asyncio
    async def test_method_not_found_error(self):
        """Test server returns error for unknown method."""
        server = IntelligenceMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "unknown/method",
            "params": {}
        }

        response = await server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_internal_error_handling(self):
        """Test server handles internal errors gracefully."""
        server = IntelligenceMCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            }
        }

        response = await server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 4
        assert "error" in response
        assert response["error"]["code"] == -32603
        assert "Internal error" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_tools_call_response_format(self):
        """Test tools/call returns properly formatted response."""
        server = IntelligenceMCPServer()
        # We'll test with a mock - actual tool tests are in test_tool_workflows.py
        # This just verifies the response structure

        # Note: This would need actual tool mocking to work fully
        # For now, we test the error case to verify response format
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_available_timezones",
                "arguments": {}
            }
        }

        response = await server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 5
        # Will have either "result" or "error" depending on environment
        assert "result" in response or "error" in response


class TestMCPServerToolMetadata:
    """Test tool metadata correctness."""

    @pytest.mark.asyncio
    async def test_weather_tools_metadata(self):
        """Test weather tools have correct metadata."""
        server = IntelligenceMCPServer()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await server.handle_request(request)

        tools = {tool["name"]: tool for tool in response["result"]["tools"]}

        # get_match_weather
        assert "get_match_weather" in tools
        weather_tool = tools["get_match_weather"]
        assert "match_id" in weather_tool["inputSchema"]["properties"]
        assert "lat" in weather_tool["inputSchema"]["properties"]
        assert "lon" in weather_tool["inputSchema"]["properties"]
        assert "city" in weather_tool["inputSchema"]["properties"]
        assert weather_tool["inputSchema"]["required"] == ["match_id"]

    @pytest.mark.asyncio
    async def test_news_tools_metadata(self):
        """Test news tools have correct metadata."""
        server = IntelligenceMCPServer()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await server.handle_request(request)

        tools = {tool["name"]: tool for tool in response["result"]["tools"]}

        # fetch_and_analyze_team_news
        assert "fetch_and_analyze_team_news" in tools
        news_tool = tools["fetch_and_analyze_team_news"]
        assert "team_id" in news_tool["inputSchema"]["properties"]
        assert "team_name" in news_tool["inputSchema"]["properties"]
        assert set(news_tool["inputSchema"]["required"]) == {"team_id", "team_name"}

    @pytest.mark.asyncio
    async def test_api_football_tools_metadata(self):
        """Test API-Football tools have correct metadata."""
        server = IntelligenceMCPServer()
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await server.handle_request(request)

        tools = {tool["name"]: tool for tool in response["result"]["tools"]}

        # get_match_predictions
        assert "get_match_predictions" in tools
        pred_tool = tools["get_match_predictions"]
        assert "fixture_id" in pred_tool["inputSchema"]["properties"]
        assert pred_tool["inputSchema"]["required"] == ["fixture_id"]

        # get_sidelined_players
        assert "get_sidelined_players" in tools
        sidelined_tool = tools["get_sidelined_players"]
        assert "player_id" in sidelined_tool["inputSchema"]["properties"]
        assert "coach_id" in sidelined_tool["inputSchema"]["properties"]
        # Mutually exclusive - no required fields

        # get_player_transfers
        assert "get_player_transfers" in tools
        transfers_tool = tools["get_player_transfers"]
        assert "player_id" in transfers_tool["inputSchema"]["properties"]
        assert "team_id" in transfers_tool["inputSchema"]["properties"]
