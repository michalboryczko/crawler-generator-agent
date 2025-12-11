# Test Plan: pism.pl

## Test Dataset Overview

- **File**: `data/test_set.jsonl`
- **Total Entries**: 29
  - Listing pages: 7
  - Article pages: 22
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
1. https://www.pism.pl/publikacje?page=150
2. https://www.pism.pl/publikacje?page=10
3. https://www.pism.pl/publikacje?page=2
4. https://www.pism.pl/publikacje?page=1
5. https://www.pism.pl/publikacje?page=50
6. https://www.pism.pl/publikacje?page=5
7. https://www.pism.pl/publikacje?page=300

### Article Pages (22)
1. https://www.pism.pl/publikacje/Wybory_w_BadeniiWirtembergii_i_NadreniiPalatynacie_Zolta_kartka_dla_CDU
2. https://www.pism.pl/publikacje/rezygnacja-andrija-jermaka
3. https://www.pism.pl/publikacje/rocznik-polskiej-polityki-zagranicznej-2024
4. https://www.pism.pl/publikacje/Szczyt_formatu_Quad___potwierdzenie_kluczowej_roli_w_IndoPacyfiku
5. https://www.pism.pl/publikacje/Eksport_polskich_zielonych_technologii-na_rynki_pozaeuropejskie_
6. https://www.pism.pl/publikacje/polsko-niemieckie-konsultacje-miedzyrzadowe-zblizenie-stanowisk-bez-przelomu
7. https://www.pism.pl/publikacje/Prezydent_Nigru_nagrodzony_afrykanskim_Noblem
8. https://www.pism.pl/publikacje/Swoboda_przep_ywu_os_b_w_Unii_Europejskiej__mobilno___zamiast_migracji
9. https://www.pism.pl/publikacje/Polska_i_ASEAN__w_poszukiwaniu_nowych_rynk_w_w_Azji
10. https://www.pism.pl/publikacje/polskie-dokumenty-dyplomatyczne-1982
... and 12 more

---

## Notes

Test dataset for https://www.pism.pl/publikacje with 7 listing pages (spread across pages 1,2,5,10,50,150,300) and 22 article detail pages. Listings stored as test-data-listing-1..7, articles stored as test-data-article-1..22. Each listing entry includes full HTML and extracted article URLs plus pagination flag. Each article entry includes full HTML and extracted fields: title, date, authors, category, lead, content, tags, breadcrumbs.

- Listing pages are randomly sampled to avoid overfitting to specific structure
- Article pages are randomly selected from multiple listing pages
- HTML content is cleaned but preserves structure for selector testing
