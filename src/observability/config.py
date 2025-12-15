"""Configuration for the observability system.

This module provides configuration management for observability.
Note: There is NO log level filtering. Level is metadata only.
All events are always emitted.

Architecture:
    - Config is just data, no knowledge of handler implementations
    - Handler is injected via initialize_observability()
    - Tracer is initialized for OTel span creation
    - ConsoleOutput is optional for development
"""

import os
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .handlers import LogHandler
    from .outputs import LogOutput


@dataclass
class ObservabilityConfig:
    """Configuration for observability system.

    This is pure configuration data - no handler creation logic.
    Handler is injected separately via initialize_observability().

    Attributes:
        service_name: Service name for logs/traces identification
        otel_endpoint: OTel Collector endpoint (host:port)
        otel_insecure: Whether to use insecure connection to collector
        console_enabled: Whether to output to console (dev only)
        console_color: Whether to use colored console output
        redact_pii: Whether to redact PII from logs
    """
    service_name: str = "crawler-agent"

    # OTel Collector settings
    otel_endpoint: str = "localhost:4317"
    otel_insecure: bool = True

    # Console output (for development)
    console_enabled: bool = True
    console_color: bool = True

    # PII redaction
    redact_pii: bool = True

    def create_console_output(self) -> Optional['LogOutput']:
        """Create console output if enabled.

        Returns:
            ConsoleOutput if enabled, None otherwise.
        """
        if not self.console_enabled:
            return None

        from .outputs import ConsoleOutput
        return ConsoleOutput(color=self.console_color)

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """Load from environment variables.

        Environment Variables:
            SERVICE_NAME: Service name for logs/traces
            OTEL_ENDPOINT: OTel Collector endpoint (default: localhost:4317)
            OTEL_INSECURE: Use insecure connection (default: true)
            LOG_CONSOLE: Enable console output (default: true)
            LOG_COLOR: Enable colored console (default: true)
            LOG_REDACT_PII: Enable PII redaction (default: true)

        Returns:
            ObservabilityConfig loaded from environment.
        """
        return cls(
            service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
            otel_endpoint=os.environ.get("OTEL_ENDPOINT", "localhost:4317"),
            otel_insecure=os.environ.get("OTEL_INSECURE", "true").lower() == "true",
            console_enabled=os.environ.get("LOG_CONSOLE", "true").lower() == "true",
            console_color=os.environ.get("LOG_COLOR", "true").lower() == "true",
            redact_pii=os.environ.get("LOG_REDACT_PII", "true").lower() == "true",
        )


# Global state
_handler: Optional['LogHandler'] = None
_console_output: Optional['LogOutput'] = None
_initialized: bool = False
_config: Optional[ObservabilityConfig] = None


def initialize_observability(
    handler: 'LogHandler',
    config: ObservabilityConfig = None
) -> None:
    """Initialize the observability system.

    This initializes:
    1. OTel tracer (for span creation in decorators)
    2. Log handler (for log emission)
    3. Console output (optional)

    Args:
        handler: LogHandler instance (injected by caller).
        config: Configuration to use. Loads from env if None.
    """
    global _handler, _console_output, _initialized, _config

    if config is None:
        config = ObservabilityConfig.from_env()

    _config = config

    # Initialize OTel tracer for span creation
    from .tracer import init_tracer
    init_tracer(
        endpoint=config.otel_endpoint,
        service_name=config.service_name,
        insecure=config.otel_insecure
    )

    _handler = handler
    _console_output = config.create_console_output()
    _initialized = True


def get_handler() -> Optional['LogHandler']:
    """Get the configured handler."""
    return _handler


def get_console_output() -> Optional['LogOutput']:
    """Get the console output if enabled."""
    return _console_output


def get_config() -> Optional[ObservabilityConfig]:
    """Get current configuration."""
    return _config


def is_initialized() -> bool:
    """Check if observability is initialized."""
    return _initialized


def shutdown() -> None:
    """Shutdown the observability system."""
    global _handler, _console_output, _initialized, _config

    # Shutdown tracer
    from .tracer import shutdown_tracer
    shutdown_tracer()

    if _handler:
        try:
            _handler.flush()
            _handler.close()
        except Exception:
            pass

    _handler = None
    _console_output = None
    _initialized = False
    _config = None
