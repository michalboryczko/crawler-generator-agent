"""Configuration management."""
import os
from dataclasses import dataclass


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    model: str = "gpt-4o"
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
        return cls(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            temperature=float(os.environ.get("OPENAI_TEMPERATURE", "0.0")),
        )


@dataclass
class BrowserConfig:
    """Chrome DevTools configuration."""
    host: str = "localhost"
    port: int = 9222
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "BrowserConfig":
        return cls(
            host=os.environ.get("CDP_HOST", "localhost"),
            port=int(os.environ.get("CDP_PORT", "9222")),
            timeout=int(os.environ.get("CDP_TIMEOUT", "30"))
        )


@dataclass
class AppConfig:
    """Main application configuration."""
    openai: OpenAIConfig
    browser: BrowserConfig
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            openai=OpenAIConfig.from_env(),
            browser=BrowserConfig.from_env(),
            log_level=os.environ.get("LOG_LEVEL", "INFO")
        )
