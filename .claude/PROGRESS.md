# Project Progress: Self-Creating Web Crawler Agent

## Status Dashboard
| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1-7: Core Implementation | ✅ Complete | 100% |
| Phase 8: Selector Agent Refactoring | ✅ Complete | 100% |

## Phase 8: Selector Agent Refactoring

### Problem Statement
The selector agent doesn't properly implement the sampling logic:
1. Hardcoded 5 listing pages / 5 article pages instead of dynamic sampling
2. Not grouping URLs by pattern
3. Not using isolated contexts per page
4. Relies on prompt instructions which LLM often ignores

### Solution: LLM-Based Sampling Tools

#### Tool 1: ListingPagesGeneratorTool ✅
- [x] Input: target_url, max_pages, pagination_links (for pattern detection)
- [x] Logic: LLM detects pagination URL pattern (page vs offset vs path), calculates 2% of pages (min 5, max 20)
- [x] Output: List of listing page URLs with detected pagination pattern
- File: `src/tools/selector_sampling.py`

#### Tool 2: ArticlePagesGeneratorTool ✅
- [x] Input: All collected article URLs
- [x] Logic: Group by URL pattern, sample 20% per group (min 3)
- [x] Output: List of article URLs to visit, grouped by pattern
- File: `src/tools/selector_sampling.py`

#### Tool 3: ListingPageExtractorTool ✅
- [x] Input: Listing page URL
- [x] Logic: Fresh LLM context, navigate, extract selectors + article URLs
- [x] Output: Selectors found, article URLs extracted
- File: `src/tools/selector_extraction.py`

#### Tool 4: ArticlePageExtractorTool ✅
- [x] Input: Article URL
- [x] Logic: Fresh LLM context, navigate, extract detail selectors
- [x] Output: Detail selectors found on this page
- File: `src/tools/selector_extraction.py`

#### Tool 5: SelectorAggregatorTool ✅
- [x] Input: All listing selectors, all detail selectors
- [x] Logic: Creates SELECTOR CHAINS - ordered lists of ALL working selectors (not just one!)
- [x] Output: Selector chains where crawler tries each in order until match
- File: `src/tools/selector_extraction.py`

#### SelectorAgent Updated ✅
- [x] Replaced old prompt-based workflow with tool-based orchestration
- [x] Now uses 5 new tools instead of browser + selector tools
- File: `src/agents/selector_agent.py`

### Simplified Selector Agent Workflow
1. Read target_url and pagination_max_pages from memory
2. Call ListingPagesGeneratorTool → get listing URLs
3. For each listing URL: call ListingPageExtractorTool
4. Collect all article URLs from extractions
5. Call ArticlePagesGeneratorTool → get sample article URLs
6. For each article URL: call ArticlePageExtractorTool
7. Call SelectorAggregatorTool → get final selectors
8. Store results in memory

---

## Session Log

### 2025-12-11 - Selector Agent Refactoring
- Analyzed current issues with selector agent
- Designed 5 new LLM-based tools to encapsulate sampling logic
- Implemented all 5 tools:
  - ListingPagesGeneratorTool (LLM-based pagination pattern detection)
  - ArticlePagesGeneratorTool (LLM-based URL pattern grouping)
  - ListingPageExtractorTool (isolated context extraction)
  - ArticlePageExtractorTool (isolated context extraction)
  - SelectorAggregatorTool (creates selector chains with all working selectors)
- Updated SelectorAgent to use new tools
- Phase 8 complete - ready for testing

### 2025-12-11 - Pagination & Selector Chain Improvements
- Updated ListingPagesGeneratorTool to use LLM for pagination pattern detection
  - Now handles page-based (?page=N), offset-based (?offset=N), and other patterns
  - Analyzes sample pagination links to detect the pattern
- Updated SelectorAggregatorTool to preserve ALL working selectors as chains
  - Instead of picking ONE best selector, creates ordered list of all that worked
  - Crawler can try selectors in order until one matches
  - Handles sites with different page structures
- Updated BrowserAgent to store pagination_links for pattern detection

### 2025-12-11 - Dynamic Plan Generation from Discovered Fields
- Updated plan_generator.py to dynamically build output based on discovered fields
- **Goal Section**: Now lists all discovered fields (title, date, files, attachments, etc.)
- **Data Model**: JSON example built dynamically from detail_selectors
- **Config Section**: Uses selector chains format (arrays of selectors to try in order)
- **Detail Section**: Shows selector chains with priority and success rate
- **Test Plan**: Article expected fields match discovered selectors
- Supports new fields like: files, attachments, breadcrumbs, tags, related_articles, images

### 2025-12-11 - Fixed Article URL Collection Bug
- **Problem**: batch_extract_listings reported 28 URLs but only 4 were available for article fetching
- **Root Causes**:
  1. LLM-reported `article_count` didn't match actual `article_urls` array length
  2. Logging showed misleading counts from LLM responses
  3. Data prep agent prompt wasn't clear about reading URLs AFTER batch extraction
- **Fixes Applied**:
  1. `RunListingExtractionAgentTool`: Now uses actual URL count, not LLM-reported count
  2. Added detailed logging showing sample URLs extracted from each page
  3. `BatchExtractListingsTool`: Added per-page logging of URLs yielded
  4. Improved extraction prompt to emphasize complete URL array is required
  5. Updated data prep agent prompt to read URLs IMMEDIATELY after batch extraction
  6. Added `article_urls_sample` in batch result for debugging

### 2025-12-11 - Focused Content Extraction for LLM (Major Fix)
- **Problem**: LLM was returning same 4 URLs for ALL listing pages regardless of ?start= offset
  - Sample URLs were identical across pages: always recent/featured articles
  - LLM was extracting from header/sidebar instead of main content
- **Solution**: Two-pronged approach (keeping LLM for extraction)
  1. **Extract main content container first** (`_extract_main_content()`)
     - Derives container selector from article selector (e.g., `ul.teasers li > a` -> `ul.teasers`)
     - Uses BeautifulSoup to extract just that container's HTML
     - Sends focused HTML to LLM (smaller, no header/footer noise)
  2. **Improved LLM prompt** (`_extract_urls_with_llm()`)
     - Explicit list of sections to SKIP: header, nav, sidebar, featured, popular, footer
     - Emphasizes "main repeating list" that changes with pagination
     - Clearer instruction about the CSS selector to use
  3. Added beautifulsoup4 to pyproject.toml dependencies
- **Why this works**: By sending only the main content container to LLM, we eliminate
  header/sidebar articles that were confusing it. LLM still does the extraction.

### 2025-12-11 - Dynamic Article Extraction Fields
- **Problem**: `RunExtractionAgentTool` had hardcoded fields (title, date, authors, content)
  - Didn't use discovered fields like files, attachments, breadcrumbs, tags
  - Test data wouldn't include dynamically discovered fields
- **Solution**: Added `_build_extraction_prompt()` method
  - Reads `detail_selectors` from memory to get discovered fields
  - Builds dynamic JSON example with appropriate type hints per field:
    - authors/tags: `["value1", "value2"]`
    - files/attachments/images: `[{"url": "...", "title": "..."}]`
    - breadcrumbs: `["Home", "Section", "Article"]`
    - others: `"field value or null"`
  - Includes CSS selector hints for each field
  - Falls back to default fields if no selectors discovered

### 2025-12-11 - Listing Container Selector Discovery and Usage
- **Problem**: LLM was extracting articles from headers/sidebars instead of main listing
- **Solution**: Discover and store `listing_container_selector` to focus extraction

  **Changes to Selector Agent Flow:**
  1. Updated `LISTING_EXTRACTION_PROMPT` to discover `listing_container` selector
     - New field in output: selector for main content area (e.g., `main`, `div.content`)
     - Also discovers `article_list` selector (e.g., `ul.articles`)
  2. `ListingPageExtractorTool` now accepts optional `listing_container_selector`
     - After first page discovers container, subsequent pages use it to focus HTML
     - Added `_extract_container()` method using BeautifulSoup
  3. Updated selector agent prompt to store `listing_container_selector` in memory
  4. `SelectorAggregatorTool` already aggregates all selectors including container

  **Changes to Data Prep Agent:**
  1. `RunListingExtractionAgentTool` now reads `listing_container_selector` from memory
     - Uses it to extract just the container HTML before sending to LLM
     - Simplified `_extract_main_content()` to use selector directly

  **Changes to Plan Generator:**
  1. Added new section "3.1. Main content container" explaining the container selector
  2. Updated config to include `container_selector` in listing section
  3. Added note about using container_selector first to narrow DOM

  **Test Data:** Full HTML still stored in `given` field (not just container)
  so crawler implementation can be tested against real pages

### 2025-12-11 - Fix Selector Agent URL Extraction (Session 2)
- **Problem**: Selector agent extracted 0 article URLs from all 20 listing pages
  - LLM found selectors (listing_container, article_link, etc.) but returned empty article_urls
  - `article_selector` and `listing_container_selector` were never stored (None)
  - Data prep agent fell back to extracting same 3 URLs from headers

- **Root Causes**:
  1. `LISTING_EXTRACTION_PROMPT` emphasized selectors over URL extraction
  2. LLM treated URL extraction as secondary task, often skipping it
  3. Selector agent prompt didn't explicitly show how to extract primary selectors from chains
  4. No validation warning when LLM returns too few URLs

- **Fixes Applied**:
  1. **Rewrote `LISTING_EXTRACTION_PROMPT`** in `selector_extraction.py`:
     - Made URL extraction the PRIMARY task (emphasized at top of prompt)
     - Added explicit "expect 10-30 URLs" guidance
     - Added CRITICAL note that article_urls must contain actual URLs, not placeholders
     - Restructured JSON with article_urls FIRST

  2. **Added URL validation** in `ListingPageExtractorTool`:
     - Warns when fewer than 5 URLs extracted
     - Converts relative URLs to absolute using `urljoin`
     - Filters out placeholder "..." entries
     - Logs sample URLs for debugging

  3. **Improved `SELECTOR_AGENT_PROMPT`** in `selector_agent.py`:
     - Explicit Step 7 showing SEPARATE memory_write calls for each key
     - Shows exact syntax: `listing_selectors["listing_container"][0]["selector"]`
     - Added fallback instruction: store selectors even if URLs are empty
     - Clearer workflow with emphasis on COLLECTING article_urls from each page

  4. **Improved `RunListingExtractionAgentTool`** in `extraction.py`:
     - Added explicit logging of `listing_container_selector` value
     - Added `_derive_container_from_article_selector()` fallback method
       - If no container selector, derives from article selector (e.g., "ul.teasers li a" -> "ul.teasers")
     - Added warning log when no selectors available
     - Improved LLM extraction prompt:
       - Emphasized "different pages have DIFFERENT articles"
       - Explicit note that ?start= parameter means different content
       - Clearer sections for what to skip vs extract
       - Warning that <5 URLs means wrong section extracted

---

## Phase 9: Structured Logging Architecture

### Status Dashboard
| Phase | Status | Progress |
|-------|--------|----------|
| Phase 9.1: Foundation (MVP) | ✅ Complete | 100% |
| Phase 9.2: Enhanced (Tools) | ✅ Complete | 100% |
| Phase 9.3: Production | ✅ Complete | 100% |
| Phase 9.4: Visualization + Jaeger | ✅ Complete | 100% |

### Phase 9.1: Foundation (MVP) - Core Infrastructure ✅ COMPLETE
#### Files Created
- [x] `src/core/structured_logger.py` - Core classes (LogEntry, TraceContext, StructuredLogger)
- [x] `src/core/log_outputs.py` - Output implementations (JSONLines, Console, Async, OTel)
- [x] `src/core/log_context.py` - Context propagation (ContextVar, span manager)
- [x] `src/core/log_config.py` - Configuration dataclass with MODEL_COSTS

#### Files Modified
- [x] `main.py` - Initialize LoggerManager, dual logging (legacy + structured)
- [x] `src/core/llm.py` - LLM metrics logging (tokens, cost, latency, tool calls)
- [x] `src/agents/base.py` - Agent lifecycle + tool execution logging

### Phase 9.2: Enhanced (Tool Coverage) ✅ COMPLETE
#### Files Modified
- [x] `src/tools/browser.py` - Browser operation logging
- [x] `src/tools/memory.py` - Memory operation logging
- [x] `src/tools/extraction.py` - Extraction logging with batch progress
- [x] `src/tools/selector_extraction.py` - Selector discovery logging
- [x] `src/tools/selector_sampling.py` - Sampling decision logging
- [x] `src/tools/orchestration.py` - Sub-agent invocation logging
- [x] `src/agents/main_agent.py` - Workflow logging (create_crawl_plan)

### Phase 9.3: Production ✅ COMPLETE
#### Features Implemented
- [x] Environment-based configuration (LOG_LEVEL, LOG_CONSOLE, LOG_JSONL, LOG_OTEL, etc.)
- [x] Async buffered writing (AsyncBufferedOutput with configurable buffer/flush)
- [x] OpenTelemetry OTLP exporter (real implementation with BatchSpanProcessor)
- [x] PII redaction patterns configured (redact_pii, redact_patterns in LoggingConfig)
- [x] python-dotenv integration for .env file loading

### Phase 9.4: Visualization + Jaeger ✅ COMPLETE
#### Infrastructure Files Created
- [x] `docker-compose.logging.yml` - Full stack: Elasticsearch, Kibana, OTel Collector, Jaeger
- [x] `docker-compose.logging-minimal.yml` - Lightweight: Elasticsearch, Kibana only
- [x] `infra/otel-collector-config.yaml` - OTel Collector with OTLP receivers, Jaeger exporter
- [x] `infra/es-index-template.sh` - Elasticsearch index template for crawler-logs-*
- [x] `infra/kibana-dashboard.ndjson` - Pre-built dashboard with 8 visualizations
- [x] `infra/setup-kibana.sh` - Auto-import script for dashboard and data views

#### Documentation
- [x] `docs/logging-readme.md` - User manual for Kibana, Jaeger, and OTel Collector

### Key Architecture Decisions
1. **OpenTelemetry-compatible schema** - JSON Lines output compatible with OTel
2. **Context propagation via ContextVars** - Thread-safe context for async operations
3. **Trace hierarchy**: session_id → request_id → trace_id → span_id with parent relationships
4. **Dual output**: Console (human-readable) + JSONL (machine-parseable)
5. **Cost estimation**: Track token usage and calculate API costs per model
6. **PII redaction**: Configurable patterns for sensitive data removal

### Highest Risk Items
1. **Context propagation across agents** - Ensure trace context flows through nested agent calls
2. **Performance impact** - JSON serialization on every log entry
3. **Large content truncation** - Balance log completeness vs storage/performance

### 2025-12-12 - Logging Architecture Implementation Start
- Read complete logging-architecture-plan.md (3000+ lines)
- Created tracking structure (.claude/checkpoints, .claude/logs)
- Starting Phase 9.1 implementation

### 2025-12-12 - Phase 9.1 Foundation Complete
- **Created 4 core logging modules:**
  - `structured_logger.py`: LogLevel, LogLevelDetail, EventCategory, TraceContext, LogEvent, LogMetrics, LogEntry, LogOutput ABC, StructuredLogger
  - `log_outputs.py`: JSONLinesOutput, ConsoleOutput (colored), AsyncBufferedOutput, OpenTelemetryOutput, CompositeOutput
  - `log_context.py`: ContextVar-based propagation, get_logger(), set_logger(), span() context manager, LoggerManager singleton, with_span decorator
  - `log_config.py`: LoggingConfig dataclass, from_env(), development/production/testing presets, MODEL_COSTS, estimate_cost()

- **Modified core files:**
  - `main.py`: Initializes both legacy logging and structured logging, logs application lifecycle events
  - `llm.py`: LLM call start/complete events with token counts, cost estimation, duration, tool calls
  - `base.py`: Agent lifecycle (start/complete/error), iteration logging, tool execution with timing

- **Verified**: All syntax checks pass, imports validated

### 2025-12-13 - Phase 9.2-9.4 Complete + OpenTelemetry Implementation
- **Added structured logging to tools:**
  - `orchestration.py`: RunSelectorAgentTool, RunAccessibilityAgentTool, RunDataPrepAgentTool
  - `selector_sampling.py`: ListingPagesGeneratorTool, ArticlePagesGeneratorTool
  - `selector_extraction.py`: ListingPageExtractorTool, ArticlePageExtractorTool, SelectorAggregatorTool
  - `main_agent.py`: create_crawl_plan() workflow logging

- **Fixed infrastructure issues:**
  - Docker Elasticsearch disk watermark error - added `cluster.routing.allocation.disk.threshold_enabled=false`
  - .env file not loading - added python-dotenv dependency and load_dotenv() in main.py

- **Implemented OpenTelemetry OTLP exporter:**
  - Full implementation in `log_outputs.py` replacing stub
  - Uses BatchSpanProcessor for efficient export
  - Converts LogEntry to OTel spans with proper trace/span ID conversion
  - Added opentelemetry-sdk and opentelemetry-exporter-otlp-proto-grpc dependencies

- **Created Kibana dashboard setup:**
  - `infra/kibana-dashboard.ndjson`: Pre-built dashboard with data view, searches, visualizations
  - `infra/setup-kibana.sh`: Auto-import script

- **Updated documentation:**
  - `docs/logging-readme.md`: User manual for Kibana, Jaeger, OTel Collector
  - Updated MODEL_COSTS with December 2025 OpenAI pricing
