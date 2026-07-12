"""Unit tests for Claude/Bedrock client.

Following TDD methodology:
1. RED: Write failing tests
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve implementation
"""

from unittest.mock import Mock, patch

import pytest

from sipap_intelligence_mcp.ai.claude import ClaudeBedrockClient, _clear_bedrock_cache
from sipap_intelligence_mcp.exceptions import ClaudeAPIException


@pytest.fixture
def claude_client():
    """Create Claude/Bedrock client for testing."""
    return ClaudeBedrockClient(region="us-east-1")


@pytest.fixture
def mock_bedrock_response():
    """Mock Bedrock invoke_model response."""
    return {
        "body": Mock(read=Mock(return_value=b"""{
            "content": [{
                "text": "{\\"sentiment\\": \\"positive\\", \\"confidence\\": 0.85, \\"key_topics\\": [\\"form\\", \\"morale\\"]}"
            }],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 50}
        }""")),
        "contentType": "application/json",
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }


class TestClaudeBedrockClient:
    """Test Claude/Bedrock client."""

    def test_client_initialization(self, claude_client):
        """Test client initializes with default model."""
        assert claude_client.region == "us-east-1"
        assert claude_client.model_id == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_client_initialization_custom_model(self):
        """Test client initializes with custom model."""
        client = ClaudeBedrockClient(
            region="us-west-2",
            model_id="anthropic.claude-3-sonnet-20240229-v1:0"
        )
        assert client.model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert client.region == "us-west-2"

    @pytest.mark.asyncio
    async def test_analyze_text_success(self, claude_client, mock_bedrock_response):
        """Test text analysis succeeds."""
        with patch("boto3.client") as mock_boto_client:
            mock_bedrock = Mock()
            mock_bedrock.invoke_model.return_value = mock_bedrock_response
            mock_boto_client.return_value = mock_bedrock

            # Clear cache and re-initialize client to use mock
            _clear_bedrock_cache()

            result = await claude_client.analyze_text(
                prompt="Analyze team news",
                system_prompt="You are a sports analyst",
                max_tokens=500
            )

            assert result["sentiment"] == "positive"
            assert result["confidence"] == 0.85
            assert "form" in result["key_topics"]

    @pytest.mark.asyncio
    async def test_analyze_text_with_schema_validation(self, claude_client):
        """Test text analysis with JSON schema validation."""
        schema = {
            "type": "object",
            "properties": {
                "sentiment": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["sentiment", "confidence"]
        }

        mock_response = {
            "body": Mock(read=Mock(return_value=b"""{
                "content": [{
                    "text": "{\\"sentiment\\": \\"negative\\", \\"confidence\\": 0.72}"
                }],
                "stop_reason": "end_turn"
            }""")),
            "contentType": "application/json"
        }

        with patch("boto3.client") as mock_boto_client:
            mock_bedrock = Mock()
            mock_bedrock.invoke_model.return_value = mock_response
            mock_boto_client.return_value = mock_bedrock

            _clear_bedrock_cache()

            result = await claude_client.analyze_text(
                prompt="Test prompt",
                response_schema=schema,
                max_tokens=300
            )

            assert result["sentiment"] == "negative"
            assert result["confidence"] == 0.72

    @pytest.mark.asyncio
    async def test_analyze_text_api_error(self, claude_client):
        """Test API error raises ClaudeAPIException."""
        with patch("boto3.client") as mock_boto_client:
            mock_bedrock = Mock()
            mock_bedrock.invoke_model.side_effect = Exception("Bedrock API error")
            mock_boto_client.return_value = mock_bedrock

            _clear_bedrock_cache()

            with pytest.raises(ClaudeAPIException, match="Bedrock API error"):
                await claude_client.analyze_text(prompt="Test")

    @pytest.mark.asyncio
    async def test_analyze_text_invalid_json_response(self, claude_client):
        """Test invalid JSON in response raises error."""
        mock_response = {
            "body": Mock(read=Mock(return_value=b"""{
                "content": [{"text": "This is not valid JSON at all"}],
                "stop_reason": "end_turn"
            }""")),
            "contentType": "application/json"
        }

        with patch("boto3.client") as mock_boto_client:
            mock_bedrock = Mock()
            mock_bedrock.invoke_model.return_value = mock_response
            mock_boto_client.return_value = mock_bedrock

            _clear_bedrock_cache()

            with pytest.raises(ClaudeAPIException, match="Failed to parse JSON"):
                await claude_client.analyze_text(prompt="Test")

    @pytest.mark.asyncio
    async def test_analyze_sentiment_success(self, claude_client):
        """Test sentiment analysis convenience method."""
        mock_response = {
            "body": Mock(read=Mock(return_value=b"""{
                "content": [{
                    "text": "{\\"sentiment\\": \\"positive\\", \\"confidence\\": 0.90, \\"reasoning\\": \\"Team is on winning streak\\"}"
                }],
                "stop_reason": "end_turn"
            }""")),
            "contentType": "application/json"
        }

        with patch("boto3.client") as mock_boto_client:
            mock_bedrock = Mock()
            mock_bedrock.invoke_model.return_value = mock_response
            mock_boto_client.return_value = mock_bedrock

            _clear_bedrock_cache()

            result = await claude_client.analyze_sentiment(
                text="Manchester United wins 3-0 against rivals"
            )

            assert result["sentiment"] == "positive"
            assert result["confidence"] == 0.90

    @pytest.mark.asyncio
    async def test_assess_impact_success(self, claude_client):
        """Test impact assessment convenience method."""
        mock_response = {
            "body": Mock(read=Mock(return_value=b"""{
                "content": [{
                    "text": "{\\"impact_level\\": \\"high\\", \\"confidence\\": 0.85, \\"factors\\": [\\"key_player_injured\\"]}"
                }],
                "stop_reason": "end_turn"
            }""")),
            "contentType": "application/json"
        }

        with patch("boto3.client") as mock_boto_client:
            mock_bedrock = Mock()
            mock_bedrock.invoke_model.return_value = mock_response
            mock_boto_client.return_value = mock_bedrock

            _clear_bedrock_cache()

            result = await claude_client.assess_impact(
                context="Star striker out for 3 months",
                assessment_type="injury"
            )

            assert result["impact_level"] == "high"
            assert result["confidence"] == 0.85

    def test_build_messages_correctly(self, claude_client):
        """Test _build_messages constructs correct format."""
        messages = claude_client._build_messages(
            prompt="Test prompt",
            context="Additional context"
        )

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "Test prompt" in messages[0]["content"]
        assert "Additional context" in messages[0]["content"]

    def test_build_messages_without_context(self, claude_client):
        """Test _build_messages with no context."""
        messages = claude_client._build_messages(prompt="Test only")

        assert len(messages) == 1
        assert messages[0]["content"] == "Test only"

    def test_extract_json_from_text_success(self, claude_client):
        """Test _extract_json_from_text parses correctly."""
        text = '{"key": "value", "number": 42}'
        result = claude_client._extract_json_from_text(text)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_extract_json_from_text_with_markdown(self, claude_client):
        """Test _extract_json_from_text strips markdown."""
        text = '```json\n{"key": "value"}\n```'
        result = claude_client._extract_json_from_text(text)

        assert result["key"] == "value"

    def test_extract_json_from_text_invalid(self, claude_client):
        """Test _extract_json_from_text raises on invalid JSON."""
        with pytest.raises(ClaudeAPIException, match="Failed to parse JSON"):
            claude_client._extract_json_from_text("Not JSON at all")
