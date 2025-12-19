# Web Crawler Architecture Blueprint

A reference architecture for building production-ready web crawlers that extract structured data from paginated listing sites.

---

## Core Concepts

### 1. Two-Phase Crawling

Separate the crawl into distinct phases for better control and resumability:

```
Phase 1: URL Collection
├── Traverse listing pages
├── Extract detail page URLs
├── Handle pagination
└── Deduplicate URLs

Phase 2: Data Extraction
├── Fetch each detail page
├── Extract structured fields
├── Validate/normalize data
└── Persist results
```

**Benefits:**
- Can checkpoint between phases
- Easier to resume interrupted crawls
- Can parallelize Phase 2 independently
- Allows manual review of collected URLs before extraction

---

### 2. Configuration-Driven Selectors

Externalize all CSS selectors and patterns into configuration rather than hardcoding:

```yaml
selectors:
  listing:
    items: "ul.results li"           # Container for each item
    link: "a.item-link"              # Link to detail page

  detail:
    title: "h1, .title"              # Comma = fallback chain
    author: ".author, .byline"
    date: "time, .date"

  pagination:
    next: ".pagination .next"
    pattern: "?page={n}"
```

**Design principles:**
- **Fallback chains**: Use comma-separated selectors for robustness across page variants
- **First-match wins**: Try selectors in order, use first successful match
- **Graceful degradation**: Missing fields → null, not errors

---

### 3. Rate Limiting & Politeness

Implement respectful crawling to avoid overloading target servers:

```
┌─────────────────────────────────────────┐
│           Request Pipeline              │
├─────────────────────────────────────────┤
│  Request → Rate Limiter → HTTP Client   │
│              ↓                          │
│         Wait if needed                  │
│              ↓                          │
│         Retry on failure                │
│              ↓                          │
│         Response                        │
└─────────────────────────────────────────┘
```

**Key parameters:**
| Parameter | Purpose | Typical Value |
|-----------|---------|---------------|
| `min_delay` | Minimum seconds between requests | 1-2s |
| `max_retries` | Retry count for transient failures | 3 |
| `backoff_factor` | Exponential backoff multiplier | 2.0 |
| `timeout` | Request timeout | 30s |

---

### 4. State Management & Resume

Persist crawl state to enable resuming after interruption:

```
State Components:
├── seen_urls: Set[str]      # Already processed URLs
├── pending_urls: List[str]  # URLs queued for processing
├── last_offset: int         # Pagination position
├── processed_count: int     # Progress tracking
└── error_count: int         # Error tracking
```

**Resume strategy:**
1. On start: Check for existing state file
2. If exists: Load state, skip seen URLs, continue from last offset
3. During crawl: Periodically checkpoint state (every N items)
4. On graceful shutdown: Save final state
5. On completion: Optionally archive/clear state

---

### 5. Output Formats

**JSON Lines (JSONL)** - Recommended for crawling:
```json
{"url": "...", "title": "...", "extracted_at": "..."}
{"url": "...", "title": "...", "extracted_at": "..."}
```

**Advantages:**
- Append-only (safe for incremental writes)
- Stream-processable (no need to load entire file)
- Easy to resume (just append new records)
- Simple to convert to other formats post-crawl

**Post-crawl export options:**
- JSON array (for APIs)
- CSV (for spreadsheets)
- SQLite (for querying)

---

### 6. Error Handling Strategy

```
Error Categories:
├── Transient (retry)
│   ├── Timeout
│   ├── Connection error
│   └── 5xx responses
│
├── Permanent (skip + log)
│   ├── 404 Not Found
│   ├── 403 Forbidden
│   └── Parse errors
│
└── Fatal (abort)
    ├── Rate limited (429)
    └── Configuration errors
```

**Per-record error tracking:**
```json
{
  "url": "https://example.com/item",
  "title": "Found Title",
  "author": null,
  "extraction_errors": ["Author selector matched no elements"]
}
```

---

### 7. CLI Interface Pattern

Provide intuitive commands for common operations:

```bash
# Primary command: Start/resume crawl
crawler crawl [--resume] [--max-items N] [--delay S]

# Status: Show progress and statistics
crawler status

# Export: Convert output format
crawler export --format {json,csv}

# Clear: Reset state for fresh start
crawler clear [--force]
```

**Progress display:**
```
Collecting URLs... ━━━━━━━━━━━━━━━━ 142 found
Extracting data... ━━━━━━━━━━━━━━━━ 45% 64/142 [00:32<00:40]
```

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  crawl | status | export | clear                             │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                      Orchestrator                            │
│  - Coordinates phases                                        │
│  - Manages state                                             │
│  - Handles signals (graceful shutdown)                       │
└───────────┬─────────────────────────────────┬────────────────┘
            │                                 │
┌───────────▼───────────┐       ┌─────────────▼────────────────┐
│   Listing Crawler     │       │     Detail Extractor         │
│   - Pagination        │       │     - Field extraction       │
│   - URL collection    │       │     - Data normalization     │
│   - Deduplication     │       │     - Validation             │
└───────────┬───────────┘       └─────────────┬────────────────┘
            │                                 │
            └─────────────┬───────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                     HTTP Client                              │
│  - Rate limiting                                             │
│  - Retry logic                                               │
│  - Connection pooling                                        │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────────┐
│                      Storage                                 │
│  - JSONL output                                              │
│  - State persistence                                         │
│  - Seen URL tracking                                         │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Model Template

```python
@dataclass
class ExtractedItem:
    # Required
    url: str
    extracted_at: datetime

    # Common fields (nullable)
    title: str | None
    description: str | None
    date: str | None

    # Multi-value fields
    authors: list[str]
    tags: list[str]
    links: list[str]

    # Metadata
    extraction_errors: list[str]
```

---

## Configuration Template

```python
@dataclass
class CrawlerConfig:
    # Target
    start_url: str
    base_url: str

    # Selectors
    listing_selectors: ListingSelectors
    detail_selectors: DetailSelectors
    pagination: PaginationConfig

    # Limits
    max_pages: int | None
    max_items: int | None

    # Request settings
    delay_seconds: float
    timeout_seconds: float
    max_retries: int
    user_agent: str

    # Output
    output_dir: Path
    output_format: str
    checkpoint_interval: int
```

---

## Pagination Patterns

### Pattern A: Next Button
```python
# Find and follow "Next" link until exhausted
next_link = page.select_one(".pagination .next")
if next_link:
    next_url = next_link["href"]
```

### Pattern B: Offset Parameter
```python
# Increment offset parameter
# ?start=0 → ?start=12 → ?start=24
current_offset += items_per_page
next_url = f"{base_url}?start={current_offset}"
```

### Pattern C: Page Numbers
```python
# Increment page number
# ?page=1 → ?page=2 → ?page=3
current_page += 1
next_url = f"{base_url}?page={current_page}"
```

### Pattern D: Cursor/Token
```python
# Use cursor from response for next page
next_cursor = response.get("next_cursor")
next_url = f"{base_url}?cursor={next_cursor}"
```

---

## Selector Robustness Strategies

### 1. Fallback Chains
```css
/* Try multiple selectors in priority order */
h1.title, .article-title, main h1, h1
```

### 2. Attribute Selectors
```css
/* More stable than class names */
a[href*="/article/"]
time[datetime]
[data-testid="author-name"]
```

### 3. Structural Selectors
```css
/* Based on document structure */
article > header > h1
main section:first-child p
```

### 4. Content-Based (last resort)
```python
# Match by text content when structure fails
element = soup.find(string=re.compile(r"Author:"))
```

---

## Checklist for New Crawlers

- [ ] Analyze target site structure (listing + detail pages)
- [ ] Identify pagination pattern
- [ ] Define data schema (required vs optional fields)
- [ ] Configure selectors with fallbacks
- [ ] Set appropriate rate limits
- [ ] Test with small sample (--max-items 5)
- [ ] Verify extraction across page variants
- [ ] Test resume functionality
- [ ] Test graceful shutdown (Ctrl+C)
- [ ] Validate output format
