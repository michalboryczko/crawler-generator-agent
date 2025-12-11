# Test Plan: rand.org

## Test Dataset Overview

- **File**: `data/test_set.jsonl`
- **Total Entries**: 11
  - Listing pages: 7
  - Article pages: 4
- **Format**: JSONL (one JSON object per line)

---

## Entry Types

### Listing Page Entry

```json
{
    "type": "listing",
    "url": "listing page URL",
    "given": "HTML content of the listing page",
    "expected": {
        "article_urls": ["url1", "url2", ...],
        "article_count": 10,
        "has_pagination": true,
        "next_page_url": "next page URL or null"
    }
}
```

### Article Page Entry

```json
{
    "type": "article",
    "url": "article URL",
    "given": "HTML content of the article page",
    "expected": {
        "title": "extracted title",
        "date": "publication date",
        "authors": ["author1", "author2"],
        "category": "category name",
        "content": "article content (truncated)"
    }
}
```

---

## How to Use

### Load test data:
```python
import json

def load_test_data(path):
    with open(path) as f:
        return [json.loads(line) for line in f]

tests = load_test_data("data/test_set.jsonl")
listings = [t for t in tests if t["type"] == "listing"]
articles = [t for t in tests if t["type"] == "article"]
```

### Test listing extraction:
```python
from your_crawler import extract_article_links

for test in listings:
    result = extract_article_links(test["given"])
    assert len(result) == test["expected"]["article_count"]
    # Verify URLs match
```

### Test article extraction:
```python
from your_crawler import extract_article

for test in articles:
    result = extract_article(test["given"])
    assert result["title"] == test["expected"]["title"]
    assert result["date"] == test["expected"]["date"]
```

---

## Test URLs

### Listing Pages (7)
1. https://www.rand.org/pubs.html?start=3600
2. https://www.rand.org/pubs.html?start=480
3. https://www.rand.org/pubs.html?start=12
4. https://www.rand.org/pubs.html?start=0
5. https://www.rand.org/pubs.html?start=600
6. https://www.rand.org/pubs.html?start=1200
7. https://www.rand.org/pubs.html?start=120

### Article Pages (4)
1. https://www.rand.org/pubs/research_reports/RRA2186-1.html
2. https://www.rand.org/pubs/commentary/2025/12/the-students-who-disappear-before-they-count.html
3. https://www.rand.org/pubs/commentary/2025/12/china-is-worried-about-ai-job-losses.html
4. https://www.rand.org/pubs/research_reports/RRA4435-1.html

---

## Notes

Test dataset for https://www.rand.org/pubs.html with 7 listing pages (offset-based pagination via ?start=) and 4 article detail pages. Listings use selector ul.teasers li > a. Articles include fields: title, authors, date, product_type, series, description, topics, isbn_doi, download_links.

- Listing pages are randomly sampled to avoid overfitting to specific structure
- Article pages are randomly selected from multiple listing pages
- HTML content is cleaned but preserves structure for selector testing
