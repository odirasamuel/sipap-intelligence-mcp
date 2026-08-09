# sipap-intelligence-mcp

AI-Powered Intelligence MCP Server for SIPAP - Aggregating intelligence from news sentiment, weather analysis, and API-Football predictions using Claude (Bedrock).

## Overview

This MCP server provides AI-powered intelligence tools that enhance sports predictions with:
- **Weather Intelligence**: Real-time weather forecasts and AI-assessed impact on matches
- **News Sentiment Analysis**: Claude-powered analysis of recent news for teams
- **Injury Impact Assessment**: AI-driven evaluation of injury impact on performance
- **API-Football Intelligence**: Algorithmic predictions, player availability, and transfers
- **Historical Performance Analysis**: Team performance patterns in specific conditions

## Architecture

Unlike `sipap-data-mcp` (database reads only), this MCP server:
- Makes on-demand API calls (OpenWeatherMap, NewsAPI, API-Football)
- Uses Claude via AWS Bedrock for AI analysis
- Has higher latency (<2s vs <100ms) due to AI processing + API calls
- Implements differential TTL caching strategy (1h-24h) to minimize API costs
- Follows Sentinel patterns: #19 (Lambda warm start), #20 (Cache-aside)

## Tools (9 Total)

### Weather Intelligence (3 tools)

1. **`get_match_weather(match_id: str, lat?: float, lon?: float, city?: str)`**
   - Fetches weather forecast for match time and location
   - Source: OpenWeatherMap API
   - Returns: Temperature, precipitation, wind, visibility, humidity
   - Cache TTL: 1 hour
   - Accepts: Coordinates (lat/lon) OR city name

2. **`assess_weather_impact(weather_conditions: dict, match_type?: str, home_team?: str, away_team?: str)`**
   - AI analysis of weather impact on match outcome
   - Uses: Claude via Bedrock
   - Returns: Impact level, confidence, factors, betting implications
   - Cache TTL: 6 hours
   - Optional team context for tactical analysis

3. **`get_historical_weather_performance(team_id: str, team_name: str, weather_type: str, max_matches?: int)`**
   - Analyzes team's historical performance in specific weather
   - Uses: Mock historical data + Claude analysis
   - Returns: Pattern strength, confidence, win rate, goal stats, insights
   - Cache TTL: 24 hours

### News Intelligence (2 tools)

4. **`fetch_and_analyze_team_news(team_id: str, team_name: str, days_back?: int)`**
   - Fetches recent news and performs sentiment analysis
   - Uses: NewsAPI + Claude
   - Returns: Sentiment, confidence, key topics, impact summary, articles analyzed
   - Cache TTL: 6 hours
   - Default: 7 days back, top 5 sources

5. **`get_injury_reports(team_id: str, team_name: str, severity_filter?: str)`**
   - Injury reports with AI-powered impact assessment
   - Uses: Mock injury data + Claude
   - Returns: Injuries with AI-assessed impact scores
   - Cache TTL: 24 hours
   - Filters: "all", "major", "minor"

### API-Football Intelligence (4 tools)

6. **`get_match_predictions(fixture_id: int)`**
   - Algorithmic match predictions from API-Football
   - Source: API-Football predictions endpoint (poisson, stats, form)
   - Returns: Winner prediction, probabilities (home/draw/away), league/teams info
   - Cache TTL: 6 hours

7. **`get_sidelined_players(player_id?: int, coach_id?: int)`**
   - Player/coach availability (injuries, suspensions, absences)
   - Source: API-Football sidelined endpoint
   - Returns: Type, player/coach info, start date, end date
   - Cache TTL: 24 hours
   - Mutually exclusive: provide player_id OR coach_id

8. **`get_player_transfers(player_id?: int, team_id?: int)`**
   - Player transfer history and context
   - Source: API-Football transfers endpoint
   - Returns: Transfer details, teams, dates, type
   - Cache TTL: 24 hours
   - Optional filters: player_id, team_id

9. **`get_available_timezones()`**
   - Available timezones for fixture scheduling
   - Source: API-Football timezones endpoint
   - Returns: List of valid timezone identifiers
   - Cache TTL: 7 days (static data)

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

- Python 3.12, 3.13, or 3.14
- AWS credentials with Bedrock access (Claude)
- OpenWeatherMap API key (free tier: 60 calls/min)
- NewsAPI key (free tier: 100 requests/day)
- API-Football key (Ultra plan: 75,000 requests/day)
- sipap-common >= 0.1.0
- sipap-mcp >= 0.1.0
- Redis instance (AWS ElastiCache or local)

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
from sipap_intelligence_mcp.server import IntelligenceMCPServer

# Initialize MCP server
server = IntelligenceMCPServer()

# List available tools
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
}
response = await server.handle_request(request)
# Returns list of 9 tools with JSON schemas

# Call a weather tool
request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "get_match_weather",
        "arguments": {
            "match_id": "match-123",
            "lat": 51.5,
            "lon": -0.1
        }
    }
}
response = await server.handle_request(request)

# Call an API-Football tool
request = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "get_match_predictions",
        "arguments": {
            "fixture_id": 198772
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

# OpenWeatherMap API (required for weather intelligence)
OPENWEATHER_API_KEY=your_api_key_here

# NewsAPI (required for news intelligence)
NEWS_API_KEY=your_api_key_here

# API-Football (required for predictions/transfers/sidelined)
API_FOOTBALL_KEY=your_api_key_here

# Redis cache (required for all tools)
REDIS_ENDPOINT=sipap-dev-cache.cache.amazonaws.com:6379

# Database (optional, for historical analysis)
DB_ENDPOINT=sipap-dev-aurora.cluster-xxx.us-east-1.rds.amazonaws.com
DB_NAME=sipap_dev
DB_USER=sipap_admin
DB_PASSWORD=stored_in_secrets_manager
```

## Testing

### Quality Gates Status

✅ **Tests**: 130/130 passing (72% coverage)
- Unit tests: 112 (weather: 17, news: 21, API-Football: 36, clients: 38)
- Integration tests: 18 (MCP server: 8, workflows: 10)

✅ **Type Checking**: Zero mypy errors (strict mode)

✅ **Linting**: Zero ruff errors

✅ **Imports**: All successful

### Coverage Breakdown

- Weather tools: 92% coverage
- News tools: 89% coverage
- API-Football tools: 95% coverage
- MCP server: 83% coverage
- Claude client: 99% coverage
- Prompts: 100% coverage

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/sipap_intelligence_mcp --cov-report=html

# Run specific test suites
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only

# Run type checking
mypy src/sipap_intelligence_mcp --strict

# Run linting
ruff check src/ tests/

# Run all quality gates
pytest && mypy src/sipap_intelligence_mcp --strict && ruff check src/ tests/
```

## Performance

- **Latency**: <2s average (AI processing + API calls overhead)
- **Cache Hit Rate**: 85%+ target (differential TTL strategy)
- **Cost**: ~$15/month (Claude analysis + API calls)
- **Rate Limits**:
  - OpenWeatherMap: 60 calls/min (free tier)
  - NewsAPI: 100 requests/day (free tier)
  - API-Football: 75,000 requests/day (Ultra plan)
  - Claude/Bedrock: Pay-as-you-go (~$0.01 per analysis)
- **Caching Strategy**:
  - Weather: 1 hour (volatile)
  - Weather impact: 6 hours (semi-stable)
  - Historical performance: 24 hours (stable)
  - News sentiment: 6 hours (semi-stable)
  - Injury reports: 24 hours (stable)
  - Predictions: 6 hours (semi-stable)
  - Sidelined/Transfers: 24 hours (stable)
  - Timezones: 7 days (static)

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
1. `weather_intelligence.py` - Weather forecast + impact assessment + historical performance
2. `news_intelligence.py` - News sentiment analysis + injury reports
3. `api_football_intelligence.py` - Match predictions + sidelined players + transfers
4. `mcp_client.py` - Full MCP protocol usage with all 9 tools
5. `README.md` - Setup instructions and usage guide

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
