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
from src.core.llm import LLMClient, LLMClientFactory
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
        nargs="?",
        help="Target URL to analyze"
    )
    parser.add_argument(
        "--log-level", "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--multi-model", "-m",
        action="store_true",
        help="Enable multi-model mode (use LLMClientFactory with per-component models)"
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit"
    )
    args = parser.parse_args()

    # Handle --list-models
    if args.list_models:
        from src.core.default_models import get_default_registry
        from src.core.component_models import ComponentModelConfig
        registry = get_default_registry()
        component_config = ComponentModelConfig.from_env()
        print("\nAvailable models:")
        for model_id in sorted(registry.list_models()):
            print(f"  - {model_id}")
        print("\nComponent model assignments:")
        for component in component_config.list_components():
            model = component_config.get_model_for_component(component)
            print(f"  {component}: {model}")
        return 0

    # URL is required if not using --list-models
    if not args.url:
        parser.error("url is required")

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

        # Initialize LLM - either factory (multi-model) or single client (legacy)
        if args.multi_model:
            llm_factory = LLMClientFactory.from_env()
            llm = llm_factory.get_client("main_agent")
            legacy_logger.info(f"Multi-model mode: using factory with {len(llm_factory.registry)} models")
            emit_info(
                event="llm.factory.initialized",
                ctx=ctx,
                data={
                    "mode": "multi-model",
                    "model_count": len(llm_factory.registry),
                    "main_agent_model": llm_factory.get_component_model("main_agent")
                }
            )
        else:
            llm = LLMClient(app_config.openai)
            llm_factory = None
            emit_info(
                event="llm.client.initialized",
                ctx=ctx,
                data={"mode": "legacy", "model": app_config.openai.model}
            )

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
