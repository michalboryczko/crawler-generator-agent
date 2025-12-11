# Crawler Agent

Self-creating web crawler agent that uses AI to analyze websites and generate crawling plans.

## Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install with locked versions (recommended)
pip install -r requirements.lock

# Or install with flexible versions
pip install -e ".[dev]"
```

## Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Required variables:
- `OPENAI_API_KEY` - Your OpenAI API key

Optional variables:
- `OPENAI_MODEL` - Model to use (default: gpt-5.1)
- `OPENAI_TEMPERATURE` - Temperature (default: 0.0)
- `CDP_HOST` - Chrome DevTools host (default: localhost)
- `CDP_PORT` - Chrome DevTools port (default: 9222)

## Running Chrome with DevTools

Start Chrome with remote debugging enabled:

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Or use a dedicated profile
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
```

## Usage

```bash
# Activate venv
source .venv/bin/activate

# Run the crawler agent
python main.py https://example.com/blog

# Save output to file
python main.py https://example.com/blog -o crawl-plan.md

# Enable debug logging
python main.py https://example.com/blog -l DEBUG
```

## Architecture

```
src/
├── core/           # Configuration, LLM client, browser CDP client
├── tools/          # Tool implementations (memory, browser, selector)
└── agents/         # Agent implementations
    ├── browser_agent.py   # Navigates and extracts links
    ├── selector_agent.py  # Finds CSS selectors
    └── main_agent.py      # Orchestrates the workflow
```

## Development

```bash
# Run linter
ruff check src/

# Run tests
pytest
```
