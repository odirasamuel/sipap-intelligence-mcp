# SIPAP Intelligence MCP Examples

Comprehensive examples demonstrating all 5 AI-powered intelligence tools.

## Setup

```bash
# Install package
cd sipap-intelligence-mcp
pip install -e .

# Set environment variables
export OPENWEATHER_API_KEY="your_openweather_api_key"
export AWS_REGION="us-east-1"
# Configure AWS credentials for Bedrock access
```

## Examples

1. **weather_analysis.py** - Weather forecast + AI impact assessment
2. **news_sentiment.py** - Team news sentiment analysis
3. **injury_impact.py** - Injury reports with AI assessment
4. **mcp_client.py** - Full MCP protocol usage (JSON-RPC 2.0)

## Running Examples

```bash
# Weather analysis
python examples/weather_analysis.py

# News sentiment
python examples/news_sentiment.py

# Injury impact
python examples/injury_impact.py

# MCP client
python examples/mcp_client.py
```

## Notes

- Examples use real API calls (OpenWeatherMap, Claude/Bedrock)
- Requires valid API keys and AWS credentials
- Some examples may incur small costs (~$0.01 per Claude analysis)
