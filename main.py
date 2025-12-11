#!/usr/bin/env python3
"""Main entry point for the web crawler agent."""
import argparse
import logging
import shutil
import sys

from src.core.config import AppConfig
from src.core.llm import LLMClient
from src.core.browser import BrowserSession
from src.tools.memory import MemoryStore
from src.agents.main_agent import MainAgent


def setup_logging(level: str) -> None:
    """Configure logging."""
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

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        config = AppConfig.from_env()
        logger.info(f"Using model: {config.openai.model}")

        # Create output directory from URL
        output_dir = config.output.get_output_dir(args.url)
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")

        # Initialize components
        llm = LLMClient(config.openai)
        browser_session = BrowserSession(config.browser)
        memory_store = MemoryStore()

        # Connect to browser
        logger.info("Connecting to Chrome DevTools...")
        browser_session.connect()

        try:
            # Create and run main agent
            agent = MainAgent(llm, browser_session, output_dir, memory_store)
            logger.info(f"Creating crawl plan for: {args.url}")

            result = agent.create_crawl_plan(args.url)

            if result["success"]:
                logger.info("Crawl plan created successfully")
                logger.info(f"Result: {result['result']}")

                # Copy templates if configured
                if config.output.template_dir and config.output.template_dir.exists():
                    logger.info(f"Copying templates from: {config.output.template_dir}")
                    shutil.copytree(
                        config.output.template_dir,
                        output_dir,
                        dirs_exist_ok=True
                    )

                logger.info(f"Output files written to: {output_dir}")
                return 0
            else:
                logger.error(f"Failed to create plan: {result.get('error')}")
                return 1

        finally:
            browser_session.disconnect()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
