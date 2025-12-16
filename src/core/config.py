"""Configuration management."""
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    pass


def url_to_dirname(url: str) -> str:
    """Convert URL to safe directory name.

    Example: https://www.rand.org/blog -> rand_org
    """
    parsed = urlparse(url)
    hostname = parsed.netloc or parsed.path.split("/")[0]
    # Remove www. prefix and port
    hostname = re.sub(r"^www\.", "", hostname)
    hostname = re.sub(r":\d+$", "", hostname)
    # Replace dots and special chars with underscore
    dirname = re.sub(r"[^a-zA-Z0-9]", "_", hostname)
    # Remove consecutive underscores
    dirname = re.sub(r"_+", "_", dirname)
    return dirname.strip("_").lower()


@dataclass
class OutputConfig:
    """Output directory configuration."""
    base_dir: Path
    template_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "OutputConfig":
        base_dir = Path(os.environ.get("PLANS_OUTPUT_DIR", "./plans_output"))
        template_dir_str = os.environ.get("PLANS_TEMPLATE_DIR")
        template_dir = Path(template_dir_str) if template_dir_str else None
        return cls(base_dir=base_dir, template_dir=template_dir)

    def get_output_dir(self, url: str) -> Path:
        """Get output directory for a given URL.

        Format: {base_dir}/{url_dirname}_{timestamp}
        Example: ./plans_output/example_com_20250116_153045
        """
        dirname = url_to_dirname(url)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.base_dir / f"{dirname}_{timestamp}"


@dataclass
class OpenAIConfig:
    """Legacy OpenAI API configuration.

    This class is maintained for backward compatibility. For new code,
    use LLMClientFactory with ModelConfig and ComponentModelConfig instead.

    See docs/multi-model-configuration.md for migration guide.
    """
    api_key: str
    model: str = "gpt-5.1"
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Load configuration from environment variables.

        Supports both legacy (OPENAI_API_KEY) and new (OPENAI_KEY) variable names.
        """
        # Support both old and new env var names
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY or OPENAI_KEY environment variable"
            )
        return cls(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL", os.environ.get("DEFAULT_MODEL", "gpt-4o")),
            temperature=float(os.environ.get("OPENAI_TEMPERATURE", "0.0")),
        )


@dataclass
class BrowserConfig:
    """Chrome DevTools configuration.

    Supports two modes:
    1. URL mode: Set CDP_URL to full WebSocket URL (e.g., ws://localhost:9222)
    2. Host/Port mode: Set CDP_HOST and CDP_PORT separately

    CDP_URL takes precedence if both are set.
    """
    host: str = "localhost"
    port: int = 9222
    timeout: int = 30
    url: str | None = None  # Full WebSocket URL (overrides host/port)

    @classmethod
    def from_env(cls) -> "BrowserConfig":
        cdp_url = os.environ.get("CDP_URL")

        # If URL provided, parse host/port from it for compatibility
        if cdp_url:
            parsed = urlparse(cdp_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 9222
            return cls(
                host=host,
                port=port,
                timeout=int(os.environ.get("CDP_TIMEOUT", "30")),
                url=cdp_url,
            )

        return cls(
            host=os.environ.get("CDP_HOST", "localhost"),
            port=int(os.environ.get("CDP_PORT", "9222")),
            timeout=int(os.environ.get("CDP_TIMEOUT", "30")),
        )

    @property
    def websocket_url(self) -> str:
        """Get the WebSocket URL for DevTools connection."""
        if self.url:
            return self.url
        return f"ws://{self.host}:{self.port}"


@dataclass
class StorageConfig:
    """Configuration for storage backend.

    Usage in .env:
        STORAGE_BACKEND=memory                              # In-memory (default)
        STORAGE_BACKEND=sqlalchemy                          # Use DATABASE_URL
        DATABASE_URL=mysql+mysqlconnector://user:pass@host/db
        DATABASE_URL=postgresql://user:pass@host/db
        DATABASE_URL=sqlite:///./crawler.db
    """

    backend_type: str = "memory"  # 'memory' or 'sqlalchemy'
    database_url: str | None = None

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """Load storage configuration from environment variables."""
        return cls(
            backend_type=os.environ.get("STORAGE_BACKEND", "memory"),
            database_url=os.environ.get("DATABASE_URL"),
        )


def get_agent_version() -> str:
    """Get agent version from environment or fallback to 'unknown'."""
    return os.environ.get("AGENT_VERSION", "unknown")


@dataclass
class AppConfig:
    """Main application configuration."""
    openai: OpenAIConfig
    browser: BrowserConfig
    output: OutputConfig
    storage: StorageConfig
    log_level: str = "INFO"
    agent_version: str = "unknown"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            openai=OpenAIConfig.from_env(),
            browser=BrowserConfig.from_env(),
            output=OutputConfig.from_env(),
            storage=StorageConfig.from_env(),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            agent_version=get_agent_version(),
        )
