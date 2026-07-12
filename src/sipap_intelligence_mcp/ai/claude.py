"""Claude/Bedrock client for AI-powered analysis.

Provides sentiment analysis, impact assessment, and other AI-powered intelligence
using Claude models via AWS Bedrock.
"""

import json
import re
from typing import Any

import boto3

from sipap_intelligence_mcp.exceptions import ClaudeAPIException

# Global Bedrock client cache for Lambda warm start optimization
_bedrock_clients: dict[tuple[str, str], Any] = {}


def _clear_bedrock_cache() -> None:
    """Clear the Bedrock client cache (for testing purposes only)."""
    _bedrock_clients.clear()


class ClaudeBedrockClient:
    """Client for Claude AI via AWS Bedrock.

    Uses Claude models (Haiku/Sonnet) for:
    - News sentiment analysis
    - Injury impact assessment
    - Weather impact analysis
    - Historical performance insights

    Attributes:
        region: AWS region for Bedrock (default: us-east-1)
        model_id: Claude model ID (default: Haiku)

    Example:
        >>> client = ClaudeBedrockClient()
        >>> result = await client.analyze_sentiment("Team wins 3-0")
        >>> result['sentiment']
        'positive'
    """

    def __init__(
        self,
        region: str = "us-east-1",
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    ):
        """Initialize Claude/Bedrock client.

        Args:
            region: AWS region for Bedrock
            model_id: Claude model ID (Haiku or Sonnet)
        """
        self.region = region
        self.model_id = model_id

    def _get_bedrock_client(self) -> Any:
        """Get cached Bedrock client (Lambda warm start optimization).

        Returns:
            boto3 Bedrock Runtime client
        """
        cache_key = (self.region, self.model_id)
        if cache_key not in _bedrock_clients:
            _bedrock_clients[cache_key] = boto3.client("bedrock-runtime", region_name=self.region)
        return _bedrock_clients[cache_key]

    async def analyze_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        context: str | None = None,
        response_schema: dict[str, Any] | None = None,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> dict[str, Any]:
        """Analyze text using Claude with structured output.

        Args:
            prompt: Main analysis prompt
            system_prompt: System instructions for Claude
            context: Additional context for analysis
            response_schema: JSON schema for structured output (optional)
            max_tokens: Maximum response tokens
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Parsed JSON response from Claude

        Raises:
            ClaudeAPIException: If API call fails or response invalid
        """
        try:
            bedrock = self._get_bedrock_client()

            # Build request
            messages = self._build_messages(prompt, context)

            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }

            # Add system prompt if provided
            if system_prompt:
                request_body["system"] = system_prompt

            # Invoke Claude via Bedrock
            response = bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            text_content = response_body["content"][0]["text"]

            # Extract and validate JSON from response
            result = self._extract_json_from_text(text_content)

            # Validate against schema if provided
            if response_schema:
                self._validate_schema(result, response_schema)

            return result

        except ClaudeAPIException:
            raise
        except Exception as e:
            raise ClaudeAPIException(f"Bedrock API error: {str(e)}") from e

    async def analyze_sentiment(
        self,
        text: str,
        entity: str | None = None
    ) -> dict[str, Any]:
        """Analyze sentiment of text (convenience method).

        Args:
            text: Text to analyze (news headline, article, etc.)
            entity: Optional entity to focus on (team name, player)

        Returns:
            Sentiment analysis with:
                - sentiment: positive, negative, neutral
                - confidence: 0.0-1.0
                - reasoning: Explanation of sentiment
        """
        entity_context = f" regarding {entity}" if entity else ""
        prompt = f"""Analyze the sentiment of this sports news{entity_context}:

Text: {text}

Return JSON with:
- sentiment: "positive", "negative", or "neutral"
- confidence: number between 0 and 1
- reasoning: brief explanation
"""

        schema = {
            "type": "object",
            "properties": {
                "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning": {"type": "string"}
            },
            "required": ["sentiment", "confidence"]
        }

        system_prompt = "You are an expert sports analyst specializing in sentiment analysis."

        return await self.analyze_text(
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=schema,
            max_tokens=300,
            temperature=0.5
        )

    async def assess_impact(
        self,
        context: str,
        assessment_type: str = "general"
    ) -> dict[str, Any]:
        """Assess impact of event/condition (convenience method).

        Args:
            context: Context to assess (injury, weather, news)
            assessment_type: Type of assessment (injury, weather, news, general)

        Returns:
            Impact assessment with:
                - impact_level: low, medium, high
                - confidence: 0.0-1.0
                - factors: List of contributing factors
                - recommendation: Betting implications
        """
        prompt = f"""Assess the impact of this {assessment_type} on match outcome:

Context: {context}

Return JSON with:
- impact_level: "low", "medium", or "high"
- confidence: number between 0 and 1
- factors: array of key factors (strings)
- recommendation: brief betting implication
"""

        schema = {
            "type": "object",
            "properties": {
                "impact_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "factors": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"}
            },
            "required": ["impact_level", "confidence"]
        }

        system_prompt = f"You are an expert sports analyst specializing in {assessment_type} impact assessment."

        return await self.analyze_text(
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=schema,
            max_tokens=400,
            temperature=0.6
        )

    def _build_messages(
        self,
        prompt: str,
        context: str | None = None
    ) -> list[dict[str, str]]:
        """Build messages array for Claude API.

        Args:
            prompt: Main prompt
            context: Optional additional context

        Returns:
            Messages array in Claude format
        """
        if context:
            combined = f"{context}\n\n{prompt}"
        else:
            combined = prompt

        return [
            {
                "role": "user",
                "content": combined
            }
        ]

    def _extract_json_from_text(self, text: str) -> dict[str, Any]:
        """Extract JSON from Claude response text.

        Claude sometimes wraps JSON in markdown code blocks.
        This method extracts and parses the JSON.

        Args:
            text: Response text from Claude

        Returns:
            Parsed JSON object

        Raises:
            ClaudeAPIException: If JSON parsing fails
        """
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```"):
            # Extract content between ``` markers
            match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        try:
            result: dict[str, Any] = json.loads(text)
            return result
        except json.JSONDecodeError as e:
            raise ClaudeAPIException(f"Failed to parse JSON from Claude response: {str(e)}") from e

    def _validate_schema(self, data: dict[str, Any], schema: dict[str, Any]) -> None:
        """Basic schema validation for required fields.

        Args:
            data: Data to validate
            schema: JSON schema

        Raises:
            ClaudeAPIException: If validation fails
        """
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                raise ClaudeAPIException(
                    f"Missing required field '{field}' in Claude response"
                )
