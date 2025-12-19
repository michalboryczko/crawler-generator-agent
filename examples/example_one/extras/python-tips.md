    # Python Crawler Implementation Tips

Practical patterns and package recommendations for building web crawlers in Python.

---

## Recommended Packages

### HTTP & Networking

| Package | Purpose | When to Use |
|---------|---------|-------------|
| `httpx` | Modern async/sync HTTP client | Primary choice - async support, HTTP/2, connection pooling |
| `requests` | Sync HTTP client | Simple scripts, legacy compatibility |
| `aiohttp` | Async HTTP client | High-concurrency async crawlers |

```python
# httpx example with retry and timeout
import httpx

client = httpx.Client(
    timeout=30.0,
    follow_redirects=True,
    headers={"User-Agent": "MyCrawler/1.0"}
)
```

### HTML Parsing

| Package | Purpose | When to Use |
|---------|---------|-------------|
| `beautifulsoup4` | HTML parsing with forgiving parser | Most cases - handles malformed HTML |
| `lxml` | Fast XML/HTML parser | Performance-critical, well-formed HTML |
| `selectolax` | Very fast CSS selector engine | Maximum performance needs |
| `parsel` | Scrapy's selector library | XPath + CSS, Scrapy compatibility |

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, "lxml")  # lxml parser is faster
# or
soup = BeautifulSoup(html, "html.parser")  # No C dependency
```

### CLI & Output

| Package | Purpose | When to Use |
|---------|---------|-------------|
| `typer` | CLI framework | Modern CLI with type hints |
| `click` | CLI framework | More control, complex CLIs |
| `rich` | Terminal formatting | Progress bars, tables, colors |

```python
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer()

@app.command()
def crawl(
    max_items: int = typer.Option(None, "--max-items", "-n"),
    delay: float = typer.Option(1.0, "--delay", "-d"),
    resume: bool = typer.Option(False, "--resume", "-r"),
):
    """Start or resume the crawl."""
    ...
```

### Data Handling

| Package | Purpose | When to Use |
|---------|---------|-------------|
| `pydantic` | Data validation & serialization | Complex data models, API output |
| `dataclasses` | Simple data containers | Built-in, lightweight models |
| `orjson` | Fast JSON serialization | High-volume JSONL output |

```python
from dataclasses import dataclass, asdict
from datetime import datetime
import orjson

@dataclass
class Item:
    url: str
    title: str | None
    extracted_at: datetime

# Fast JSONL writing
with open("output.jsonl", "ab") as f:
    f.write(orjson.dumps(asdict(item)) + b"\n")
```

---

## Signal Handling (Graceful Shutdown)

Handle Ctrl+C gracefully to save state before exiting:

```python
import signal
import sys
from typing import Callable

class GracefulShutdown:
    """Context manager for graceful shutdown handling."""

    def __init__(self):
        self.shutdown_requested = False
        self._original_handlers: dict[int, Callable] = {}

    def __enter__(self):
        # Store original handlers
        self._original_handlers[signal.SIGINT] = signal.signal(
            signal.SIGINT, self._handler
        )
        self._original_handlers[signal.SIGTERM] = signal.signal(
            signal.SIGTERM, self._handler
        )
        return self

    def __exit__(self, *args):
        # Restore original handlers
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def _handler(self, signum, frame):
        if self.shutdown_requested:
            # Second signal = force exit
            sys.exit(1)
        self.shutdown_requested = True
        print("\nShutdown requested, finishing current item...")

# Usage
with GracefulShutdown() as shutdown:
    for url in urls:
        if shutdown.shutdown_requested:
            save_state()
            break
        process(url)
```

---

## Rate Limiting Patterns

### Simple Delay

```python
import time

class RateLimiter:
    def __init__(self, min_delay: float = 1.0):
        self.min_delay = min_delay
        self.last_request = 0.0

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request = time.time()
```

### Token Bucket (for bursting)

```python
import time

class TokenBucket:
    def __init__(self, rate: float, capacity: int = 1):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    def acquire(self):
        now = time.time()
        # Add tokens based on elapsed time
        self.tokens = min(
            self.capacity,
            self.tokens + (now - self.last_update) * self.rate
        )
        self.last_update = now

        if self.tokens >= 1:
            self.tokens -= 1
            return

        # Wait for token
        wait_time = (1 - self.tokens) / self.rate
        time.sleep(wait_time)
        self.tokens = 0
```

---

## Retry Logic with Exponential Backoff

```python
import time
import httpx
from functools import wraps

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (httpx.TimeoutException, httpx.NetworkError),
    retryable_status_codes: tuple = (429, 500, 502, 503, 504),
):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    response = func(*args, **kwargs)

                    if response.status_code in retryable_status_codes:
                        if attempt < max_retries:
                            delay = base_delay * (backoff_factor ** attempt)
                            time.sleep(delay)
                            continue

                    return response

                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** attempt)
                        time.sleep(delay)

            raise last_exception or Exception("Max retries exceeded")
        return wrapper
    return decorator

# Usage
@retry_with_backoff(max_retries=3)
def fetch(url: str) -> httpx.Response:
    return client.get(url)
```

---

## URL Handling

```python
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

# Always use urljoin for relative URLs
base = "https://example.com/articles/"
relative = "../images/photo.jpg"
absolute = urljoin(base, relative)  # https://example.com/images/photo.jpg

# Parse and modify query parameters
url = "https://example.com/search?q=test&page=1"
parsed = urlparse(url)
params = parse_qs(parsed.query)
params["page"] = ["2"]
new_query = urlencode(params, doseq=True)
new_url = parsed._replace(query=new_query).geturl()
```

---

## State Persistence

```python
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Set

@dataclass
class CrawlState:
    seen_urls: Set[str]
    pending_urls: list[str]
    last_offset: int
    processed_count: int

    def save(self, path: Path):
        data = {
            "seen_urls": list(self.seen_urls),
            "pending_urls": self.pending_urls,
            "last_offset": self.last_offset,
            "processed_count": self.processed_count,
        }
        # Atomic write: write to temp file, then rename
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2))
        temp_path.rename(path)

    @classmethod
    def load(cls, path: Path) -> "CrawlState":
        if not path.exists():
            return cls(set(), [], 0, 0)
        data = json.loads(path.read_text())
        return cls(
            seen_urls=set(data["seen_urls"]),
            pending_urls=data["pending_urls"],
            last_offset=data["last_offset"],
            processed_count=data["processed_count"],
        )
```

---

## Selector Helpers

```python
from bs4 import BeautifulSoup, Tag

def select_first(soup: BeautifulSoup, selectors: str) -> Tag | None:
    """Try comma-separated selectors, return first match."""
    for selector in selectors.split(","):
        selector = selector.strip()
        if element := soup.select_one(selector):
            return element
    return None

def extract_text(soup: BeautifulSoup, selectors: str) -> str | None:
    """Extract text from first matching selector."""
    if element := select_first(soup, selectors):
        return element.get_text(strip=True)
    return None

def extract_attr(soup: BeautifulSoup, selectors: str, attr: str) -> str | None:
    """Extract attribute from first matching selector."""
    if element := select_first(soup, selectors):
        return element.get(attr)
    return None

def extract_all(soup: BeautifulSoup, selector: str) -> list[Tag]:
    """Extract all elements matching selector."""
    return soup.select(selector)
```

---

## Project Structure

```
crawler/
├── pyproject.toml          # Project config (use modern packaging)
├── src/
│   └── crawler/
│       ├── __init__.py
│       ├── __main__.py     # Entry point: python -m crawler
│       ├── cli.py          # CLI commands (typer/click)
│       ├── config.py       # Configuration dataclasses
│       ├── client.py       # HTTP client with rate limiting
│       ├── extractors.py   # Listing + detail extractors
│       ├── models.py       # Data models
│       └── state.py        # State persistence
├── output/                  # Crawl output (gitignored)
│   ├── data.jsonl
│   └── state.json
└── tests/
    └── test_extractors.py
```

---

## Common Gotchas

### 1. Memory leaks with BeautifulSoup
```python
# Bad: keeps references
results = []
for html in pages:
    soup = BeautifulSoup(html, "lxml")
    results.append(soup.find("title"))  # Holds entire tree!

# Good: extract data immediately
results = []
for html in pages:
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("title")
    results.append(title.text if title else None)
```

### 2. Connection pooling
```python
# Bad: new connection per request
for url in urls:
    response = httpx.get(url)

# Good: reuse connections
with httpx.Client() as client:
    for url in urls:
        response = client.get(url)
```

### 3. Unicode in JSONL
```python
# Ensure proper encoding
with open("output.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(data, ensure_ascii=False) + "\n")
```

### 4. Relative URLs
```python
# Always resolve relative URLs before storing
from urllib.parse import urljoin

link = urljoin(page_url, href)  # Never store relative URLs
```
