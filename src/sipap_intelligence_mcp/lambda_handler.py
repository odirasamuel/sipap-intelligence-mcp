"""AWS Lambda handler for SIPAP Intelligence MCP.

Provides Lambda entry point for JSON-RPC 2.0 MCP requests.
Handles environment configuration for weather APIs and Bedrock AI services.
"""

import asyncio
import json
import os
from typing import Any

import boto3

from sipap_intelligence_mcp.server import IntelligenceMCPServer

# Initialize server (singleton for Lambda container reuse)
_server: IntelligenceMCPServer | None = None


def _load_api_keys_from_secrets() -> None:
    """Load API keys from AWS Secrets Manager and inject into environment.

    Reads API_KEYS_SECRET_ARN from environment and fetches:
    - API_FOOTBALL_KEY
    - OPENWEATHER_API_KEY
    - NEWS_API_KEY

    Sets them as environment variables for tools to access.
    """
    secret_arn = os.environ.get("API_KEYS_SECRET_ARN")
    if not secret_arn:
        # No secret ARN configured - skip (useful for local testing)
        return

    # Fetch secret from Secrets Manager
    sm_client = boto3.client("secretsmanager", region_name="us-east-1")
    try:
        response = sm_client.get_secret_value(SecretId=secret_arn)
        secret_data = json.loads(response["SecretString"])

        # Inject API keys into environment for tools to access
        if "API_FOOTBALL_KEY" in secret_data:
            os.environ["API_FOOTBALL_KEY"] = secret_data["API_FOOTBALL_KEY"]

        if "OPENWEATHER_API_KEY" in secret_data:
            os.environ["OPENWEATHER_API_KEY"] = secret_data["OPENWEATHER_API_KEY"]

        if "NEWS_API_KEY" in secret_data:
            os.environ["NEWS_API_KEY"] = secret_data["NEWS_API_KEY"]

    except Exception as e:
        # Log error but don't fail - tools will handle missing keys gracefully
        print(f"Warning: Failed to load API keys from Secrets Manager: {e}")


def get_server() -> IntelligenceMCPServer:
    """Get or create MCP server instance.

    Reuses server instance across Lambda invocations for warm starts.

    Returns:
        Initialized IntelligenceMCPServer
    """
    global _server

    if _server is None:
        # Load API keys from Secrets Manager (once per cold start)
        _load_api_keys_from_secrets()

        # Get configuration from environment variables (AWS Lambda environment)
        # Redis for caching weather/news data
        redis_endpoint = os.environ.get("REDIS_ENDPOINT", "localhost:6379")
        redis_ssl = os.environ.get("REDIS_SSL", "false").lower() == "true"
        redis_protocol = "rediss" if redis_ssl else "redis"
        redis_url = f"{redis_protocol}://{redis_endpoint}/0"

        # Store config in environment for tool functions to access
        os.environ["REDIS_URL"] = redis_url

        # Create server instance
        _server = IntelligenceMCPServer()

    return _server


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler for Intelligence MCP.

    Implements Lambda warm start optimization (Sentinel Pattern #19).

    Args:
        event: Lambda event (JSON-RPC request or API Gateway proxy event)
        context: Lambda context

    Returns:
        Lambda response (JSON-RPC response or API Gateway proxy response)
    """
    # Get or create server instance
    server = get_server()

    # Parse request (handle both direct Lambda invocation and API Gateway proxy)
    if "body" in event:
        # API Gateway proxy format
        try:
            request = json.loads(event["body"])
        except (json.JSONDecodeError, KeyError):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Invalid JSON"
                    }
                })
            }
    else:
        # Direct Lambda invocation format
        request = event

    # Handle JSON-RPC request (async)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response = loop.run_until_complete(server.handle_request(request))
    finally:
        loop.close()

    # Return Lambda response
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(response)
    }
