"""Exception hierarchy for SIPAP Intelligence MCP Server."""

from sipap_common.exceptions import SIPAPException  # type: ignore[import-untyped]


class IntelligenceMCPException(SIPAPException):  # type: ignore[misc]
    """Base exception for intelligence MCP errors."""



class WeatherAPIException(IntelligenceMCPException):
    """Raised when OpenWeatherMap API fails."""



class NewsAPIException(IntelligenceMCPException):
    """Raised when NewsAPI fails."""



class ClaudeAPIException(IntelligenceMCPException):
    """Raised when Claude/Bedrock API fails."""



class CacheException(IntelligenceMCPException):
    """Raised when cache operations fail."""



class PromptTemplateException(IntelligenceMCPException):
    """Raised when prompt template rendering fails."""



__all__ = [
    "IntelligenceMCPException",
    "WeatherAPIException",
    "NewsAPIException",
    "ClaudeAPIException",
    "CacheException",
    "PromptTemplateException",
]
