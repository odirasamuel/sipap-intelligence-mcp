"""Unit tests for prompt templates.

Testing prompt generation logic and structure.
"""

from sipap_intelligence_mcp.ai.prompts import PromptTemplates


class TestPromptTemplates:
    """Test prompt template generation."""

    def test_news_sentiment_prompt_with_team(self):
        """Test news sentiment prompt includes team name."""
        prompt = PromptTemplates.news_sentiment_prompt(
            news_text="Team wins 3-0",
            team_name="Manchester United"
        )

        assert "Manchester United" in prompt
        assert "Team wins 3-0" in prompt
        assert "sentiment" in prompt.lower()
        assert "confidence" in prompt.lower()

    def test_news_sentiment_prompt_without_team(self):
        """Test news sentiment prompt works without team name."""
        prompt = PromptTemplates.news_sentiment_prompt(
            news_text="Great performance today"
        )

        assert "Great performance today" in prompt
        assert "sentiment" in prompt.lower()

    def test_news_sentiment_system_prompt(self):
        """Test news sentiment system prompt."""
        system = PromptTemplates.news_sentiment_system_prompt()

        assert "sports analyst" in system.lower()
        assert "sentiment" in system.lower()

    def test_injury_impact_prompt(self):
        """Test injury impact prompt includes details."""
        prompt = PromptTemplates.injury_impact_prompt(
            injury_details="Star striker out 3 months with ACL tear",
            team_name="Arsenal"
        )

        assert "Arsenal" in prompt
        assert "Star striker out 3 months" in prompt
        assert "impact_level" in prompt
        assert "recommendation" in prompt

    def test_injury_impact_system_prompt(self):
        """Test injury impact system prompt."""
        system = PromptTemplates.injury_impact_system_prompt()

        assert "injury" in system.lower()
        assert "analyst" in system.lower()

    def test_weather_impact_prompt(self):
        """Test weather impact prompt formats conditions."""
        conditions = {
            "temperature": 15.2,
            "precipitation": "light_rain",
            "wind_speed": 12.5,
            "visibility": 8000,
            "humidity": 82
        }

        prompt = PromptTemplates.weather_impact_prompt(
            weather_conditions=conditions,
            match_type="soccer"
        )

        assert "15.2" in prompt
        assert "light_rain" in prompt
        assert "12.5" in prompt
        assert "soccer" in prompt
        assert "betting_implications" in prompt

    def test_weather_impact_system_prompt(self):
        """Test weather impact system prompt."""
        system = PromptTemplates.weather_impact_system_prompt()

        assert "weather" in system.lower()
        assert "analyst" in system.lower()

    def test_historical_weather_performance_prompt(self):
        """Test historical weather performance prompt."""
        historical_data = [
            {"date": "2024-01-15", "result": "W", "score": "2-1", "opponent": "Chelsea"},
            {"date": "2024-01-08", "result": "L", "score": "0-2", "opponent": "Liverpool"},
            {"date": "2024-01-01", "result": "D", "score": "1-1", "opponent": "Spurs"}
        ]

        prompt = PromptTemplates.historical_weather_performance_prompt(
            team_name="Manchester City",
            weather_type="rain",
            historical_data=historical_data
        )

        assert "Manchester City" in prompt
        assert "rain" in prompt
        assert "Chelsea" in prompt
        assert "win_rate" in prompt
        assert "avg_goals_scored" in prompt

    def test_historical_weather_performance_system_prompt(self):
        """Test historical weather performance system prompt."""
        system = PromptTemplates.historical_weather_performance_system_prompt()

        assert "statistician" in system.lower()
        assert "pattern" in system.lower()

    def test_get_response_schema_sentiment(self):
        """Test sentiment analysis schema."""
        schema = PromptTemplates.get_response_schema("sentiment")

        assert schema["type"] == "object"
        assert "sentiment" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert "sentiment" in schema["required"]

    def test_get_response_schema_injury(self):
        """Test injury assessment schema."""
        schema = PromptTemplates.get_response_schema("injury")

        assert schema["type"] == "object"
        assert "impact_level" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert "factors" in schema["properties"]

    def test_get_response_schema_weather(self):
        """Test weather impact schema."""
        schema = PromptTemplates.get_response_schema("weather")

        assert schema["type"] == "object"
        assert "impact_level" in schema["properties"]
        assert "betting_implications" in schema["properties"]

    def test_get_response_schema_historical(self):
        """Test historical analysis schema."""
        schema = PromptTemplates.get_response_schema("historical")

        assert schema["type"] == "object"
        assert "pattern_strength" in schema["properties"]
        assert "win_rate" in schema["properties"]
        assert "avg_goals_scored" in schema["properties"]

    def test_get_response_schema_unknown(self):
        """Test unknown analysis type returns generic schema."""
        schema = PromptTemplates.get_response_schema("unknown")

        assert schema["type"] == "object"
        assert len(schema.get("properties", {})) == 0
