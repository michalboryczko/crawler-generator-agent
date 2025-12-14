"""Configuration for the observability system.

This module provides configuration management for observability.
Note: There is NO log level filtering. Level is metadata only.
All events are always emitted.

Architecture:
    - Config is just data, no knowledge of handler implementations
    - Handler is injected via initialize_observability()
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
        console_enabled: Whether to output to console (dev only)
        console_color: Whether to use colored console output
        redact_pii: Whether to redact PII from logs
    """
    service_name: str = "crawler-agent"

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
            LOG_CONSOLE: Enable console output (default: true)
            LOG_COLOR: Enable colored console (default: true)
            LOG_REDACT_PII: Enable PII redaction (default: true)

        Returns:
            ObservabilityConfig loaded from environment.
        """
        return cls(
            service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
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

    Args:
        handler: LogHandler instance (injected by caller).
        config: Configuration to use. Loads from env if None.
    """
    global _handler, _console_output, _initialized, _config

    if config is None:
        config = ObservabilityConfig.from_env()

    _config = config
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
