# Crawler Agent

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-412991?logo=openai)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An **autonomous**, **AI-native** web crawler agent that intelligently analyzes websites and automatically generates production-ready crawling plans with validation datasets. Powered by a **cutting-edge multi-agent orchestration architecture** to discover site structure, extract optimal CSS selectors, and prepare comprehensive test suites.

## Why Crawler Agent?

| Feature | Crawler Agent | Manual Planning | Generic Scrapers |
|---------|--------------|-----------------|------------------|
| Autonomous site discovery | Yes | No | No |
| AI-powered selector extraction | Yes | No | No |
| Auto-generated test datasets | Yes | No | No |
| Intelligent pagination handling | Yes | Manual | Partial |
| Multi-model orchestration | Yes | N/A | No |
| Enterprise observability | Yes | No | No |

### Key Benefits

- **Zero-Config AI Discovery** — Leverages state-of-the-art LLMs to autonomously analyze page structure, identify content patterns, and extract optimal CSS selectors without manual configuration.
- **Agentic Architecture** — Purpose-built specialized agents for discovery, selector extraction, accessibility validation, and test data preparation — each with isolated memory and explicit data contracts.
- **Contract-First Design** — JSON Schema-validated input/output contracts ensure type-safe, reliable inter-agent communication and seamless integration.
- **Multi-Model Orchestration** — Dynamically assign different LLM models to different agents and tools for cost optimization, latency tuning, or capability matching.
- **Enterprise-Grade Observability** — OpenTelemetry-native distributed tracing with structured logging, Elasticsearch-ready schemas, and full trace correlation.
- **Cloud-Native Storage** — Pluggable repository pattern with in-memory for rapid development and SQLAlchemy for production persistence (MySQL, PostgreSQL, SQLite).

## Current Limitations

> This project is in **active development**. Contributions welcome!

- **Listing-Items Focus** — Currently agent has been optimized for article-based sites with pagination
- **Requires Chrome DevTools** — Needs Chrome running with remote debugging enabled
- **Single-site focus** — Designed for analyzing one site at a time
- **No proxy support** — Does not handle IP rotation or geo-targeting
- **No authentication** — Cannot handle login-protected content
- **No JSON API discovery** — Only discovers HTML-based content, not REST/GraphQL APIs

## Quick Start

### Prerequisites

- Python 3.11+
- Chrome browser with remote debugging enabled
- OpenAI API key

### Installation

```bash
# Clone and setup
git clone <repo-url> && cd agent2
python3 -m venv .venv
source .venv/bin/activate

# Install with locked versions (recommended)
pip install -r requirements.lock

# Or install with flexible versions
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
```

### Running Chrome with DevTools

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# With dedicated profile (recommended)
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug
```

### Usage

```bash
# Activate venv
source .venv/bin/activate

# Analyze a website and generate crawl plan
python main.py https://example.com/blog

# Enable debug logging
python main.py https://example.com/blog -l DEBUG

# Use multi-model mode (per-agent model assignments)
python main.py https://example.com/blog --multi-model

# List available models
python main.py --list-models

# Use different env file
python main.py https://example.com/blog --env-file .env-gpt5.1

# Override DevTools URL
python main.py https://example.com/blog --devtools-url ws://localhost:9222
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

## Examples

See [`examples/`](examples/) for sample outputs including:

```
examples/
└── example_one/
    ├── plan.md              # Generated crawl plan
    └── extras/              # Reference docs for implementation
        ├── headfull-chrome.md
        ├── crawler-blueprint.md
        ├── logging-standards.md
        └── python-tips.md
```

### Using with AI Coding Assistants

The `extras/` folder contains reference documentation designed to be passed as context to AI coding assistants (Claude Code, Cursor, GitHub Copilot) when implementing a production crawler based on the generated plan:

```bash
# Pass plan + extras to Claude Code for implementation
claude "Implement a crawler based on examples/example_one/plan.md
        using patterns from examples/example_one/extras/"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (main.py)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Config    │  │ Observability│  │     Container       │  │
│  │  (AppConfig)│  │   (OTel)    │  │  (DI + Services)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    MainAgent                            ││
│  │              (Workflow Orchestrator)                    ││
│  └─────────────────────────────────────────────────────────┘│
│         │              │              │              │       │
│  ┌──────┴──────┐┌──────┴──────┐┌──────┴──────┐┌──────┴────┐│
│  │ Discovery   ││  Selector   ││Accessibility││ DataPrep  ││
│  │   Agent     ││   Agent     ││   Agent     ││  Agent    ││
│  │(Navigation) ││(CSS Finder) ││(HTTP Check) ││(Test Data)││
│  └─────────────┘└─────────────┘└─────────────┘└───────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                       Tools Layer                            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │  Browser   │ │  Memory    │ │  Selector  │ │   Plan   │ │
│  │   Tools    │ │   Tools    │ │   Tools    │ │  Tools   │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │ Extraction │ │   File     │ │Orchestration│ │  Agent   │ │
│  │   Tools    │ │   Tools    │ │   Tools    │ │  Tools   │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │LLMClient │  │ Browser  │  │ Memory   │  │  Session   │  │
│  │(OpenAI)  │  │ Session  │  │ Service  │  │  Service   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
│                      │                            │          │
│              ┌───────┴───────┐         ┌─────────┴────────┐│
│              │Chrome DevTools│         │    Repository    ││
│              │     (CDP)     │         │(InMem/SQLAlchemy)││
│              └───────────────┘         └──────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Component Descriptions

| Component | Purpose |
|-----------|---------|
| **MainAgent** | Orchestrates workflow: discovery, selector finding, accessibility check, data prep |
| **DiscoveryAgent** | Navigates pages, extracts links, identifies pagination patterns |
| **SelectorAgent** | Discovers and validates CSS selectors for listings and articles |
| **AccessibilityAgent** | Tests if site works without JavaScript via HTTP |
| **DataPrepAgent** | Samples pages and creates test datasets with extracted content |
| **Container** | Dependency injection for services and repositories |
| **MemoryService** | Isolated key-value storage per agent |
| **SessionService** | Tracks crawler runs with status and timing |

## Configuration

Copy `.env.example` to `.env` and configure:

### Required

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |

### Optional - Model Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_MODEL` | gpt-5.1 | Model for legacy mode |
| `OPENAI_TEMPERATURE` | 0.0 | Temperature setting |
| `DEFAULT_MODEL` | gpt-5.1 | Default model for multi-model mode |
| `MAIN_AGENT_MODEL` | - | Model for main orchestrator |
| `SELECTOR_AGENT_MODEL` | - | Model for selector discovery |

### Optional - Chrome DevTools

| Variable | Default | Description |
|----------|---------|-------------|
| `CDP_URL` | - | Full WebSocket URL (preferred) |
| `CDP_HOST` | localhost | DevTools host |
| `CDP_PORT` | 9222 | DevTools port |
| `CDP_TIMEOUT` | 30 | Connection timeout (seconds) |

### Optional - Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_BACKEND` | memory | Backend type: `memory` or `sqlalchemy` |
| `DATABASE_URL` | - | SQLAlchemy connection string |

### Optional - Output

| Variable | Default | Description |
|----------|---------|-------------|
| `PLANS_OUTPUT_DIR` | ./plans_output | Output directory for plans |
| `PLANS_TEMPLATE_DIR` | - | Template files to copy to output |
| `AGENT_VERSION` | 1.0.0 | Version identifier for tracking |

### Optional - Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Logging level |
| `SERVICE_NAME` | crawler-agent | Service name for tracing |
| `OTEL_ENDPOINT` | localhost:4317 | OpenTelemetry collector endpoint |
| `OTEL_INSECURE` | true | Use insecure gRPC connection |

## Workflow

```mermaid
sequenceDiagram
    participant User
    participant Main as MainAgent
    participant Discovery as DiscoveryAgent
    participant Selector as SelectorAgent
    participant Access as AccessibilityAgent
    participant DataPrep as DataPrepAgent
    participant Files as Output Files

    User->>Main: create_crawl_plan(url)

    Main->>Discovery: Extract article links & pagination
    Discovery-->>Main: AgentResult(links, pagination_type, max_pages)

    Main->>Selector: Find CSS selectors
    Selector-->>Main: AgentResult(listing_selectors, article_selectors)

    Main->>Access: Check HTTP accessibility
    Access-->>Main: AgentResult(http_accessible, requires_js)

    Main->>DataPrep: Create test dataset
    DataPrep-->>Main: AgentResult(listing_count, article_count)

    Main->>Files: Generate plan.md, test.md, test_set.jsonl
    Main-->>User: AgentResult(success, summary)
```

## Docker Setup (Optional)

For persistent storage with MySQL:

```bash
# Start MySQL container
docker-compose up -d mysql

# Run migrations
alembic upgrade head

# Set environment variables
export STORAGE_BACKEND=sqlalchemy
export DATABASE_URL=mysql+pymysql://crawler:crawler_password@localhost:3306/crawler

# Run the crawler
python main.py https://example.com/blog
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run tests
pytest

# Run tests with coverage
pytest --cov=src
```

## Roadmap

- [ ] Proxy support for IP rotation
- [ ] Authentication handling (login flows)
- [ ] Parallel agent execution
- [ ] WebSocket-based real-time updates
- [ ] Additional LLM provider support (Anthropic, Google)

## Related Projects

| Project | Description |
|---------|-------------|
| [Headfull-Chrome](https://github.com/michalboryczko/Headfull-chrome) | Cloud-native browser automation API with stealth-first design. Runs Chrome with real virtual display (Xvfb) for anti-bot resistance. Recommended for production crawlers implementing plans generated by this agent. |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT
