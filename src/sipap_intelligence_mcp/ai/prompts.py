"""Prompt templates for AI-powered sports intelligence analysis.

Sport-specific prompts optimized for accuracy and structured output.
"""

from typing import Any


class PromptTemplates:
    """Collection of prompt templates for Claude analysis."""

    @staticmethod
    def news_sentiment_prompt(news_text: str, team_name: str | None = None) -> str:
        """Generate prompt for news sentiment analysis.

        Args:
            news_text: News article or headlines to analyze
            team_name: Optional team to focus analysis on

        Returns:
            Formatted prompt for Claude
        """
        team_context = f" for {team_name}" if team_name else ""

        return f"""Analyze the sentiment of this sports news{team_context}:

{news_text}

Consider:
- Team morale and confidence indicators
- Performance trends mentioned
- Injury or lineup news
- Management/coaching changes
- Fan sentiment

Return JSON with:
- sentiment: "positive", "negative", or "neutral"
- confidence: number 0-1 (how certain you are)
- key_topics: array of main topics discussed
- impact_summary: brief explanation of potential match impact
"""

    @staticmethod
    def news_sentiment_system_prompt() -> str:
        """System prompt for news sentiment analysis."""
        return """You are an expert sports analyst specializing in sentiment analysis.
You understand how news affects team performance, morale, and betting markets.
Focus on actionable insights and provide confidence scores based on evidence strength."""

    @staticmethod
    def injury_impact_prompt(injury_details: str, team_name: str) -> str:
        """Generate prompt for injury impact assessment.

        Args:
            injury_details: Injury information (player, severity, timeline)
            team_name: Team affected by injury

        Returns:
            Formatted prompt for Claude
        """
        return f"""Assess the impact of this injury on {team_name}'s upcoming match performance:

{injury_details}

Consider:
- Player's importance to team (key player vs squad player)
- Position-specific impact (striker vs defender)
- Availability of quality replacements
- Team's depth in that position
- Recent team form with/without this player

Return JSON with:
- impact_level: "low", "medium", or "high"
- confidence: number 0-1
- factors: array of key factors (e.g., "star_striker_missing", "poor_backup_options")
- recommendation: brief betting implication (1-2 sentences)
"""

    @staticmethod
    def injury_impact_system_prompt() -> str:
        """System prompt for injury impact assessment."""
        return """You are an expert sports analyst specializing in injury impact assessment.
You understand squad depth, tactical systems, and how player absences affect team performance.
Base your assessment on evidence and provide clear reasoning."""

    @staticmethod
    def weather_impact_prompt(
        weather_conditions: dict[str, Any],
        match_type: str = "soccer"
    ) -> str:
        """Generate prompt for weather impact assessment.

        Args:
            weather_conditions: Weather data (temp, precipitation, wind, etc.)
            match_type: Type of match (soccer, nba, nfl, etc.)

        Returns:
            Formatted prompt for Claude
        """
        weather_summary = f"""Temperature: {weather_conditions.get('temperature', 'N/A')}°C
Precipitation: {weather_conditions.get('precipitation', 'none')}
Wind Speed: {weather_conditions.get('wind_speed', 0)} m/s
Visibility: {weather_conditions.get('visibility', 10000)} meters
Humidity: {weather_conditions.get('humidity', 0)}%"""

        return f"""Assess how these weather conditions will impact a {match_type} match:

{weather_summary}

Consider:
- Playing style impact (possession vs counter-attack)
- Passing accuracy in wet/windy conditions
- Goalkeeper challenges (visibility, ball movement)
- Player fatigue in extreme conditions
- Historical performance in similar weather
- Scoring likelihood (over/under goals)

Return JSON with:
- impact_level: "low", "medium", or "high"
- confidence: number 0-1
- factors: array of specific weather factors affecting play
- betting_implications: specific betting insights (e.g., "Consider under 2.5 goals")
"""

    @staticmethod
    def weather_impact_system_prompt() -> str:
        """System prompt for weather impact assessment."""
        return """You are an expert sports analyst specializing in weather impact analysis.
You understand how different weather conditions affect playing styles, tactics, and scoring.
Provide actionable betting insights based on weather patterns."""

    @staticmethod
    def historical_weather_performance_prompt(
        team_name: str,
        weather_type: str,
        historical_data: list[dict[str, Any]]
    ) -> str:
        """Generate prompt for historical weather performance analysis.

        Args:
            team_name: Team to analyze
            weather_type: Type of weather (rain, snow, wind, heat)
            historical_data: Past match results in similar conditions

        Returns:
            Formatted prompt for Claude
        """
        # Format historical data for prompt
        data_summary = "\n".join([
            f"- {match.get('date', 'Unknown')}: {match.get('result', 'N/A')} "
            f"({match.get('score', 'N/A')}) vs {match.get('opponent', 'Unknown')}"
            for match in historical_data[:10]  # Limit to last 10 matches
        ])

        return f"""Analyze {team_name}'s historical performance in {weather_type} conditions:

Recent matches in {weather_type}:
{data_summary}

Identify:
- Win/loss/draw patterns in these conditions
- Scoring trends (over/under average)
- Home vs away performance differences
- Tactical adjustments made
- Statistical significance of the pattern

Return JSON with:
- pattern_strength: "weak", "moderate", or "strong"
- confidence: number 0-1
- win_rate: percentage (0-100)
- avg_goals_scored: average goals
- avg_goals_conceded: average goals
- key_insight: main takeaway for betting (1-2 sentences)
"""

    @staticmethod
    def historical_weather_performance_system_prompt() -> str:
        """System prompt for historical weather performance analysis."""
        return """You are an expert sports statistician specializing in pattern analysis.
You identify meaningful trends while avoiding false patterns from small sample sizes.
Provide statistical context and confidence levels for all insights."""

    @staticmethod
    def get_response_schema(analysis_type: str) -> dict[str, Any]:
        """Get JSON schema for structured output validation.

        Args:
            analysis_type: Type of analysis (sentiment, injury, weather, historical)

        Returns:
            JSON schema for response validation
        """
        if analysis_type == "sentiment":
            return {
                "type": "object",
                "properties": {
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "key_topics": {"type": "array", "items": {"type": "string"}},
                    "impact_summary": {"type": "string"}
                },
                "required": ["sentiment", "confidence"]
            }
        elif analysis_type == "injury":
            return {
                "type": "object",
                "properties": {
                    "impact_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "factors": {"type": "array", "items": {"type": "string"}},
                    "recommendation": {"type": "string"}
                },
                "required": ["impact_level", "confidence"]
            }
        elif analysis_type == "weather":
            return {
                "type": "object",
                "properties": {
                    "impact_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "factors": {"type": "array", "items": {"type": "string"}},
                    "betting_implications": {"type": "string"}
                },
                "required": ["impact_level", "confidence"]
            }
        elif analysis_type == "historical":
            return {
                "type": "object",
                "properties": {
                    "pattern_strength": {"type": "string", "enum": ["weak", "moderate", "strong"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "win_rate": {"type": "number", "minimum": 0, "maximum": 100},
                    "avg_goals_scored": {"type": "number", "minimum": 0},
                    "avg_goals_conceded": {"type": "number", "minimum": 0},
                    "key_insight": {"type": "string"}
                },
                "required": ["pattern_strength", "confidence"]
            }
        else:
            return {"type": "object"}
