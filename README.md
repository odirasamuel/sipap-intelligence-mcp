# sipap-intelligence-mcp

AI-Powered Intelligence MCP Server for SIPAP - News sentiment analysis, injury impact assessment, and weather intelligence using Claude (Bedrock) and OpenWeatherMap.

## Overview

This MCP server provides AI-powered intelligence tools that enhance sports predictions with:
- **News Sentiment Analysis**: Claude-powered analysis of recent news for teams
- **Injury Impact Assessment**: AI-driven evaluation of injury impact on performance
- **Weather Intelligence**: Real-time weather forecasts and AI-assessed impact on matches
- **Historical Weather Performance**: Team performance patterns in specific weather conditions

## Architecture

Unlike `sipap-data-mcp` (database reads only), this MCP server:
- Makes on-demand API calls (OpenWeatherMap, NewsAPI)
- Uses Claude via AWS Bedrock for AI analysis
- Has higher latency (<2s vs <100ms) due to AI processing
- Implements aggressive caching (6h-24h TTL) to minimize API costs

## Tools

### Weather Tools (3 tools)

1. **`get_match_weather(match_id: str)`**
   - Fetches weather forecast for match time and location
   - Source: OpenWeatherMap API
   - Returns: Temperature, precipitation, wind, visibility
   - Cache TTL: 1 hour

2. **`assess_weather_impact(weather_conditions: dict, match_type: str)`**
   - AI analysis of weather impact on match outcome
   - Uses: Claude via Bedrock
   - Returns: Impact level, factors, betting implications
   - Cache TTL: 6 hours

3. **`get_historical_weather_performance(team_id: str, weather_type: str)`**
   - Analyzes team's historical performance in specific weather
   - Uses: Aurora database + Claude analysis
   - Returns: Performance insights, statistical patterns
   - Cache TTL: 24 hours

### News Tools (2 tools)

4. **`analyze_team_news(team_id: str, days_back: int)`**
   - Sentiment analysis of recent news headlines
   - Uses: NewsAPI + Claude
   - Returns: Sentiment score, key topics, impact assessment
   - Cache TTL: 6 hours

5. **`get_injury_reports(team_id: str, severity_filter: str)`**
   - Injury reports with AI-powered impact assessment
   - Uses: Database + Claude
   - Returns: Injuries with AI-assessed impact scores
   - Cache TTL: 24 hours

## Installation

```bash
# Install from wheel
pip install sipap_intelligence_mcp-0.1.0-py3-none-any.whl

# Or install in editable mode for development
cd sipap-intelligence-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Requirements

- Python 3.12+
- AWS credentials with Bedrock access
- OpenWeatherMap API key (free tier: 60 calls/min)
- sipap-common >= 0.1.0
- sipap-serverlesshandler-mcp >= 0.1.0

## Usage

### Direct Tool Usage

```python
from sipap_intelligence_mcp.tools.weather import get_match_weather, assess_weather_impact

# Get weather forecast for match
weather = await get_match_weather(match_id="match-123")
# Returns: {
#     'temperature': 15.2,
#     'precipitation': 'light_rain',
#     'wind_speed': 12.5,
#     'visibility': 8000
# }

# Assess impact on match
impact = await assess_weather_impact(weather, match_type="soccer")
# Returns: {
#     'impact_level': 'medium',
#     'factors': ['Light rain favors defensive play', 'Wind affects long passes'],
#     'betting_implications': 'Consider under 2.5 goals',
#     'confidence': 0.78
# }
```

### MCP Protocol Usage (JSON-RPC 2.0)

```python
from sipap_intelligence_mcp.server import get_mcp_server

# Initialize MCP server
server = get_mcp_server()

# List available tools
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
}
response = await server.handle_request(request)
# Returns list of 5 tools

# Call a tool
request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "get_match_weather",
        "arguments": {
            "match_id": "match-123"
        }
    }
}
response = await server.handle_request(request)
```

## Configuration

### Environment Variables

```bash
# AWS Bedrock (required for AI analysis)
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0

# OpenWeatherMap API (required for weather)
OPENWEATHER_API_KEY=your_api_key_here

# NewsAPI (optional, for news sentiment)
NEWS_API_KEY=your_api_key_here

# Redis cache (required)
REDIS_ENDPOINT=sipap-dev-cache.cache.amazonaws.com:6379

# Database (required for historical analysis)
DB_ENDPOINT=sipap-dev-aurora.cluster-xxx.us-east-1.rds.amazonaws.com
DB_NAME=sipap_dev
DB_USER=sipap_admin
DB_PASSWORD=stored_in_secrets_manager
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/sipap_intelligence_mcp --cov-report=html

# Run type checking
mypy src/sipap_intelligence_mcp --strict

# Run linting
ruff check src/ tests/

# Run all quality gates
pytest && mypy src/sipap_intelligence_mcp --strict && ruff check src/ tests/
```

## Performance

- **Latency**: <2s average (AI processing overhead)
- **Cache Hit Rate**: 85%+ target (weather/news change infrequently)
- **Cost**: ~$10/month (Claude analysis + API calls)
- **Rate Limits**:
  - OpenWeatherMap: 60 calls/min (free tier)
  - NewsAPI: 100 requests/day (free tier)
  - Claude/Bedrock: Pay-as-you-go (~$0.01 per analysis)

## Architecture Patterns

### Sentinel Pattern Adoption

- **Pattern #9**: Structured output enforcement (JSON Schema for AI responses)
- **Pattern #19**: Lambda warm start optimization (global variables for API clients)
- **Pattern #20**: Cache-aside with TTL strategy (6h-24h based on volatility)

### AI Integration

- **Claude Haiku**: Fast, cost-effective for simple analyses (<$0.003 per call)
- **Claude Sonnet**: Complex reasoning for injury impact (<$0.015 per call)
- **Prompt Engineering**: Sport-specific prompts optimized for accuracy
- **Structured Output**: Force JSON schema to eliminate parsing errors

## Examples

See `examples/` directory for:
1. `weather_analysis.py` - Weather forecast + impact assessment
2. `news_sentiment.py` - News sentiment analysis for teams
3. `injury_impact.py` - Injury report with AI assessment
4. `mcp_client.py` - Full MCP protocol usage example

## Development

```bash
# Setup development environment
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Run quality gates before committing
pytest && mypy src/sipap_intelligence_mcp --strict && ruff check src/ tests/
```

## License

MIT License - See LICENSE file for details

## Support

For issues or questions: charles@sipap.com
