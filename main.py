#!/usr/bin/env python3
"""Main entry point for the web crawler agent."""
import argparse
import logging
import shutil
import sys

# Load .env file before any other imports that use os.environ
from dotenv import load_dotenv
load_dotenv()

from src.core.config import AppConfig
from src.core.llm import LLMClient
from src.core.browser import BrowserSession
from src.tools.memory import MemoryStore
from src.agents.main_agent import MainAgent

# Structured logging imports
from src.core.log_config import LoggingConfig
from src.core.log_context import LoggerManager, get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail
)


def setup_logging(level: str) -> None:
    """Configure legacy logging (for backward compatibility)."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def setup_structured_logging(level: str) -> LoggerManager:
    """Initialize the structured logging system.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Initialized LoggerManager
    """
    # Create logging config based on environment
    config = LoggingConfig.from_env()
    config.min_level = level.upper()

    # Create outputs
    outputs = config.create_outputs()

    # Initialize logger manager
    manager = LoggerManager.initialize(
        outputs=outputs,
        min_level=config.min_level,
        service_name=config.service_name,
    )

    return manager


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create a web crawler plan for a given URL"
    )
    parser.add_argument(
        "url",
        help="Target URL to analyze"
    )
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    args = parser.parse_args()

    # Setup both legacy and structured logging
    setup_logging(args.log_level)
    legacy_logger = logging.getLogger(__name__)

    # Initialize structured logging
    log_manager = setup_structured_logging(args.log_level)
    slog = log_manager.root_logger

    # Log application start
    slog.info(
        event=LogEvent(
            category=EventCategory.AGENT_LIFECYCLE,
            event_type="application.start",
            name="Application started",
        ),
        message=f"Crawler agent starting for URL: {args.url}",
        data={"target_url": args.url, "log_level": args.log_level},
        tags=["application", "startup"],
    )

    try:
        # Load configuration
        config = AppConfig.from_env()
        legacy_logger.info(f"Using model: {config.openai.model}")
        slog.info(
            event=LogEvent(
                category=EventCategory.AGENT_LIFECYCLE,
                event_type="config.loaded",
                name="Configuration loaded",
            ),
            message=f"Using model: {config.openai.model}",
            data={"model": config.openai.model},
        )

        # Create output directory from URL
        output_dir = config.output.get_output_dir(args.url)
        output_dir.mkdir(parents=True, exist_ok=True)
        legacy_logger.info(f"Output directory: {output_dir}")

        # Initialize components
        llm = LLMClient(config.openai)
        browser_session = BrowserSession(config.browser)
        memory_store = MemoryStore()

        # Connect to browser
        legacy_logger.info("Connecting to Chrome DevTools...")
        slog.info(
            event=LogEvent(
                category=EventCategory.BROWSER_OPERATION,
                event_type="browser.connect.start",
                name="Browser connecting",
            ),
            message="Connecting to Chrome DevTools...",
        )
        browser_session.connect()
        slog.info(
            event=LogEvent(
                category=EventCategory.BROWSER_OPERATION,
                event_type="browser.connect.complete",
                name="Browser connected",
            ),
            message="Connected to Chrome DevTools",
        )

        try:
            # Create and run main agent
            agent = MainAgent(llm, browser_session, output_dir, memory_store)
            legacy_logger.info(f"Creating crawl plan for: {args.url}")

            result = agent.create_crawl_plan(args.url)

            if result["success"]:
                legacy_logger.info("Crawl plan created successfully")
                legacy_logger.info(f"Result: {result['result']}")

                # Copy templates if configured
                if config.output.template_dir and config.output.template_dir.exists():
                    legacy_logger.info(f"Copying templates from: {config.output.template_dir}")
                    shutil.copytree(
                        config.output.template_dir,
                        output_dir,
                        dirs_exist_ok=True
                    )

                legacy_logger.info(f"Output files written to: {output_dir}")

                # Log success
                slog.info(
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="application.complete",
                        name="Application completed",
                    ),
                    message="Crawl plan created successfully",
                    data={"output_dir": str(output_dir), "success": True},
                    tags=["application", "success"],
                )
                return 0
            else:
                legacy_logger.error(f"Failed to create plan: {result.get('error')}")
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="application.failed",
                        name="Application failed",
                    ),
                    message=f"Failed to create plan: {result.get('error')}",
                    data={"error": result.get("error"), "success": False},
                    tags=["application", "failure"],
                )
                return 1

        finally:
            browser_session.disconnect()
            slog.info(
                event=LogEvent(
                    category=EventCategory.BROWSER_OPERATION,
                    event_type="browser.disconnect",
                    name="Browser disconnected",
                ),
                message="Disconnected from Chrome DevTools",
            )

    except KeyboardInterrupt:
        legacy_logger.info("Interrupted by user")
        slog.warning(
            event=LogEvent(
                category=EventCategory.AGENT_LIFECYCLE,
                event_type="application.interrupted",
                name="Application interrupted",
            ),
            message="Interrupted by user",
            tags=["application", "interrupted"],
        )
        return 130
    except Exception as e:
        legacy_logger.error(f"Error: {e}", exc_info=True)
        slog.error(
            event=LogEvent(
                category=EventCategory.ERROR,
                event_type="application.error",
                name="Application error",
            ),
            level_detail=LogLevelDetail.ERROR_UNRECOVERABLE,
            message=f"Unhandled error: {type(e).__name__}: {str(e)}",
            data={"error_type": type(e).__name__, "error_message": str(e)},
            tags=["application", "error", "unhandled"],
        )
        return 1
    finally:
        # Flush and close all log outputs
        for output in slog.outputs:
            try:
                output.flush()
                output.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
