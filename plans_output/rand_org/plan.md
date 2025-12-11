# Crawl Plan for rand.org

Target: **https://www.rand.org/pubs.html**

This plan is based on:
- Stored target URL
- Browser Agent output: extracted article records + pagination info
- Selector Agent output: verified listing & pagination selectors, inferred detail-page selectors
- Accessibility Agent output: HTTP vs browser requirement analysis

---

## 1. Scope & Objectives

**Goal:** Collect all articles/publications from this section, including:
- URL
- Title
- Publication date
- Author(s)
- Category/section
- Main content/body

**Coverage:**
- Listing pages: `https://www.rand.org/pubs.html?page=N` (1 … ~3388)
- Article detail pages: `https://www.rand.org/pubs.html/<slug>`

---

## 2. Start URLs

- Primary start URL:
  `https://www.rand.org/pubs.html`

Optional explicit pages:
- Page 1: `https://www.rand.org/pubs.html`
- Page 2: `https://www.rand.org/pubs.html?page=2`
- Last page: `https://www.rand.org/pubs.html?page=3388`

---

## 3. Listing Pages

### 3.1. Article blocks & links

**Purpose:** Discover article detail URLs and basic metadata from listing pages.

**Article link selector (verified):**
```css
ul.teasers li > a
```
- **Confidence**: 0.98

**Usage:**
- For each listing page, select all matching `<a>` elements.
- Extract:
  - `url`: resolve relative `href` against base URL
  - `title`: `textContent` of the `<a>`

**Additional listing-level metadata:**

- **article_container:**
  ```css
  [{'selector': 'ul.teasers li', 'priority': 1, 'success_rate': 1.0}]
  ```

- **article_link:**
  ```css
  [{'selector': 'ul.teasers li > a', 'priority': 1, 'success_rate': 1.0}]
  ```

- **article_date:**
  ```css
  [{'selector': 'ul.teasers li .text p.date', 'priority': 1, 'success_rate': 0.95}, {'selector': 'ul.teasers li p.date', 'priority': 2, 'success_rate': 0.05}]
  ```

- **article_category:**
  ```css
  [{'selector': 'ul.teasers li .text .type-time p.type', 'priority': 1, 'success_rate': 0.95}, {'selector': 'ul.teasers li p.type', 'priority': 2, 'success_rate': 0.05}]
  ```

- **pagination:**
  ```css
  [{'selector': '.filteredlist .pagination, .filteredlist nav.pagination, .filteredlist ul.pagination', 'priority': 1, 'success_rate': 0.55}, {'selector': '.filteredlist .pagination, .filteredlist nav.pagination, .filteredlist .pager', 'priority': 2, 'success_rate': 0.25}, {'selector': '.filteredlist .pagination a', 'priority': 3, 'success_rate': 0.15}, {'selector': 'div.filteredlist nav.pagination a, div.filteredlist nav.pagination li, div.filteredlist nav.pagination', 'priority': 4, 'success_rate': 0.05}]
  ```

---

## 4. Pagination

### 4.1. Pagination type

- **Type:** `url_parameter`
### 4.2. Pagination selector

**All pagination links:**
```css
a[href*='?start=']
```

### 4.3. Pagination strategy

Recommended approach:

Single page - extract all articles from the start URL.

---

## 5. Article Detail Pages

Selectors below are inferred from site structure; validate on sample pages.

### 5.1. Title

**Selector:**
```css
[{'selector': 'div.product-header h1#RANDTitleHeadingId', 'priority': 1, 'success_rate': 1.0}]
```


### 5.2. Date

**Selector:**
```css
[{'selector': 'div.product-header p.type-published span.published', 'priority': 1, 'success_rate': 0.67}, {'selector': 'p.type-published span.published', 'priority': 2, 'success_rate': 0.33}]
```


### 5.3. Authors

**Selector:**
```css
[{'selector': 'div.product-header p.authors a', 'priority': 1, 'success_rate': 0.67}, {'selector': 'p.authors a', 'priority': 2, 'success_rate': 0.33}]
```


### 5.4. Product_Type

**Selector:**
```css
[{'selector': 'div.product-header p.type-published span.type', 'priority': 1, 'success_rate': 0.67}, {'selector': 'p.type-published span.type', 'priority': 2, 'success_rate': 0.33}]
```


### 5.5. Series

**Selector:**
```css
[{'selector': 'div.product-main div.series a', 'priority': 1, 'success_rate': 0.0}]
```


### 5.6. Description

**Selector:**
```css
[{'selector': 'div.product-main div.abstract.product-page-abstract div.abstract-first-letter p', 'priority': 1, 'success_rate': 0.33}, {'selector': 'div.abstract.product-page-abstract div.abstract-first-letter p', 'priority': 2, 'success_rate': 0.33}, {'selector': 'div.product-main div.abstract.product-page-abstract div.abstract-first-letter', 'priority': 3, 'success_rate': 0.33}]
```


### 5.7. Topics

**Selector:**
```css
[{'selector': 'ul.related-topics li a', 'priority': 1, 'success_rate': 1.0}]
```


### 5.8. Isbn_Doi

**Selector:**
```css
[{'selector': 'div.product-main div.document-details li span.isbn, div.product-main div.document-details li span.doi', 'priority': 1, 'success_rate': 0.0}]
```


### 5.9. Download_Links

**Selector:**
```css
[{'selector': "div.cover-cta div#buybox div.btn-download a[href$='.pdf']", 'priority': 1, 'success_rate': 0.33}, {'selector': 'div.section.external-link a.more-link', 'priority': 2, 'success_rate': 0.67}]
```


---

## 6. Data Model

Recommended fields per article:

```json
{
  "url": "https://www.rand.org/pubs.html/example-article",
  "title": "Article Title",
  "publication_date": "2024-01-15",
  "authors": ["Author Name"],
  "category": "Category",
  "language": "en",
  "body_html": "<p>...</p>",
  "body_text": "...",
  "source_listing_page": "https://www.rand.org/pubs.html?page=1"
}
```

Notes:
- `publication_date` should come from the detail page, not the listing.
- `language` from `html[lang]`.
- `source_listing_page` is optional but useful for debugging.

---

## 7. Crawler Configuration

```python
config = {
    "start_url": "https://www.rand.org/pubs.html",
    "listing": {
        "article_link_selector": "ul.teasers li > a",
    },
    "pagination": {
        "enabled": true,
        "selector": "a[href*='?start=']",
        "type": "url_parameter",
        "strategy": "follow_next",
        "max_pages": 3388
    },
    "detail": {
        "title_selector": "[{'selector': 'div.product-header h1#RANDTitleHeadingId', 'priority': 1, 'success_rate': 1.0}]",
        "date_selector": "[{'selector': 'div.product-header p.type-published span.published', 'priority': 1, 'success_rate': 0.67}, {'selector': 'p.type-published span.published', 'priority': 2, 'success_rate': 0.33}]",
        "authors_selector": "[{'selector': 'div.product-header p.authors a', 'priority': 1, 'success_rate': 0.67}, {'selector': 'p.authors a', 'priority': 2, 'success_rate': 0.33}]",
        "product_type_selector": "[{'selector': 'div.product-header p.type-published span.type', 'priority': 1, 'success_rate': 0.67}, {'selector': 'p.type-published span.type', 'priority': 2, 'success_rate': 0.33}]",
        "series_selector": "[{'selector': 'div.product-main div.series a', 'priority': 1, 'success_rate': 0.0}]",
        "description_selector": "[{'selector': 'div.product-main div.abstract.product-page-abstract div.abstract-first-letter p', 'priority': 1, 'success_rate': 0.33}, {'selector': 'div.abstract.product-page-abstract div.abstract-first-letter p', 'priority': 2, 'success_rate': 0.33}, {'selector': 'div.product-main div.abstract.product-page-abstract div.abstract-first-letter', 'priority': 3, 'success_rate': 0.33}]",
        "topics_selector": "[{'selector': 'ul.related-topics li a', 'priority': 1, 'success_rate': 1.0}]",
        "isbn_doi_selector": "[{'selector': 'div.product-main div.document-details li span.isbn, div.product-main div.document-details li span.doi', 'priority': 1, 'success_rate': 0.0}]",
        "download_links_selector": "[{'selector': \"div.cover-cta div#buybox div.btn-download a[href$='.pdf']\", 'priority': 1, 'success_rate': 0.33}, {'selector': 'div.section.external-link a.more-link', 'priority': 2, 'success_rate': 0.67}]"
    },
    "request": {
        "requires_browser": false,
        "wait_between_requests": 2,
        "max_concurrent_requests": 4,
        "timeout_seconds": 15
    },
    "deduplication": {
        "key": "url"
    }
}
```

---

## 8. Accessibility & Requirements

**Browser Required:** No

This site can be crawled with simple HTTP requests (no JavaScript needed).

**Recommendation:** Use `requests` or `aiohttp` for efficient crawling.

---

## 9. Sample Articles

1. [China Is Worried About AI Job Losses](https://www.rand.org/pubs/commentary/2025/12/china-is-worried-about-ai-job-losses.html)
2. [Potential Security Implications of AI-Induced Psychosis](https://www.rand.org/pubs/research_reports/RRA4435-1.html)
3. [Staffing Issues in the Military's Child Development Program](https://www.rand.org/pubs/research_reports/RRA2186-1.html)
4. [The Students Who Disappear Before They Count](https://www.rand.org/pubs/commentary/2025/12/the-students-who-disappear-before-they-count.html)
5. [Passive Aggressive: Reconsidering the Relevance of Passive Defenses in Major War](https://www.rand.org/pubs/research_reports/RRA2955-1.html)
6. [Advancing Development of LRRK2-Targeted Therapeutics for Parkinson’s Disease: Conference Proceedings and Roadmap for Research](https://www.rand.org/pubs/conf_proceedings/CFA4120-1.html)
7. [A Relational Perspective on Instructional System Coherence: Introducing New Approaches from Network Analysis](https://www.rand.org/pubs/external_publications/EP71092.html)
8. [Adoption of Artificial Intelligence in the Health Care Sector](https://www.rand.org/pubs/external_publications/EP71027.html)
9. [Examining SAMHSA Funding Awards by Category Before Impending Budget Reductions, 2018-2024](https://www.rand.org/pubs/external_publications/EP71074.html)
10. [China's National Security: The People's Liberation Army's Shrinking Role in Protecting the Nation's Core Interests](https://www.rand.org/pubs/external_publications/EP71164.html)

---

## 10. Known Limitations / Notes

- **Static Content:** Site can be crawled via HTTP requests.
- **Rate Limiting:** Respect robots.txt and implement polite delays.
- **Selector Validation:** Detail page selectors are inferred; validate on sample pages before production crawl.
- **Pagination Bounds:** Verify max pages dynamically if content is frequently updated.

This plan provides the foundation for implementing a complete site crawler.
