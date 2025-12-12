"""Configuration for structured logging.

Provides a dataclass-based configuration system that can be loaded from
environment variables or created programmatically.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from .log_outputs import (
    AsyncBufferedOutput,
    ConsoleOutput,
    JSONLinesOutput,
    OpenTelemetryOutput,
    CompositeOutput,
    LogOutput,
)
from .structured_logger import LogLevel


@dataclass
class LoggingConfig:
    """Configuration for the structured logging system.

    Provides settings for:
    - General log level and service name
    - Console output (human-readable)
    - JSON Lines file output (machine-parseable)
    - OpenTelemetry export (distributed tracing)
    - Sampling and PII redaction (for production)
    """

    # General settings
    min_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "crawler-agent"

    # Console output settings
    console_enabled: bool = True
    console_color: bool = True

    # JSON Lines output settings
    jsonl_enabled: bool = True
    jsonl_path: Path | None = None  # None = auto-generate based on session
    jsonl_async: bool = True
    jsonl_buffer_size: int = 100
    jsonl_flush_interval: float = 1.0

    # OpenTelemetry output settings
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"
    otel_export_logs: bool = True
    otel_export_traces: bool = True

    # Sampling settings (for high-volume events)
    sampling_enabled: bool = False
    sampling_rate: float = 1.0  # 1.0 = log everything
    sampled_event_types: list[str] = field(default_factory=lambda: [
        "memory.read",
        "memory.write",
        "browser.query",
    ])

    # PII redaction settings
    redact_pii: bool = True
    redact_patterns: list[str] = field(default_factory=lambda: [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone
        r"\b\d{16}\b",  # Credit card (simple)
    ])

    # Content truncation settings
    max_content_preview: int = 500
    max_url_params: int = 100

    # Log directory for auto-generated paths
    log_dir: Path = field(default_factory=lambda: Path("logs"))

    def create_outputs(self) -> list[LogOutput]:
        """Create log outputs based on configuration.

        Returns:
            List of configured LogOutput instances
        """
        outputs: list[LogOutput] = []

        # Console output
        if self.console_enabled:
            outputs.append(ConsoleOutput(color=self.console_color))

        # JSON Lines output
        if self.jsonl_enabled:
            # Auto-generate log file path if not specified
            if self.jsonl_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                jsonl_path = self.log_dir / f"agent_{timestamp}.jsonl"
            else:
                jsonl_path = self.jsonl_path

            # Ensure parent directory exists
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)

            jsonl_output: LogOutput = JSONLinesOutput(file_path=jsonl_path)

            # Wrap in async buffer if enabled
            if self.jsonl_async:
                jsonl_output = AsyncBufferedOutput(
                    jsonl_output,
                    buffer_size=self.jsonl_buffer_size,
                    flush_interval=self.jsonl_flush_interval,
                )

            outputs.append(jsonl_output)

        # OpenTelemetry output
        if self.otel_enabled:
            outputs.append(OpenTelemetryOutput(
                service_name=self.service_name,
                endpoint=self.otel_endpoint,
                export_logs=self.otel_export_logs,
                export_traces=self.otel_export_traces,
            ))

        return outputs

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load configuration from environment variables.

        Environment variables:
        - LOG_LEVEL: Minimum log level (default: INFO)
        - SERVICE_NAME: Service name (default: crawler-agent)
        - LOG_CONSOLE: Enable console output (default: true)
        - LOG_COLOR: Enable colored console output (default: true)
        - LOG_JSONL: Enable JSON Lines output (default: true)
        - LOG_JSONL_PATH: JSON Lines file path (default: auto-generated)
        - LOG_JSONL_ASYNC: Enable async buffering (default: true)
        - LOG_DIR: Directory for log files (default: logs)
        - LOG_OTEL: Enable OpenTelemetry (default: false)
        - LOG_OTEL_ENDPOINT: OTLP endpoint (default: http://localhost:4317)
        - LOG_SAMPLING: Enable event sampling (default: false)
        - LOG_SAMPLING_RATE: Sampling rate 0.0-1.0 (default: 1.0)
        - LOG_REDACT_PII: Enable PII redaction (default: true)

        Returns:
            LoggingConfig populated from environment
        """
        return cls(
            min_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
            console_enabled=os.environ.get("LOG_CONSOLE", "true").lower() == "true",
            console_color=os.environ.get("LOG_COLOR", "true").lower() == "true",
            jsonl_enabled=os.environ.get("LOG_JSONL", "true").lower() == "true",
            jsonl_path=Path(p) if (p := os.environ.get("LOG_JSONL_PATH")) else None,
            jsonl_async=os.environ.get("LOG_JSONL_ASYNC", "true").lower() == "true",
            log_dir=Path(os.environ.get("LOG_DIR", "logs")),
            otel_enabled=os.environ.get("LOG_OTEL", "false").lower() == "true",
            otel_endpoint=os.environ.get("LOG_OTEL_ENDPOINT", "http://localhost:4317"),
            sampling_enabled=os.environ.get("LOG_SAMPLING", "false").lower() == "true",
            sampling_rate=float(os.environ.get("LOG_SAMPLING_RATE", "1.0")),
            redact_pii=os.environ.get("LOG_REDACT_PII", "true").lower() == "true",
        )

    @classmethod
    def development(cls) -> "LoggingConfig":
        """Create a development configuration.

        Enables console output with colors, JSON Lines to logs/ directory,
        and DEBUG level logging.

        Returns:
            Development-friendly LoggingConfig
        """
        return cls(
            min_level="DEBUG",
            console_enabled=True,
            console_color=True,
            jsonl_enabled=True,
            jsonl_async=False,  # Synchronous for easier debugging
            otel_enabled=False,
            sampling_enabled=False,
            redact_pii=False,  # Don't redact in development
        )

    @classmethod
    def production(cls) -> "LoggingConfig":
        """Create a production configuration.

        Enables INFO level, async JSON Lines, PII redaction,
        and optionally OpenTelemetry.

        Returns:
            Production-ready LoggingConfig
        """
        return cls(
            min_level="INFO",
            console_enabled=False,  # Usually not needed in production
            console_color=False,
            jsonl_enabled=True,
            jsonl_async=True,
            jsonl_buffer_size=200,
            otel_enabled=True,
            sampling_enabled=False,  # Enable if needed for high volume
            redact_pii=True,
        )

    @classmethod
    def testing(cls) -> "LoggingConfig":
        """Create a testing configuration.

        Minimal output for tests - only console at WARNING level.

        Returns:
            Testing LoggingConfig
        """
        return cls(
            min_level="WARNING",
            console_enabled=True,
            console_color=False,
            jsonl_enabled=False,
            otel_enabled=False,
            sampling_enabled=False,
            redact_pii=False,
        )


# LLM cost lookup table (per 1K tokens)
# Used for cost estimation in metrics
MODEL_COSTS: dict[str, dict[str, float]] = {
    # OpenAI models
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},

    # Anthropic models
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
}


def estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    """Estimate API cost for an LLM call.

    Args:
        model: Model name (e.g., "gpt-4o", "gpt-4o-mini")
        tokens_input: Number of input tokens
        tokens_output: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    costs = MODEL_COSTS.get(model, {"input": 0, "output": 0})
    return (
        (tokens_input / 1000) * costs["input"] +
        (tokens_output / 1000) * costs["output"]
    )
