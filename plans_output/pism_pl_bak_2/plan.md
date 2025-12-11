# Crawl Plan for pism.pl

Target: **https://www.pism.pl/publikacje**

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
- Listing pages: `https://www.pism.pl/publikacje?page=N` (1 … ~342)
- Article detail pages: `https://www.pism.pl/publikacje/<slug>`

---

## 2. Start URLs

- Primary start URL:
  `https://www.pism.pl/publikacje`

Optional explicit pages:
- Page 1: `https://www.pism.pl/publikacje`
- Page 2: `https://www.pism.pl/publikacje?page=2`
- Last page: `https://www.pism.pl/publikacje?page=342`

---

## 3. Listing Pages

### 3.1. Article blocks & links

**Purpose:** Discover article detail URLs and basic metadata from listing pages.

**Article link selector (verified):**
```css
.articles.index.content .article-preview .article-title > a[href]
```
- **Confidence**: 0.98

**Usage:**
- For each listing page, select all matching `<a>` elements.
- Extract:
  - `url`: resolve relative `href` against base URL
  - `title`: `textContent` of the `<a>`

**Additional listing-level metadata:**

- **article_block:**
  ```css
  .articles.index.content .article-preview
  ```

- **article_title:**
  ```css
  .article-title > a[href]
  ```

- **article_url:**
  ```css
  .article-title > a[href]
  ```

- **article_category:**
  ```css
  .article-title .article-type a
  ```

- **article_authors:**
  ```css
  .article-author a
  ```

- **pagination:**
  ```css
  .paginator .pagination a[href]
  ```

---

## 4. Pagination

### 4.1. Pagination type

- **Type:** `numbered`
- Example structure:
  ```html
  <div class="paginator">
    <ul class="pagination">
      <li class="first"><a href="...">&lt;&lt;</a></li>
      <li class="prev"><a rel="prev" href="...">&lt;</a></li>
      <li><a href="...">1</a></li>
      ...
      <li class="next"><a rel="next" href="...">&gt;</a></li>
      <li class="last"><a href="...">&gt;&gt;</a></li>
    </ul>
  </div>
  ```

### 4.2. Pagination selector

**All pagination links:**
```css
.paginator .pagination li a
```

### 4.3. Pagination strategy

Recommended approach:

1. Start at the primary URL.
2. On each page:
   - Extract article links using the article selector.
   - Extract pagination links.
3. Either:
   - **Deterministic loop:** Iterate `page=1..342`, or
   - **Link-following:** Follow the "next" link until it disappears or repeats.
4. De-duplicate article URLs globally.

---

## 5. Article Detail Pages

Selectors below are inferred from site structure; validate on sample pages.

### 5.1. Title

**Selector:**
```css
h1.title
```


### 5.2. Date

**Selector:**
```css
.article-header .date
```


### 5.3. Authors

**Selector:**
```css
.article-header .author a
```


### 5.4. Lead

**Selector:**
```css
.article-header .lead
```


### 5.5. Content

**Selector:**
```css
.article .content .richtext-preview
```


---

## 6. Data Model

Recommended fields per article:

```json
{
  "url": "https://www.pism.pl/publikacje/example-article",
  "title": "Article Title",
  "publication_date": "2024-01-15",
  "authors": ["Author Name"],
  "category": "Category",
  "language": "en",
  "body_html": "<p>...</p>",
  "body_text": "...",
  "source_listing_page": "https://www.pism.pl/publikacje?page=1"
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
    "start_url": "https://www.pism.pl/publikacje",
    "listing": {
        "article_link_selector": ".articles.index.content .article-preview .article-title > a[href]",
    },
    "pagination": {
        "enabled": true,
        "selector": ".paginator .pagination li a",
        "type": "numbered",
        "strategy": "loop_pages",
        "max_pages": 342
    },
    "detail": {
        "title_selector": "h1.title",
        "date_selector": ".article-header .date",
        "authors_selector": ".article-header .author a",
        "lead_selector": ".article-header .lead",
        "content_selector": ".article .content .richtext-preview"
    },
    "request": {
        "requires_browser": true,
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

**Browser Required:** Yes

This site requires JavaScript rendering for full functionality.

- Listing pages accessible via HTTP: No
- Article pages accessible via HTTP: No

**Recommendation:** Use Playwright or Puppeteer with headless browser.
See `docs/headfull-chrome.md` for implementation details.

---

## 9. Sample Articles

1. [Rocznik Polskiej Polityki Zagranicznej 2024](https://www.pism.pl/publikacje/rocznik-polskiej-polityki-zagranicznej-2024)
2. [Litwa wprowadza stan nadzwyczajny ze względu na działania Białorusi](https://www.pism.pl/publikacje/litwa-wprowadza-stan-nadzwyczajny-ze-wzgledu-na-dzialania-bialorusi)
3. [Scenariusze odejścia UE od uzależnienia gospodarczego od ChRL](https://www.pism.pl/publikacje/scenariusze-odejscia-ue-od-uzaleznienia-gospodarczego-od-chrl)
4. [Polskie Dokumenty Dyplomatyczne 1982](https://www.pism.pl/publikacje/polskie-dokumenty-dyplomatyczne-1982)
5. [Derusyfikacja energetyczna wyszehradzkich partnerów Polski](https://www.pism.pl/publikacje/derusyfikacja-energetyczna-wyszehradzkich-partnerow-polski)

---

## 10. Known Limitations / Notes

- **JavaScript Required:** Site content is dynamically loaded.
- **Rate Limiting:** Implement delays between requests to avoid blocks.
- **Anti-bot Protection:** May need to handle Cloudflare or similar.
- **Selector Validation:** Detail page selectors are inferred; validate on sample pages before production crawl.
- **Pagination Bounds:** Verify max pages dynamically if content is frequently updated.

This plan provides the foundation for implementing a complete site crawler.
