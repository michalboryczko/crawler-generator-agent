"""Configuration management."""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


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
        """Get output directory for a given URL."""
        dirname = url_to_dirname(url)
        return self.base_dir / dirname


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
    output: OutputConfig
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            openai=OpenAIConfig.from_env(),
            browser=BrowserConfig.from_env(),
            output=OutputConfig.from_env(),
            log_level=os.environ.get("LOG_LEVEL", "INFO")
        )
