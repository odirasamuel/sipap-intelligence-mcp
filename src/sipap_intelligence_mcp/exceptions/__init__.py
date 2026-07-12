"""Exception hierarchy for SIPAP Intelligence MCP Server."""

from sipap_common.exceptions import SIPAPException


class IntelligenceMCPException(SIPAPException):
    """Base exception for intelligence MCP errors."""

    pass


class WeatherAPIException(IntelligenceMCPException):
    """Raised when OpenWeatherMap API fails."""

    pass


class NewsAPIException(IntelligenceMCPException):
    """Raised when NewsAPI fails."""

    pass


class ClaudeAPIException(IntelligenceMCPException):
    """Raised when Claude/Bedrock API fails."""

    pass


class CacheException(IntelligenceMCPException):
    """Raised when cache operations fail."""

    pass


class PromptTemplateException(IntelligenceMCPException):
    """Raised when prompt template rendering fails."""

    pass


__all__ = [
    "IntelligenceMCPException",
    "WeatherAPIException",
    "NewsAPIException",
    "ClaudeAPIException",
    "CacheException",
    "PromptTemplateException",
]
