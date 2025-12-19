# Logging Standards for Crawlers

Language-agnostic logging practices for debugging, monitoring, and auditing web crawlers.

---

## Log Levels Guide

| Level | Use For | Examples |
|-------|---------|----------|
| `DEBUG` | Detailed diagnostic info | Selector matches, parsed values, request headers |
| `INFO` | Normal operation events | Page fetched, item extracted, checkpoint saved |
| `WARNING` | Unexpected but recoverable | Missing optional field, retry attempt, slow response |
| `ERROR` | Failures requiring attention | Parse failure, max retries exceeded, invalid data |
| `CRITICAL` | Crawl cannot continue | Rate limited (429), configuration error, auth failure |

---

## What to Log

### Phase 1: URL Collection

```
INFO  Starting URL collection from https://example.com/articles
INFO  Page 1: found 25 items, 25 total
DEBUG Collected URL: https://example.com/articles/123
DEBUG Following next page: https://example.com/articles?page=2
INFO  Pagination complete: 10 pages, 248 URLs collected

# Issues
WARN  Duplicate URL skipped: https://example.com/articles/123
WARN  No items found on page 5
```

### Phase 2: Data Extraction

```
INFO  Extracting 45/248: https://example.com/articles/123
INFO  Extracted: "Article Title Here..." (fields: 8/10)

# Partial extraction
WARN  Partial extraction for /articles/123: missing author, date

# Failures
ERROR Extraction failed for /articles/456: selector matched no elements
```

### HTTP Requests

```
DEBUG GET https://example.com/articles/123
DEBUG Response: 200 OK (145ms)

# Retries
WARN  Retry 1/3 for /articles/789: timeout after 30s
WARN  Retry 2/3 for /articles/789: 503 Service Unavailable

# Final failure
ERROR Request failed after 3 retries: /articles/789 - Connection refused
```

### State & Checkpoints

```
INFO  Checkpoint saved: 150 processed, 98 pending
INFO  Resuming from checkpoint: 150 already processed, 98 pending
INFO  Crawl complete: 245 items extracted, 3 errors
```

### Shutdown

```
INFO  Shutdown signal received, finishing current item...
INFO  State saved, exiting gracefully
```

---

## Log Message Format Standards

### Structure

```
TIMESTAMP | LEVEL | COMPONENT | MESSAGE
```

Example:
```
2024-01-15 14:30:22 | INFO  | extractor | Extracted: "Article Title" (8/10 fields)
2024-01-15 14:30:23 | WARN  | http      | Retry 1/3 for /articles/789: timeout
```

### Include Context

```
# Bad - no context
ERROR Request failed

# Good - actionable context
ERROR Request failed for /articles/123 after 3 retries: Connection refused
```

### Consistent Field Order

Pattern: **action + target + details + metrics**

```
INFO  Extracted item from /articles/123: "Title" (8 fields)
INFO  Saved checkpoint to state.json: 150 items
INFO  Rate limit wait: 60 seconds
```

### URL Formatting

Use relative paths in logs when base URL is known (reduces noise):

```
# Verbose
INFO  Fetching https://example.com/articles/123

# Cleaner (when base URL is established)
INFO  Fetching /articles/123
```

---

## Log File Organization

```
output/
├── crawler.log           # Human-readable logs
├── crawler.jsonl         # Structured logs (optional, for analysis)
└── archive/
    ├── crawler_2024-01-15_143022.log
    └── crawler_2024-01-14_091555.log
```

### Rotation Strategy

| Approach | When to Use |
|----------|-------------|
| Size-based (10MB) | Long-running crawlers, predictable file sizes |
| Time-based (daily) | Scheduled crawls, easy date-based lookup |
| Per-run | One-off crawls, simple archival |

---

## Structured Logging (JSON Lines)

For production crawlers, consider structured logs for easier parsing and analysis:

```json
{"ts": "2024-01-15T14:30:22Z", "level": "INFO", "component": "collector", "msg": "Page complete", "page": 5, "items": 25, "total": 125}
{"ts": "2024-01-15T14:30:23Z", "level": "WARN", "component": "http", "msg": "Retry", "url": "/articles/789", "attempt": 1, "reason": "timeout"}
{"ts": "2024-01-15T14:30:25Z", "level": "ERROR", "component": "http", "msg": "Request failed", "url": "/articles/789", "attempts": 3, "error": "Connection refused"}
```

**Benefits:**
- Machine-parseable for log aggregation tools
- Easy to filter/query with `jq`
- Can include structured metadata (durations, counts, etc.)

---

## Metrics & Summary Logging

Log a summary at crawl completion:

```
==================================================
CRAWL SUMMARY
==================================================
Duration:        0:15:32
URLs processed:  1523
Items extracted: 1498
Errors:          25
Success rate:    98.4%
Avg time/item:   0.61s
==================================================
```

---

## Error Tracking

Track errors separately for post-crawl analysis:

```
Error Summary:
  parse_error:    12
  timeout:         5
  http_404:        3
  http_403:        2
  connection:      3

Total: 25 errors across 1523 requests (1.6% error rate)
```

Consider writing errors to a separate file for easy review:

```
output/
├── data.jsonl          # Extracted data
├── crawler.log         # Full logs
└── errors.jsonl        # Failed URLs with error details
```

Error record format:
```json
{"url": "/articles/789", "type": "timeout", "message": "Request timed out after 30s", "attempts": 3}
{"url": "/articles/456", "type": "parse_error", "message": "Title selector matched no elements"}
```

---

## Console vs File Output

| Destination | Level | Purpose |
|-------------|-------|---------|
| Console | WARN+ | User visibility during run |
| Log file | DEBUG+ | Full diagnostic trail |

**Console should show:**
- Progress indicators
- Warnings and errors
- Summary at completion

**Console should NOT show:**
- Every URL being fetched
- Every successful extraction
- Debug details

---

## Progress Display Patterns

Separate progress display from logging:

```
Collecting URLs... ━━━━━━━━━━━━━━━━ 248 found
Extracting data... ━━━━━━━━━━━━━━━━ 45% 112/248 [01:15<01:32]

WARN: Missing author field for /articles/123
WARN: Retry 1/3 for /articles/456

Extracting data... ━━━━━━━━━━━━━━━━ 100% 248/248 [02:45<00:00]

Complete: 245 extracted, 3 errors
```

---

## Debugging Checklist

When investigating issues, logs should answer:

1. **What was the crawler doing?** (phase, current URL)
2. **What was the HTTP response?** (status code, timing)
3. **What did the parser find?** (matched elements, extracted values)
4. **What went wrong?** (specific error, context)
5. **What was the state?** (progress, pending items)

If your logs can't answer these, add more context.
