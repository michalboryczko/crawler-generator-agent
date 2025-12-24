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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.result import AgentResult
    from src.services.context_service import ContextService

from dotenv import load_dotenv

from src.agents.main_agent import MainAgent
from src.core.browser import BrowserSession
from src.core.config import AppConfig
from src.core.llm import LLMClientFactory

# Observability imports
from src.infrastructure import Container, init_container
from src.observability.config import (
    ObservabilityConfig,
    initialize_observability,
    shutdown,
)
from src.observability.context import ObservabilityContext, get_or_create_context, set_context
from src.observability.emitters import emit_error, emit_info, emit_warning
from src.observability.handlers import OTelConfig, OTelGrpcHandler
from src.services import SessionService


@dataclass
class CliArgs:
    """Parsed command-line arguments."""

    url: str | None
    log_level: str
    multi_model: bool
    list_models: bool
    env_file: str
    devtools_url: str | None
    # Session replay options
    resume: str | None
    copy_from: str | None
    overwrite_at: int | None
    up_to: int | None


def parse_arguments() -> CliArgs:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Create a web crawler plan for a given URL")
    parser.add_argument("url", nargs="?", help="Target URL to analyze")
    parser.add_argument(
        "--log-level",
        "-l",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--multi-model",
        "-m",
        action="store_true",
        help="Enable multi-model mode (use LLMClientFactory with per-component models)",
    )
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")
    parser.add_argument(
        "--env-file", "-e", default=".env", help="Path to .env file (default: .env)"
    )
    parser.add_argument(
        "--devtools-url",
        "-d",
        default=None,
        help="Chrome DevTools WebSocket URL (e.g., ws://localhost:9222). Overrides CDP_URL env var",
    )
    # Session replay options
    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument(
        "--resume",
        "-r",
        default=None,
        metavar="SESSION_ID",
        help="Resume from a previous session (continue from last context point)",
    )
    session_group.add_argument(
        "--copy",
        "-c",
        default=None,
        metavar="SESSION_ID",
        dest="copy_from",
        help="Copy context from a previous session to a new session",
    )
    parser.add_argument(
        "--overwrite-at",
        type=int,
        default=None,
        metavar="SEQUENCE",
        help="With --resume, erase context after this sequence number and continue (overwrite mode)",
    )
    parser.add_argument(
        "--up-to",
        type=int,
        default=None,
        metavar="SEQUENCE",
        help="With --copy, copy context only up to this sequence number (inclusive)",
    )
    args = parser.parse_args()

    return CliArgs(
        url=args.url,
        log_level=args.log_level,
        multi_model=args.multi_model,
        list_models=args.list_models,
        env_file=args.env_file,
        devtools_url=args.devtools_url,
        resume=args.resume,
        copy_from=args.copy_from,
        overwrite_at=args.overwrite_at,
        up_to=args.up_to,
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
        ],
    )
    return logging.getLogger(__name__)


def setup_observability() -> ObservabilityContext:
    """Initialize the observability system and return the root context."""
    otel_endpoint = os.environ.get("OTEL_ENDPOINT", "localhost:4317")
    otel_insecure = os.environ.get("OTEL_INSECURE", "true").lower() == "true"
    service_name = os.environ.get("SERVICE_NAME", "crawler-agent")

    otel_handler = OTelGrpcHandler(
        OTelConfig(
            endpoint=otel_endpoint,
            insecure=otel_insecure,
            service_name=service_name,
        )
    )

    obs_config = ObservabilityConfig(
        service_name=service_name,
        otel_endpoint=otel_endpoint,
        otel_insecure=otel_insecure,
    )

    initialize_observability(handler=otel_handler, config=obs_config)

    ctx = get_or_create_context("application")
    set_context(ctx)

    return ctx


def create_llm_factory(
    app_config: AppConfig, multi_model: bool, ctx: ObservabilityContext, logger: logging.Logger
) -> LLMClientFactory:
    """Create LLM client factory.

    Always returns a factory so each agent can get its own properly-named client.
    In legacy mode, creates a factory from the single OpenAI config.
    """
    if multi_model:
        llm_factory = LLMClientFactory.from_env()
        logger.info(f"Multi-model mode: using factory with {len(llm_factory.registry)} models")
        emit_info(
            event="llm.factory.initialized",
            ctx=ctx,
            data={
                "mode": "multi-model",
                "model_count": len(llm_factory.registry),
                "main_agent_model": llm_factory.get_component_model("main_agent"),
            },
        )
        return llm_factory
    else:
        # Create a factory from the single config so agents get proper component names
        llm_factory = LLMClientFactory.from_single_config(app_config.openai)
        logger.info(f"Legacy mode: using single model {app_config.openai.model}")
        emit_info(
            event="llm.factory.initialized",
            ctx=ctx,
            data={"mode": "legacy", "model": app_config.openai.model},
        )
        return llm_factory


def run_crawler_workflow(
    url: str,
    app_config: AppConfig,
    llm_factory: LLMClientFactory,
    ctx: ObservabilityContext,
    logger: logging.Logger,
    args: CliArgs,
) -> int:
    """Run the crawler workflow and return exit code."""
    output_dir = app_config.output.get_output_dir(url)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Determine session ID based on replay mode
    session_id = None
    if args.resume:
        session_id = args.resume
        logger.info(f"Resuming session: {session_id}")
    elif args.copy_from:
        logger.info(f"Copying context from session: {args.copy_from}")

    # Initialize DI container
    container = init_container(app_config.storage, session_id)
    logger.info(f"Storage backend: {app_config.storage.backend_type}")

    # Create session record to track this run (skip if resuming)
    session_service = container.session_service
    if not args.resume:
        session_service.create(
            session_id=container.session_id,
            target_site=url,
            output_dir=output_dir,
            agent_version=app_config.agent_version,
        )
    logger.info(f"Session ID: {container.session_id}")

    browser_session = BrowserSession(app_config.browser)

    logger.info("Connecting to Chrome DevTools...")
    emit_info(
        event="browser.connect.start", ctx=ctx, data={"message": "Connecting to Chrome DevTools..."}
    )
    browser_session.connect()
    emit_info(
        event="browser.connect.complete", ctx=ctx, data={"message": "Connected to Chrome DevTools"}
    )

    try:
        return _execute_agent(
            url=url,
            output_dir=output_dir,
            app_config=app_config,
            llm_factory=llm_factory,
            browser_session=browser_session,
            container=container,
            session_service=session_service,
            ctx=ctx,
            logger=logger,
            args=args,
        )
    finally:
        browser_session.disconnect()
        emit_info(
            event="browser.disconnect",
            ctx=ctx,
            data={"message": "Disconnected from Chrome DevTools"},
        )


def _setup_context_service(
    container: Container,
    args: CliArgs,
    logger: logging.Logger,
) -> "ContextService | None":
    """Set up context service based on session replay options.

    Args:
        container: DI container
        args: CLI arguments
        logger: Logger instance

    Returns:
        ContextService if context persistence is enabled, None otherwise
    """
    from src.services.context_service import ContextService

    if not container.context_persistence_enabled:
        return None

    context_repo = container.context_repository
    if context_repo is None:
        return None

    # Resume mode: continue from existing session
    if args.resume:
        # Find the main_agent instance from the resumed session
        instances = context_repo.get_instances_by_session(args.resume)
        main_instance = next((i for i in instances if i.agent_name == "main_agent"), None)

        if main_instance:
            logger.info(f"Found existing main_agent instance: {main_instance.id}")

            # Handle overwrite mode
            if args.overwrite_at is not None:
                context_svc = container.context_service("main_agent", instance_id=main_instance.id)
                deleted = context_svc.truncate_after_sequence(args.overwrite_at)
                logger.info(
                    f"Overwrite mode: deleted {deleted} events after sequence {args.overwrite_at}"
                )
                return context_svc

            # Resume mode: return existing context service
            return container.context_service("main_agent", instance_id=main_instance.id)
        else:
            logger.warning(f"No main_agent instance found in session {args.resume}, creating new")
            return container.context_service("main_agent")

    # Copy mode: copy context from another session to new session
    if args.copy_from:
        source_instances = context_repo.get_instances_by_session(args.copy_from)
        source_main = next((i for i in source_instances if i.agent_name == "main_agent"), None)

        if source_main:
            # Create new instance for current session
            context_svc = container.context_service("main_agent")
            source_svc = ContextService(context_repo, args.copy_from, source_main.id)

            # Copy events from source to new instance (optionally up to an event ID)
            copied = source_svc.copy_to_new_instance(
                target_session_id=container.session_id,
                target_instance_id=context_svc.instance_id,
                up_to_event_id=args.up_to,
            )
            if args.up_to:
                logger.info(
                    f"Copied {copied} events (up to id {args.up_to}) from session {args.copy_from}"
                )
            else:
                logger.info(f"Copied {copied} events from session {args.copy_from}")

            # Copy memory entries from source session
            # If --up-to specified, filter by the event's timestamp
            up_to_timestamp = None
            if args.up_to:
                event = context_repo.get_event(args.up_to)
                if event:
                    up_to_timestamp = event.created_at

            from src.services.memory_service import MemoryService

            memory_copied = MemoryService.copy_session_memory(
                repository=container.repository,
                source_session_id=args.copy_from,
                target_session_id=container.session_id,
                up_to_timestamp=up_to_timestamp,
            )
            if up_to_timestamp:
                logger.info(f"Copied {memory_copied} memory entries (up to {up_to_timestamp})")
            else:
                logger.info(f"Copied {memory_copied} memory entries from session {args.copy_from}")

            return context_svc
        else:
            logger.warning(f"No main_agent instance found in session {args.copy_from}")
            return container.context_service("main_agent")

    # Default: create new context service
    return container.context_service("main_agent")


def _execute_agent(
    url: str,
    output_dir: Path,
    app_config: AppConfig,
    llm_factory: LLMClientFactory,
    browser_session: BrowserSession,
    container: Container,
    session_service: "SessionService",
    ctx: ObservabilityContext,
    logger: logging.Logger,
    args: CliArgs,
) -> int:
    """Execute the main agent and handle results."""
    memory_service = container.memory_service("main_agent")

    # Handle context service for session replay
    context_service = None
    if container.context_persistence_enabled:
        context_service = _setup_context_service(container, args, logger)

    agent = MainAgent(
        llm_factory,
        browser_session,
        output_dir,
        memory_service,
        container=container,
        context_service=context_service,
    )
    logger.info(f"Creating crawl plan for: {url}")

    result = agent.create_crawl_plan(url)

    if result.success:
        return _handle_success(
            result, output_dir, app_config, container, session_service, ctx, logger
        )
    else:
        return _handle_failure(result, container, session_service, ctx, logger)


def _handle_success(
    result: "AgentResult",
    output_dir: Path,
    app_config: AppConfig,
    container: Container,
    session_service: "SessionService",
    ctx: ObservabilityContext,
    logger: logging.Logger,
) -> int:
    """Handle successful crawl plan creation."""
    logger.info("Crawl plan created successfully")
    logger.info(f"Result: {result.get('result', 'completed')}")

    if app_config.output.template_dir and app_config.output.template_dir.exists():
        logger.info(f"Copying templates from: {app_config.output.template_dir}")
        shutil.copytree(app_config.output.template_dir, output_dir, dirs_exist_ok=True)

    # Mark session as successful
    session_service.mark_success(container.session_id)

    logger.info(f"Output files written to: {output_dir}")
    emit_info(
        event="application.complete",
        ctx=ctx,
        data={"output_dir": str(output_dir), "success": True},
        tags=["application", "success"],
    )
    return 0


def _handle_failure(
    result: "AgentResult",
    container: Container,
    session_service: "SessionService",
    ctx: ObservabilityContext,
    logger: logging.Logger,
) -> int:
    """Handle failed crawl plan creation."""
    error_message = result.errors[0] if result.errors else "Unknown error"
    logger.error(f"Failed to create plan: {error_message}")

    # Mark session as failed
    session_service.mark_failed(container.session_id, str(error_message))

    emit_error(
        event="application.failed",
        ctx=ctx,
        data={"error": error_message, "success": False},
        tags=["application", "failure"],
    )
    return 1


def main() -> int:
    """Main entry point."""
    args = parse_arguments()

    # Load environment file (before any env var access)
    env_path = Path(args.env_file)
    if env_path.exists():
        load_dotenv(env_path)
    elif args.env_file != ".env":
        print(f"Error: env file not found: {args.env_file}", file=sys.stderr)
        return 1

    # CLI --devtools-url overrides CDP_URL env var
    if args.devtools_url:
        os.environ["CDP_URL"] = args.devtools_url

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
        tags=["application", "startup"],
    )

    try:
        app_config = AppConfig.from_env()
        logger.info(f"Using model: {app_config.openai.model}")
        emit_info(event="config.loaded", ctx=ctx, data={"model": app_config.openai.model})

        llm_factory = create_llm_factory(app_config, args.multi_model, ctx, logger)

        return run_crawler_workflow(
            url=args.url,
            app_config=app_config,
            llm_factory=llm_factory,
            ctx=ctx,
            logger=logger,
            args=args,
        )

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        emit_warning(
            event="application.interrupted",
            ctx=ctx,
            data={"message": "Interrupted by user"},
            tags=["application", "interrupted"],
        )
        return 130
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        emit_error(
            event="application.error",
            ctx=ctx,
            data={"error_type": type(e).__name__, "error_message": str(e)},
            tags=["application", "error", "unhandled"],
        )
        return 1
    finally:
        shutdown()


if __name__ == "__main__":
    sys.exit(main())
