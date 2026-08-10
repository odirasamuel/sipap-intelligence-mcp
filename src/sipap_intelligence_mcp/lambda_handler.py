"""AWS Lambda handler for SIPAP Intelligence MCP.

Provides Lambda entry point for JSON-RPC 2.0 MCP requests.
Handles environment configuration for weather APIs and Bedrock AI services.
"""

import asyncio
import json
import logging
import os
from typing import Any

import boto3

from sipap_intelligence_mcp.server import IntelligenceMCPServer

# Configure structured logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set log level from environment variable (default: INFO)
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

# Initialize logger for this module
logger = logging.getLogger(__name__)

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
        logger.warning(f"Failed to load API keys from Secrets Manager: {e}", exc_info=True)


def get_server() -> IntelligenceMCPServer:
    """Get or create MCP server instance.

    Reuses server instance across Lambda invocations for warm starts.

    Returns:
        Initialized IntelligenceMCPServer
    """
    global _server

    if _server is None:
        logger.info("Cold start: Creating new Intelligence MCP server")

        # Load API keys from Secrets Manager (once per cold start)
        _load_api_keys_from_secrets()

        # Get configuration from environment variables (AWS Lambda environment)
        # Redis for caching weather/news data
        redis_endpoint = os.environ.get("REDIS_ENDPOINT", "localhost:6379")
        redis_ssl = os.environ.get("REDIS_SSL", "false").lower() == "true"
        redis_protocol = "rediss" if redis_ssl else "redis"
        redis_url = f"{redis_protocol}://{redis_endpoint}/0"

        logger.info(f"Connecting to Redis: {redis_url}")

        # Store config in environment for tool functions to access
        os.environ["REDIS_URL"] = redis_url

        # Create server instance
        _server = IntelligenceMCPServer()
        logger.info("Intelligence MCP server initialized")
    else:
        logger.info("Warm start: Reusing existing Intelligence MCP server")

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
    logger.info(f"Lambda invocation started (request_id: {context.aws_request_id})")

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

    # Log the JSON-RPC request
    logger.info(
        "Received JSON-RPC request",
        extra={
            "method": request.get("method"),
            "id": request.get("id"),
            "params_name": request.get("params", {}).get("name") if isinstance(request.get("params"), dict) else None
        }
    )
    logger.debug(f"Full request: {json.dumps(request, indent=2)}")

    # Handle JSON-RPC request (async)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response = loop.run_until_complete(server.handle_request(request))
        logger.debug(f"Full response: {json.dumps(response, indent=2)}")
    except Exception as e:
        logger.error(f"Error handling request: {e}", exc_info=True)
        raise
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
