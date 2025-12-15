#!/usr/bin/env python3
"""Main entry point for the web crawler agent.

This module uses the observability system for structured logging and tracing.
The observability decorators handle automatic instrumentation of all components.
"""
import argparse
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Load .env file before any other imports that use os.environ
from dotenv import load_dotenv

load_dotenv()

from src.agents.main_agent import MainAgent
from src.core.browser import BrowserSession
from src.core.config import AppConfig
from src.core.llm import LLMClient, LLMClientFactory

# Observability imports
from src.observability.config import (
    ObservabilityConfig,
    initialize_observability,
    shutdown,
)
from src.observability.context import ObservabilityContext, get_or_create_context, set_context
from src.observability.emitters import emit_error, emit_info, emit_warning
from src.observability.handlers import OTelConfig, OTelGrpcHandler
from src.tools.memory import MemoryStore


@dataclass
class CliArgs:
    """Parsed command-line arguments."""
    url: str | None
    log_level: str
    multi_model: bool
    list_models: bool


def parse_arguments() -> CliArgs:
    """Parse command-line arguments."""
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

    return CliArgs(
        url=args.url,
        log_level=args.log_level,
        multi_model=args.multi_model,
        list_models=args.list_models
    )


def list_available_models() -> int:
    """Print available models and exit."""
    from src.core.component_models import ComponentModelConfig
    from src.core.default_models import get_default_registry

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


def setup_logging(level: str) -> logging.Logger:
    """Configure logging and return the logger."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger(__name__)


def setup_observability() -> ObservabilityContext:
    """Initialize the observability system and return the root context."""
    otel_endpoint = os.environ.get("OTEL_ENDPOINT", "localhost:4317")
    otel_insecure = os.environ.get("OTEL_INSECURE", "true").lower() == "true"
    service_name = os.environ.get("SERVICE_NAME", "crawler-agent")

    otel_handler = OTelGrpcHandler(OTelConfig(
        endpoint=otel_endpoint,
        insecure=otel_insecure,
        service_name=service_name,
    ))

    obs_config = ObservabilityConfig(
        service_name=service_name,
        otel_endpoint=otel_endpoint,
        otel_insecure=otel_insecure,
    )

    initialize_observability(handler=otel_handler, config=obs_config)

    ctx = get_or_create_context("application")
    set_context(ctx)

    return ctx


def create_llm_client(
    app_config: AppConfig,
    multi_model: bool,
    ctx: ObservabilityContext,
    logger: logging.Logger
) -> tuple[LLMClient, LLMClientFactory | None]:
    """Create LLM client (single or factory-based)."""
    if multi_model:
        llm_factory = LLMClientFactory.from_env()
        llm = llm_factory.get_client("main_agent")
        logger.info(f"Multi-model mode: using factory with {len(llm_factory.registry)} models")
        emit_info(
            event="llm.factory.initialized",
            ctx=ctx,
            data={
                "mode": "multi-model",
                "model_count": len(llm_factory.registry),
                "main_agent_model": llm_factory.get_component_model("main_agent")
            }
        )
        return llm, llm_factory
    else:
        llm = LLMClient(app_config.openai)
        emit_info(
            event="llm.client.initialized",
            ctx=ctx,
            data={"mode": "legacy", "model": app_config.openai.model}
        )
        return llm, None


def run_crawler_workflow(
    url: str,
    app_config: AppConfig,
    llm: LLMClient,
    ctx: ObservabilityContext,
    logger: logging.Logger
) -> int:
    """Run the crawler workflow and return exit code."""
    output_dir = app_config.output.get_output_dir(url)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    browser_session = BrowserSession(app_config.browser)
    memory_store = MemoryStore()

    logger.info("Connecting to Chrome DevTools...")
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
        return _execute_agent(
            url=url,
            output_dir=output_dir,
            app_config=app_config,
            llm=llm,
            browser_session=browser_session,
            memory_store=memory_store,
            ctx=ctx,
            logger=logger
        )
    finally:
        browser_session.disconnect()
        emit_info(
            event="browser.disconnect",
            ctx=ctx,
            data={"message": "Disconnected from Chrome DevTools"}
        )


def _execute_agent(
    url: str,
    output_dir: Path,
    app_config: AppConfig,
    llm: LLMClient,
    browser_session: BrowserSession,
    memory_store: MemoryStore,
    ctx: ObservabilityContext,
    logger: logging.Logger
) -> int:
    """Execute the main agent and handle results."""
    agent = MainAgent(llm, browser_session, output_dir, memory_store)
    logger.info(f"Creating crawl plan for: {url}")

    result = agent.create_crawl_plan(url)

    if result["success"]:
        return _handle_success(result, output_dir, app_config, ctx, logger)
    else:
        return _handle_failure(result, ctx, logger)


def _handle_success(
    result: dict[str, Any],
    output_dir: Path,
    app_config: AppConfig,
    ctx: ObservabilityContext,
    logger: logging.Logger
) -> int:
    """Handle successful crawl plan creation."""
    logger.info("Crawl plan created successfully")
    logger.info(f"Result: {result['result']}")

    if app_config.output.template_dir and app_config.output.template_dir.exists():
        logger.info(f"Copying templates from: {app_config.output.template_dir}")
        shutil.copytree(
            app_config.output.template_dir,
            output_dir,
            dirs_exist_ok=True
        )

    logger.info(f"Output files written to: {output_dir}")
    emit_info(
        event="application.complete",
        ctx=ctx,
        data={"output_dir": str(output_dir), "success": True},
        tags=["application", "success"]
    )
    return 0


def _handle_failure(
    result: dict[str, Any],
    ctx: ObservabilityContext,
    logger: logging.Logger
) -> int:
    """Handle failed crawl plan creation."""
    logger.error(f"Failed to create plan: {result.get('error')}")
    emit_error(
        event="application.failed",
        ctx=ctx,
        data={"error": result.get("error"), "success": False},
        tags=["application", "failure"]
    )
    return 1


def main() -> int:
    """Main entry point."""
    args = parse_arguments()

    if args.list_models:
        return list_available_models()

    if not args.url:
        print("Error: url is required", file=sys.stderr)
        return 1

    logger = setup_logging(args.log_level)
    ctx = setup_observability()

    emit_info(
        event="application.start",
        ctx=ctx,
        data={"target_url": args.url, "log_level": args.log_level},
        tags=["application", "startup"]
    )

    try:
        app_config = AppConfig.from_env()
        logger.info(f"Using model: {app_config.openai.model}")
        emit_info(
            event="config.loaded",
            ctx=ctx,
            data={"model": app_config.openai.model}
        )

        llm, _ = create_llm_client(app_config, args.multi_model, ctx, logger)

        return run_crawler_workflow(
            url=args.url,
            app_config=app_config,
            llm=llm,
            ctx=ctx,
            logger=logger
        )

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        emit_warning(
            event="application.interrupted",
            ctx=ctx,
            data={"message": "Interrupted by user"},
            tags=["application", "interrupted"]
        )
        return 130
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
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
        shutdown()


if __name__ == "__main__":
    sys.exit(main())
