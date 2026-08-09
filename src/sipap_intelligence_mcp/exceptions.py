"""Exceptions for sipap-intelligence-mcp."""


class IntelligenceMCPException(Exception):
    """Base exception for intelligence MCP."""


class ClaudeAPIException(IntelligenceMCPException):
    """Exception raised when Claude/Bedrock API fails."""


class WeatherAPIException(IntelligenceMCPException):
    """Exception raised when OpenWeatherMap API fails."""


class NewsAPIException(IntelligenceMCPException):
    """Exception raised when NewsAPI fails."""


class CacheException(IntelligenceMCPException):
    """Exception raised when Redis cache operations fail."""
