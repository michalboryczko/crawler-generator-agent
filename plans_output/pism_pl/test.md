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
1. https://www.pism.pl/publikacje?page=342
2. https://www.pism.pl/publikacje?page=256
3. https://www.pism.pl/publikacje?page=1
4. https://www.pism.pl/publikacje?page=86
5. https://www.pism.pl/publikacje?page=10
6. https://www.pism.pl/publikacje?page=50
7. https://www.pism.pl/publikacje?page=300

### Article Pages (25)
1. https://www.pism.pl/publikacje/siergiej-lawrow-z-wizyta-w-ameryce-lacinskiej
2. https://www.pism.pl/publikacje/Pr_by_wywierania_wp_ywu_przez_Rosj__na_wybory-prezydenckie_we_Francji
3. https://www.pism.pl/publikacje/w-kierunku-eurazji-nowa-koncepcja-polityki-zagranicznej-rosji
4. https://www.pism.pl/publikacje/perspektywy-wspolpracy-technologicznej-usa-ue2
5. https://www.pism.pl/publikacje/_wiate_ko_w_tunelu__Szanse_na_ca_o_ciowe_porozumienie_w_sprawie_ira_skiego_programu_nuklearnego_
6. https://www.pism.pl/publikacje/litwa-wprowadza-stan-nadzwyczajny-ze-wzgledu-na-dzialania-bialorusi
7. https://www.pism.pl/publikacje/Perspektywy_kompromisu_w_sprawie_reformy_wsp_lnego-europejskiego_systemu_azylowego
8. https://www.pism.pl/publikacje/polskie-dokumenty-dyplomatyczne-1919-styczen-maj
9. https://www.pism.pl/publikacje/Opcja_zerowa__Perspektywy_wsparcia_USA-i_NATO_dla_Afganistanu
10. https://www.pism.pl/publikacje/PISM_Policy_Paper_nr_2__85___Germany_and_the_Future_of_the_Eurozone
... and 15 more

---

## Notes

Test dataset for https://www.pism.pl/publikacje with 7 listing pages (spread across pagination, pages ~1, 10, 50, 86, 256, 300, 342) and 25 article pages randomly sampled from those listings. Listings were extracted using selector '.articles.index.content .article-preview .article-title a:last-of-type'. Articles were extracted using configured detail_selectors for this target. Entries are stored as test-data-listing-1..7 and test-data-article-1..25 in memory, each following the required JSON structure with 'given' HTML and 'expected' fields (article_urls/article_count/has_pagination/next_page_url for listings; title/date/authors/content for articles).

- Listing pages are randomly sampled to avoid overfitting to specific structure
- Article pages are randomly selected from multiple listing pages
- HTML content is cleaned but preserves structure for selector testing
