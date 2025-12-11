# Test Plan: pism.pl

## Test Dataset Overview

- **File**: `data/test_set.jsonl`
- **Total Entries**: 32
  - Listing pages: 7
  - Article pages: 25
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
1. https://www.pism.pl/publikacje?page=1
2. https://www.pism.pl/publikacje?page=3
3. https://www.pism.pl/publikacje?page=2
4. https://www.pism.pl/publikacje?page=50
5. https://www.pism.pl/publikacje?page=342
6. https://www.pism.pl/publikacje?page=10
7. https://www.pism.pl/publikacje?page=100

### Article Pages (25)
1. https://www.pism.pl/publikacje/rosyjska-napasc-na-ukraine-to-klasyczna-wielka-europejska-wojna
2. https://www.pism.pl/publikacje/kij-i-marchewka-plany-chrl-wobec-tajwanu
3. https://www.pism.pl/publikacje/polsko-niemieckie-konsultacje-miedzyrzadowe-zblizenie-stanowisk-bez-przelomu
4. https://www.pism.pl/publikacje/scenariusze-odejscia-ue-od-uzaleznienia-gospodarczego-od-chrl
5. https://www.pism.pl/publikacje/pomoc-gospodarcza-ue-dla-ukrainy-mobilizowanie-inwestycji-w-warunkach-wojennych
6. https://www.pism.pl/publikacje/czechy-slowacja-i-wegry-wobec-zmiennej-polityki-handlowej-usa
7. https://www.pism.pl/publikacje/prawicowa-koalicja-wygrywa-wybory-parlamentarne-we-wloszech
8. https://www.pism.pl/publikacje/cop30-bez-nadziei-bez-przelomow
9. https://www.pism.pl/publikacje/michel-barnier-nowym-premierem-francji
10. https://www.pism.pl/publikacje/konsekwencje-eksplozji-rurociagow-nord-stream-1-i-2
... and 15 more

---

## Notes

Test dataset for https://www.pism.pl/publikacje with 7 listing pages (pages 1,2,3,10,50,100,342) and 25 article detail pages. Listings were extracted using selector .articles.index.content .article-preview .article-title > a[href]. Articles were extracted using selectors: title h1.title, date .article-header .date, authors .article-header .author a, lead .article-header .lead, content .article .content .richtext-preview.

- Listing pages are randomly sampled to avoid overfitting to specific structure
- Article pages are randomly selected from multiple listing pages
- HTML content is cleaned but preserves structure for selector testing
