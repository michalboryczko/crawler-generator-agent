# Crawler Agent

Self-creating web crawler agent that uses AI to analyze websites and generate crawling plans with test datasets.

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
- `OPENAI_MODEL` - Model to use (default: gpt-4o)
- `OPENAI_TEMPERATURE` - Temperature (default: 0.0)
- `CDP_HOST` - Chrome DevTools host (default: localhost)
- `CDP_PORT` - Chrome DevTools port (default: 9222)
- `PLANS_OUTPUT_DIR` - Output directory for plans (default: ./plans_output)
- `PLANS_TEMPLATE_DIR` - Template files to copy to output (optional)

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

# Enable debug logging
python main.py https://example.com/blog -l DEBUG
```

## Output

The agent generates output in `PLANS_OUTPUT_DIR/<site_name>/`:

```
plans_output/
└── example_com/
    ├── plan.md           # Crawl plan with selectors and strategy
    ├── test.md           # Test documentation
    └── data/
        └── test_set.jsonl  # Test dataset for validation
```

## Architecture

```
src/
├── core/
│   ├── config.py         # Configuration management
│   ├── llm.py            # OpenAI client wrapper
│   ├── browser.py        # Chrome DevTools Protocol client
│   └── html_cleaner.py   # HTML cleaning for LLM
├── tools/
│   ├── memory.py         # Shared memory + JSONL dump
│   ├── browser.py        # Navigate, click, query, wait
│   ├── selector.py       # Find and verify CSS selectors
│   ├── file.py           # File CRUD operations
│   ├── random_choice.py  # Random sampling
│   ├── http.py           # HTTP requests
│   └── orchestration.py  # Agent runner tools
└── agents/
    ├── browser_agent.py      # Page navigation and extraction
    ├── selector_agent.py     # CSS selector discovery
    ├── accessibility_agent.py # HTTP vs browser check
    ├── data_prep_agent.py    # Test dataset creation
    └── main_agent.py         # Workflow orchestrator
```

## Workflow

1. **Site Analysis**: Browser agent navigates and extracts article links
2. **Selector Discovery**: Selector agent finds reliable CSS selectors
3. **Accessibility Check**: Tests if site works without JavaScript
4. **Test Data Prep**: Samples pages and creates test dataset
5. **Documentation**: Generates plan.md and test.md

## Development

```bash
# Run linter
ruff check src/

# Run tests
pytest
```
