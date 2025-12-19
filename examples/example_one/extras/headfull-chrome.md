# Headfull Chrome API - Usage Guide for LLM Integration

Aviailable at: `http://localhost:8077`

This document describes how to use the Headfull Chrome API for automated web content fetching. Use this as a reference when implementing integrations.

## What This API Does

The Headfull Chrome API runs a real Chrome browser (not headless) inside a Docker container with a virtual display. This means:
- JavaScript-heavy pages render correctly
- Dynamic content loads properly
- Pages see a real browser environment

## Core Concepts

### Sessions
A **session** represents one browser instance. Each session:
- Has its own Chrome process
- Can have its own proxy server
- Processes multiple pages sequentially
- Is isolated from other sessions

### Jobs
A **job** represents fetching content from one URL. Each job:
- Has a unique ID for tracking
- Goes through states: `queued` → `in_progress` → `completed`/`failed`
- Contains the fetched HTML content when complete

### Processing Model
- Multiple sessions run **in parallel** (up to 5 by default)
- Jobs within a session run **sequentially**
- You can specify delays between job processing

## API Endpoints

### Create Content Fetch Sessions

**Endpoint:** `POST /contents`

**When to use:** When you need to fetch HTML content from one or more URLs.

**Request Format:**
```json
[
  {
    "pages": ["https://example.com", "https://httpbin.org/html"],
    "config": {
      "delay_between_requests": 5,
      "proxy_server": null
    }
  }
]
```

**Request Fields:**
- `pages` (required): Array of URLs to fetch
- `config.delay_between_requests` (optional): Seconds to wait between page loads. Default: 0
- `config.proxy_server` (optional): Proxy URL like `http://proxy:8080`. Default: null (no proxy)

**Response Format:**
```json
[
  {
    "id": "abc123-session-uuid",
    "status": "created",
    "pages": [
      {"url": "https://example.com", "id": "job-uuid-1"},
      {"url": "https://httpbin.org/html", "id": "job-uuid-2"}
    ]
  }
]
```

**Key Points:**
- Each object in the request array creates a separate browser session
- Each URL gets its own job ID for tracking
- Jobs start processing immediately after creation
- Session status will be `created` initially

### Check Job Status

**Endpoint:** `GET /jobs/{job_id}`

**When to use:** To poll for job completion and retrieve results.

**Response when queued:**
```json
{
  "id": "job-uuid",
  "status": "queued",
  "queued_at": "2024-01-01T12:00:00Z",
  "started_at": null,
  "completed_at": null,
  "result": null
}
```

**Response when completed:**
```json
{
  "id": "job-uuid",
  "status": "completed",
  "execution_time_ms": 1234,
  "queued_at": "2024-01-01T12:00:00Z",
  "started_at": "2024-01-01T12:00:01Z",
  "completed_at": "2024-01-01T12:00:03Z",
  "result": {
    "url": "https://example.com",
    "content": "<!DOCTYPE html><html>...</html>"
  }
}
```

**Response when failed:**
```json
{
  "id": "job-uuid",
  "status": "failed",
  "result": {
    "url": "https://example.com",
    "error": "Timeout waiting for page load"
  }
}
```

## Common Use Cases

### Use Case 1: Fetch Single Page

```python
import httpx
import time

# Create job
response = httpx.post("http://localhost:8000/contents", json=[{
    "pages": ["https://example.com"]
}])
job_id = response.json()[0]["pages"][0]["id"]

# Poll until complete
while True:
    result = httpx.get(f"http://localhost:8000/jobs/{job_id}").json()
    if result["status"] in ("completed", "failed"):
        break
    time.sleep(1)

# Get content
if result["status"] == "completed":
    html = result["result"]["content"]
```

### Use Case 2: Fetch Multiple Pages Sequentially (Same Session)

Use when pages should be loaded in order in the same browser context:

```python
response = httpx.post("http://localhost:8000/contents", json=[{
    "pages": [
        "https://example.com",
        "https://example.org",
        "https://example.net"
    ],
    "config": {
        "delay_between_requests": 3  # Wait 3 seconds between pages
    }
}])
session = response.json()[0]
job_ids = [page["id"] for page in session["pages"]]
```

### Use Case 3: Fetch Pages in Parallel (Multiple Sessions)

Use when pages are independent and can be fetched simultaneously:

```python
response = httpx.post("http://localhost:8000/contents", json=[
    {"pages": ["https://site1.com"]},
    {"pages": ["https://site2.com"]},
    {"pages": ["https://site3.com"]}
])
# Creates 3 sessions running in parallel
```

### Use Case 4: Fetch with Proxy

```python
response = httpx.post("http://localhost:8000/contents", json=[{
    "pages": ["https://geo-restricted-site.com"],
    "config": {
        "proxy_server": "http://us-proxy.example.com:8080"
    }
}])
```

### Use Case 5: Rate-Limited Fetching

When you need to be gentle with target servers:

```python
response = httpx.post("http://localhost:8000/contents", json=[{
    "pages": [
        "https://api-limited-site.com/page1",
        "https://api-limited-site.com/page2",
        "https://api-limited-site.com/page3"
    ],
    "config": {
        "delay_between_requests": 10  # 10 seconds between each request
    }
}])
```

## Error Handling

### HTTP 404 - Job Not Found
The job_id doesn't exist. Check if you're using the correct ID.

### HTTP 500 - Server Error
Usually indicates Chrome failed to start or crashed. Check:
- Container has enough memory (needs ~500MB+ per session)
- Max concurrent sessions isn't exceeded

### Job Status "failed"
Check `result.error` for details. Common causes:
- Page took too long to load
- Invalid URL
- Network errors
- Proxy connection failed

## Polling Strategy

Recommended polling approach:

```python
def wait_for_job(job_id: str, max_wait: int = 60, interval: float = 1.0):
    """Wait for a job to complete."""
    start = time.time()
    while time.time() - start < max_wait:
        result = httpx.get(f"http://localhost:8000/jobs/{job_id}").json()
        if result["status"] in ("completed", "failed"):
            return result
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete in {max_wait}s")
```

## Resource Considerations

- Each session uses ~300-500MB RAM (Chrome process)
- Default max 5 concurrent sessions
- Sessions are cleaned up after all jobs complete
- Proxy configuration is per-session, not per-job

---

## Python SDK (Recommended)

sdk and docs are in the `headfull-chrome` directory.

For simpler integration, use the Python SDK instead of raw HTTP calls.

### Installation

```bash
pip install headfull-chrome
# or from source:
cd sdk && pip install -e .
```

### Quick Examples

**Fetch single page:**
```python
from headfull_chrome import HeadfullChrome

with HeadfullChrome() as client:
    result = client.fetch_content("https://example.com")
    print(result.content)
```

**Fetch multiple pages sequentially:**
```python
from headfull_chrome import HeadfullChrome, SessionConfig

with HeadfullChrome() as client:
    results = client.fetch_contents(
        urls=["https://example.com", "https://example.org"],
        config=SessionConfig(delay_between_requests=2),
    )
    for r in results:
        print(f"{r.url}: {len(r.content)} bytes")
```

**Fetch multiple pages in parallel:**
```python
from headfull_chrome import HeadfullChrome

with HeadfullChrome() as client:
    results = client.fetch_parallel([
        "https://site1.com",
        "https://site2.com",
        "https://site3.com",
    ])
```

**With proxy:**
```python
from headfull_chrome import HeadfullChrome, SessionConfig

config = SessionConfig(proxy_server="http://proxy:8080")
with HeadfullChrome() as client:
    result = client.fetch_content("https://example.com", config=config)
```

**Async usage:**
```python
import asyncio
from headfull_chrome import AsyncHeadfullChrome

async def main():
    async with AsyncHeadfullChrome() as client:
        results = await client.fetch_parallel([
            "https://site1.com",
            "https://site2.com",
        ])
        for r in results:
            print(f"{r.url}: {'OK' if r.success else r.error}")

asyncio.run(main())
```

### SDK Benefits

- **No manual polling** - `fetch_content()` waits automatically
- **Type hints** - Full IDE support
- **Error handling** - Typed exceptions (`JobTimeoutError`, `JobFailedError`)
- **Sync & async** - Both `HeadfullChrome` and `AsyncHeadfullChrome`
- **Convenience methods** - `fetch_content()`, `fetch_contents()`, `fetch_parallel()`

### When to Use SDK vs Raw API

| Use SDK when... | Use Raw API when... |
|----------------|---------------------|
| Building Python applications | Non-Python languages |
| Want simple one-liners | Need custom polling logic |
| Standard fetch patterns | Complex session management |
| Type safety matters | Minimal dependencies |
