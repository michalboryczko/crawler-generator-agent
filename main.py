#!/usr/bin/env python3
"""Main entry point for the web crawler agent."""
import argparse
import logging
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
        "--output", "-o",
        help="Output file for crawl plan (default: stdout)"
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

        # Initialize components
        llm = LLMClient(config.openai)
        browser_session = BrowserSession(config.browser)
        memory_store = MemoryStore()

        # Connect to browser
        logger.info("Connecting to Chrome DevTools...")
        browser_session.connect()

        try:
            # Create and run main agent
            agent = MainAgent(llm, browser_session, memory_store)
            logger.info(f"Creating crawl plan for: {args.url}")

            result = agent.create_crawl_plan(args.url)

            if result["success"]:
                plan = result["result"]

                if args.output:
                    with open(args.output, "w") as f:
                        f.write(plan)
                    logger.info(f"Plan written to: {args.output}")
                else:
                    print("\n" + "=" * 60)
                    print(plan)
                    print("=" * 60)

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
