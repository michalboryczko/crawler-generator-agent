#!/usr/bin/env python3
"""Main entry point for the web crawler agent.

This module uses the observability system for structured logging and tracing.
The observability decorators handle automatic instrumentation of all components.
"""
import argparse
import logging
import shutil
import sys
import os

# Load .env file before any other imports that use os.environ
from dotenv import load_dotenv
load_dotenv()

from src.core.config import AppConfig
from src.core.llm import LLMClient
from src.core.browser import BrowserSession
from src.tools.memory import MemoryStore
from src.agents.main_agent import MainAgent

# Observability imports
from src.observability.config import (
    ObservabilityConfig,
    initialize_observability,
    shutdown,
)
from src.observability.handlers import OTelGrpcHandler, OTelConfig
from src.observability.context import get_or_create_context, set_context
from src.observability.emitters import emit_info, emit_warning, emit_error


def setup_logging(level: str) -> None:
    """Configure legacy logging (for backward compatibility)."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


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

    # Setup legacy logging for backward compatibility
    setup_logging(args.log_level)
    legacy_logger = logging.getLogger(__name__)

    # Get config from environment
    otel_endpoint = os.environ.get("OTEL_ENDPOINT", "localhost:4317")
    otel_insecure = os.environ.get("OTEL_INSECURE", "true").lower() == "true"
    service_name = os.environ.get("SERVICE_NAME", "crawler-agent")

    # Initialize the observability system
    # Create handler for logs (traces are handled by tracer in config)
    otel_handler = OTelGrpcHandler(OTelConfig(
        endpoint=otel_endpoint,
        insecure=otel_insecure,
        service_name=service_name,
    ))

    # Create config with same settings
    obs_config = ObservabilityConfig(
        service_name=service_name,
        otel_endpoint=otel_endpoint,
        otel_insecure=otel_insecure,
    )

    # Initialize observability (this also initializes tracer)
    initialize_observability(handler=otel_handler, config=obs_config)

    # Create root context for the session (business metadata only)
    # OTel spans will be created by decorators
    ctx = get_or_create_context("application")
    set_context(ctx)

    # Log application start
    emit_info(
        event="application.start",
        ctx=ctx,
        data={"target_url": args.url, "log_level": args.log_level},
        tags=["application", "startup"]
    )

    try:
        # Load configuration
        app_config = AppConfig.from_env()
        legacy_logger.info(f"Using model: {app_config.openai.model}")
        emit_info(
            event="config.loaded",
            ctx=ctx,
            data={"model": app_config.openai.model}
        )

        # Create output directory from URL
        output_dir = app_config.output.get_output_dir(args.url)
        output_dir.mkdir(parents=True, exist_ok=True)
        legacy_logger.info(f"Output directory: {output_dir}")

        # Initialize components
        llm = LLMClient(app_config.openai)
        browser_session = BrowserSession(app_config.browser)
        memory_store = MemoryStore()

        # Connect to browser
        legacy_logger.info("Connecting to Chrome DevTools...")
        emit_info(
            event="browser.connect.start",
            ctx=ctx,
            data={"message": "Connecting to Chrome DevTools..."}
        )
        browser_session.connect()
        emit_info(
            event="browser.connect.complete",
            ctx=ctx,
            data={"message": "Connected to Chrome DevTools"}
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
                if app_config.output.template_dir and app_config.output.template_dir.exists():
                    legacy_logger.info(f"Copying templates from: {app_config.output.template_dir}")
                    shutil.copytree(
                        app_config.output.template_dir,
                        output_dir,
                        dirs_exist_ok=True
                    )

                legacy_logger.info(f"Output files written to: {output_dir}")

                # Log success
                emit_info(
                    event="application.complete",
                    ctx=ctx,
                    data={"output_dir": str(output_dir), "success": True},
                    tags=["application", "success"]
                )
                return 0
            else:
                legacy_logger.error(f"Failed to create plan: {result.get('error')}")
                emit_error(
                    event="application.failed",
                    ctx=ctx,
                    data={"error": result.get("error"), "success": False},
                    tags=["application", "failure"]
                )
                return 1

        finally:
            browser_session.disconnect()
            emit_info(
                event="browser.disconnect",
                ctx=ctx,
                data={"message": "Disconnected from Chrome DevTools"}
            )

    except KeyboardInterrupt:
        legacy_logger.info("Interrupted by user")
        emit_warning(
            event="application.interrupted",
            ctx=ctx,
            data={"message": "Interrupted by user"},
            tags=["application", "interrupted"]
        )
        return 130
    except Exception as e:
        legacy_logger.error(f"Error: {e}", exc_info=True)
        emit_error(
            event="application.error",
            ctx=ctx,
            data={
                "error_type": type(e).__name__,
                "error_message": str(e)
            },
            tags=["application", "error", "unhandled"]
        )
        return 1
    finally:
        # Shutdown observability system (flushes and closes all outputs)
        shutdown()


if __name__ == "__main__":
    sys.exit(main())
