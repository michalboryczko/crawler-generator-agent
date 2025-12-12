"""Event sampling for high-volume log events.

Provides sampling strategies to reduce log volume in production
while maintaining statistical accuracy and preserving important events.
"""

import random
import time
from dataclasses import dataclass, field
from typing import Callable

from .structured_logger import LogEntry, LogLevel


@dataclass
class SamplingConfig:
    """Configuration for event sampling.

    Supports:
    - Global sampling rate
    - Per-event-type sampling rates
    - Time-based sampling windows
    - Error event preservation (never sampled)
    """

    # Global sampling rate (0.0 to 1.0, where 1.0 = log everything)
    global_rate: float = 1.0

    # Per-event-type sampling rates (overrides global rate)
    event_type_rates: dict[str, float] = field(default_factory=lambda: {
        # High-volume events get lower sample rates
        "memory.read": 0.1,      # 10% of memory reads
        "memory.write": 0.5,     # 50% of memory writes
        "browser.query": 0.1,    # 10% of DOM queries
        "browser.wait": 0.5,     # 50% of waits
    })

    # Event types to always log (never sample)
    always_log_event_types: set[str] = field(default_factory=lambda: {
        "agent.start",
        "agent.complete",
        "agent.error",
        "llm.call.start",
        "llm.call.complete",
        "llm.call.error",
        "tool.execute.start",
        "tool.execute.complete",
        "tool.execute.error",
        "batch.fetch.start",
        "batch.fetch.complete",
        "batch.extract.start",
        "batch.extract.complete",
    })

    # Always log errors (regardless of sampling)
    always_log_errors: bool = True

    # Minimum interval between duplicate event logs (in seconds)
    dedup_window_seconds: float = 1.0

    enabled: bool = True


class EventSampler:
    """Samples log events based on configuration.

    Provides deterministic sampling using event characteristics
    to ensure consistent sampling decisions for related events.
    """

    def __init__(self, config: SamplingConfig | None = None):
        """Initialize sampler with configuration.

        Args:
            config: Sampling configuration (uses defaults if None)
        """
        self.config = config or SamplingConfig()
        self._last_seen: dict[str, float] = {}  # For deduplication
        self._sample_counts: dict[str, int] = {}  # For metrics

    def should_sample(self, entry: LogEntry) -> bool:
        """Determine if a log entry should be sampled (logged).

        Args:
            entry: Log entry to evaluate

        Returns:
            True if the entry should be logged, False if it should be dropped
        """
        if not self.config.enabled:
            return True  # Sampling disabled, log everything

        event_type = entry.event.event_type

        # Always log errors
        if self.config.always_log_errors and entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
            return True

        # Always log specified event types
        if event_type in self.config.always_log_event_types:
            return True

        # Check deduplication window
        if not self._check_dedup_window(entry):
            return False

        # Get sampling rate for this event type
        rate = self.config.event_type_rates.get(event_type, self.config.global_rate)

        # Deterministic sampling based on trace context for consistency
        # This ensures related events in the same span are sampled together
        if rate < 1.0:
            # Use span_id for deterministic sampling
            seed = hash(entry.trace_context.span_id + event_type)
            random.seed(seed)
            sampled = random.random() < rate
            random.seed()  # Reset random state

            # Track sampling stats
            self._track_sample(event_type, sampled)
            return sampled

        return True

    def _check_dedup_window(self, entry: LogEntry) -> bool:
        """Check if event passes deduplication window.

        Args:
            entry: Log entry to check

        Returns:
            True if event should be logged (not a duplicate within window)
        """
        if self.config.dedup_window_seconds <= 0:
            return True

        # Create dedup key from event characteristics
        dedup_key = f"{entry.event.event_type}:{entry.message[:50]}"
        current_time = time.time()
        last_time = self._last_seen.get(dedup_key, 0)

        if current_time - last_time < self.config.dedup_window_seconds:
            return False

        self._last_seen[dedup_key] = current_time
        return True

    def _track_sample(self, event_type: str, sampled: bool) -> None:
        """Track sampling statistics.

        Args:
            event_type: Event type being sampled
            sampled: Whether the event was sampled (logged)
        """
        key = f"{event_type}:{'sampled' if sampled else 'dropped'}"
        self._sample_counts[key] = self._sample_counts.get(key, 0) + 1

    def get_stats(self) -> dict[str, int]:
        """Get sampling statistics.

        Returns:
            Dictionary of sampling counts by event type
        """
        return dict(self._sample_counts)

    def reset_stats(self) -> None:
        """Reset sampling statistics."""
        self._sample_counts.clear()
        self._last_seen.clear()


class SampledOutput:
    """Log output wrapper that applies sampling.

    Wraps another LogOutput and applies sampling before
    forwarding log entries.
    """

    def __init__(self, wrapped, sampler: EventSampler | None = None):
        """Initialize sampled output.

        Args:
            wrapped: The underlying LogOutput to wrap
            sampler: EventSampler to use (creates default if None)
        """
        self.wrapped = wrapped
        self.sampler = sampler or EventSampler()

    def write(self, entry: LogEntry) -> None:
        """Write entry if it passes sampling.

        Args:
            entry: Log entry to potentially write
        """
        if self.sampler.should_sample(entry):
            self.wrapped.write(entry)

    def flush(self) -> None:
        """Flush the wrapped output."""
        self.wrapped.flush()

    def close(self) -> None:
        """Close the wrapped output."""
        self.wrapped.close()


# Global default sampler instance
_default_sampler: EventSampler | None = None


def get_sampler() -> EventSampler:
    """Get the default event sampler instance.

    Returns:
        Default EventSampler instance
    """
    global _default_sampler
    if _default_sampler is None:
        _default_sampler = EventSampler()
    return _default_sampler


def set_sampler(sampler: EventSampler) -> None:
    """Set the default event sampler instance.

    Args:
        sampler: EventSampler instance to use as default
    """
    global _default_sampler
    _default_sampler = sampler


def configure_sampling(
    global_rate: float = 1.0,
    event_type_rates: dict[str, float] | None = None,
    always_log_errors: bool = True,
    enabled: bool = True,
) -> EventSampler:
    """Configure and set the default sampler.

    Args:
        global_rate: Default sampling rate (0.0 to 1.0)
        event_type_rates: Per-event-type sampling rates
        always_log_errors: Whether to always log error events
        enabled: Whether sampling is enabled

    Returns:
        Configured EventSampler instance
    """
    config = SamplingConfig(
        global_rate=global_rate,
        event_type_rates=event_type_rates or {},
        always_log_errors=always_log_errors,
        enabled=enabled,
    )
    sampler = EventSampler(config)
    set_sampler(sampler)
    return sampler
