"""Configuration for the observability system.

This module provides configuration management for observability outputs.
Note: There is NO log level filtering. Level is metadata only.
All events are always emitted to all outputs.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .outputs import LogOutput


@dataclass
class ObservabilityConfig:
    """Configuration for observability outputs.
    
    Note: There is NO log level filtering. Level is metadata only.
    All events are always emitted to all outputs.
    
    Attributes:
        service_name: Service name for logs/traces identification
        console_enabled: Whether to output to console
        console_color: Whether to use colored console output
        jsonl_enabled: Whether to output to JSONL files
        jsonl_path: Explicit path for JSONL file (auto-generated if None)
        log_dir: Directory for log files
        otel_enabled: Whether to enable OpenTelemetry output
        otel_endpoint: OTLP endpoint URL
        otel_insecure: Whether to use insecure connection
        redact_pii: Whether to redact PII from logs
    """
    service_name: str = "crawler-agent"
    
    # Console output
    console_enabled: bool = True
    console_color: bool = True
    
    # JSONL file output
    jsonl_enabled: bool = True
    jsonl_path: Optional[Path] = None
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    
    # OpenTelemetry output
    otel_enabled: bool = False
    otel_endpoint: str = "localhost:4317"
    otel_insecure: bool = True
    
    # PII redaction (preserves existing functionality)
    redact_pii: bool = True

    def create_outputs(self) -> List['LogOutput']:
        """Create configured outputs.
        
        Returns:
            List of configured LogOutput instances.
        """
        # Import here to avoid circular imports
        from .outputs import ConsoleOutput, JSONLinesOutput, OTLPOutput
        
        outputs: List['LogOutput'] = []

        if self.console_enabled:
            outputs.append(ConsoleOutput(color=self.console_color))

        if self.jsonl_enabled:
            if self.jsonl_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = self.log_dir / f"agent_{timestamp}.jsonl"
            else:
                path = self.jsonl_path
            path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(JSONLinesOutput(path))

        if self.otel_enabled:
            outputs.append(OTLPOutput(
                service_name=self.service_name,
                endpoint=self.otel_endpoint,
                insecure=self.otel_insecure
            ))

        return outputs

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """Load from environment variables.
        
        Environment Variables:
            SERVICE_NAME: Service name for logs/traces
            LOG_CONSOLE: Enable console output (default: true)
            LOG_COLOR: Enable colored console (default: true)
            LOG_JSONL: Enable JSONL file output (default: true)
            LOG_JSONL_PATH: Explicit JSONL file path
            LOG_DIR: Log directory (default: logs)
            LOG_OTEL: Enable OpenTelemetry (default: false)
            LOG_OTEL_ENDPOINT: OTLP endpoint (default: localhost:4317)
            LOG_OTEL_INSECURE: Use insecure connection (default: true)
            LOG_REDACT_PII: Enable PII redaction (default: true)
            
        Returns:
            ObservabilityConfig loaded from environment.
        """
        jsonl_path = os.environ.get("LOG_JSONL_PATH")
        
        return cls(
            service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
            console_enabled=os.environ.get("LOG_CONSOLE", "true").lower() == "true",
            console_color=os.environ.get("LOG_COLOR", "true").lower() == "true",
            jsonl_enabled=os.environ.get("LOG_JSONL", "true").lower() == "true",
            jsonl_path=Path(jsonl_path) if jsonl_path else None,
            log_dir=Path(os.environ.get("LOG_DIR", "logs")),
            otel_enabled=os.environ.get("LOG_OTEL", "false").lower() == "true",
            otel_endpoint=os.environ.get("LOG_OTEL_ENDPOINT", "localhost:4317"),
            otel_insecure=os.environ.get("LOG_OTEL_INSECURE", "true").lower() == "true",
            redact_pii=os.environ.get("LOG_REDACT_PII", "true").lower() == "true",
        )
    
    @classmethod
    def development(cls) -> "ObservabilityConfig":
        """Create development configuration.
        
        Returns:
            Configuration suitable for development.
        """
        return cls(
            service_name="crawler-agent-dev",
            console_enabled=True,
            console_color=True,
            jsonl_enabled=True,
            log_dir=Path("logs"),
            otel_enabled=False,
            redact_pii=False  # Easier debugging in dev
        )
    
    @classmethod
    def production(cls) -> "ObservabilityConfig":
        """Create production configuration.
        
        Returns:
            Configuration suitable for production.
        """
        return cls(
            service_name="crawler-agent",
            console_enabled=False,  # Use structured outputs only
            console_color=False,
            jsonl_enabled=True,
            log_dir=Path("/var/log/crawler-agent"),
            otel_enabled=True,
            otel_endpoint=os.environ.get("LOG_OTEL_ENDPOINT", "localhost:4317"),
            redact_pii=True
        )


# Global outputs list
_outputs: List['LogOutput'] = []
_initialized: bool = False
_config: Optional[ObservabilityConfig] = None


def initialize_observability(config: ObservabilityConfig = None) -> None:
    """Initialize the observability system.
    
    Args:
        config: Configuration to use. Loads from env if None.
    """
    global _outputs, _initialized, _config
    
    if config is None:
        config = ObservabilityConfig.from_env()
    
    _config = config
    _outputs = config.create_outputs()
    _initialized = True


def get_outputs() -> List['LogOutput']:
    """Get configured outputs.
    
    Returns:
        List of configured LogOutput instances.
    """
    return _outputs


def get_config() -> Optional[ObservabilityConfig]:
    """Get current configuration.
    
    Returns:
        Current ObservabilityConfig or None if not initialized.
    """
    return _config


def is_initialized() -> bool:
    """Check if observability is initialized.
    
    Returns:
        True if initialized, False otherwise.
    """
    return _initialized


def shutdown() -> None:
    """Shutdown the observability system.
    
    Flushes and closes all outputs.
    """
    global _outputs, _initialized, _config
    
    for output in _outputs:
        try:
            output.flush()
            output.close()
        except Exception:
            pass
    
    _outputs = []
    _initialized = False
    _config = None
