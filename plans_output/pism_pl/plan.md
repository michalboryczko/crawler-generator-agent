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
.articles.index.content .frontend-list-content .article-preview .article-title > a[href^="/publikacje/"]
```
- **Confidence**: 0

**Usage:**
- For each listing page, select all matching `<a>` elements.
- Extract:
  - `url`: resolve relative `href` against base URL
  - `title`: `textContent` of the `<a>`

**Additional listing-level metadata:**

- **article_container:**
  ```css
  [{'selector': '.articles.index.content .frontend-list-content .article-preview', 'success_rate': 0.83, 'found_on_pages': 5}, {'selector': 'div.articles.index.content div.frontend-list-content div.article-preview', 'success_rate': 0.17, 'found_on_pages': 1}]
  ```

- **article_link:**
  ```css
  [{'selector': '.articles.index.content .frontend-list-content .article-preview .article-title > a[href^="/publikacje/"]', 'success_rate': 0.33, 'found_on_pages': 2}, {'selector': '.articles.index.content .frontend-list-content .article-preview .article-title > a[href]', 'success_rate': 0.17, 'found_on_pages': 1}, {'selector': '.articles.index.content .frontend-list-content .article-preview .article-title > a[href^="/publikacje"]', 'success_rate': 0.17, 'found_on_pages': 1}, {'selector': '.articles.index.content .frontend-list-content .article-preview .article-title > a', 'success_rate': 0.17, 'found_on_pages': 1}, {'selector': 'div.articles.index.content div.frontend-list-content div.article-preview div.article-title > a[href]', 'success_rate': 0.17, 'found_on_pages': 1}]
  ```

- **article_category:**
  ```css
  [{'selector': '.articles.index.content .frontend-list-content .article-preview .article-title .article-type a', 'success_rate': 0.83, 'found_on_pages': 5}, {'selector': 'div.articles.index.content div.frontend-list-content div.article-preview div.article-title div.article-type > a', 'success_rate': 0.17, 'found_on_pages': 1}]
  ```

- **pagination:**
  ```css
  [{'selector': '.paginator ul.pagination li a', 'success_rate': 0.67, 'found_on_pages': 4}, {'selector': '.paginator .pagination li a', 'success_rate': 0.17, 'found_on_pages': 1}, {'selector': 'div.paginator ul.pagination li a', 'success_rate': 0.17, 'found_on_pages': 1}]
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
.paginator ul.pagination li a
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
[{'selector': '.article-header h1.title', 'priority': 1, 'notes': 'Most common (10/12). Class-based and not over\x1fspecific; should match both div and non-div containers.', 'success_rate': 0.83, 'found_on_pages': 10}, {'selector': '.article .article-header h1.title', 'priority': 2, 'notes': 'More specific context inside .article; use if multiple .article-header blocks exist on page.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': 'div.article-header h1.title', 'priority': 3, 'notes': 'Tag-specific variant; fallback for pages where .article-header is explicitly a div and other selectors fail.', 'success_rate': 0.08, 'found_on_pages': 1}]
```


### 5.2. Date

**Selector:**
```css
[{'selector': '.article-header .date', 'priority': 1, 'notes': 'Most common (10/12). Class-based and flexible regarding container tag.', 'success_rate': 0.83, 'found_on_pages': 10}, {'selector': '.article .article-header .date', 'priority': 2, 'notes': 'Adds .article context; safer when multiple .article-header blocks exist.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': 'div.article-header div.date', 'priority': 3, 'notes': 'Tag-specific; use as a last resort when other class-only selectors fail.', 'success_rate': 0.08, 'found_on_pages': 1}]
```


### 5.3. Authors

**Selector:**
```css
[{'selector': '.article-header .author a', 'priority': 1, 'notes': 'Most common (8/9). Directly targets author links within the header.', 'success_rate': 0.67, 'found_on_pages': 8}, {'selector': '.article .article-header .author a', 'priority': 2, 'notes': 'Adds .article context; fallback for pages where author block is nested under .article.', 'success_rate': 0.08, 'found_on_pages': 1}]
```


### 5.4. Lead

**Selector:**
```css
[{'selector': '.article-header .lead', 'priority': 1, 'notes': 'Most common (10/12). Class-based and independent of container tag.', 'success_rate': 0.83, 'found_on_pages': 10}, {'selector': '.article .article-header .lead', 'priority': 2, 'notes': 'More specific context under .article; use when multiple headers exist.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': 'div.article-header div.lead', 'priority': 3, 'notes': 'Tag-specific; fallback for pages with strict div structure.', 'success_rate': 0.08, 'found_on_pages': 1}]
```


### 5.5. Content

**Selector:**
```css
[{'selector': '.article .content .richtext-preview', 'priority': 1, 'notes': 'Most common (11/12). Strong structural context: article > content > richtext-preview.', 'success_rate': 0.92, 'found_on_pages': 11}, {'selector': 'div.article div.content div.richtext-preview', 'priority': 2, 'notes': 'Tag-specific variant; fallback for pages using explicit div structure.', 'success_rate': 0.08, 'found_on_pages': 1}]
```


### 5.6. Category

**Selector:**
```css
[]
```


### 5.7. Tags

**Selector:**
```css
[]
```


### 5.8. Breadcrumbs

**Selector:**
```css
[{'selector': '.frontend-path span a', 'priority': 1, 'notes': 'Most common (9/12). Targets individual breadcrumb links; best for extracting full trail.', 'success_rate': 0.75, 'found_on_pages': 9}, {'selector': 'div.frontend-path span a', 'priority': 2, 'notes': 'Tag-specific variant; fallback when .frontend-path is a div and first selector fails.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': '.frontend-path', 'priority': 3, 'notes': 'Very generic; use only as last resort to capture the whole breadcrumb container if link-level selectors fail.', 'success_rate': 0.17, 'found_on_pages': 2}]
```


### 5.9. Files

**Selector:**
```css
[{'selector': '.article-footer .files-content ul li a', 'priority': 1, 'notes': 'Most frequent file list pattern (4/10). Targets explicit files-content block.', 'success_rate': 0.33, 'found_on_pages': 4}, {'selector': '.article-footer .files ul li a', 'priority': 2, 'notes': 'Second most common (3/10). Generic files list under article footer.', 'success_rate': 0.25, 'found_on_pages': 3}, {'selector': 'div.article-footer div.files ul li a', 'priority': 3, 'notes': 'Tag-specific variant of .files list; fallback for strict div-based markup.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': '.article .picture img', 'priority': 4, 'notes': 'Single occurrence; likely main article image. Use as a low-priority file/media source.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': '.article-footer .similar-preview .article-preview .article-title a', 'priority': 5, 'notes': 'Single occurrence; links to similar articles, not primary files. Use only as last resort if other file selectors fail.', 'success_rate': 0.08, 'found_on_pages': 1}]
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
        "article_link_selector": ".articles.index.content .frontend-list-content .article-preview .article-title > a[href=\"/publikacje/\"]",
    },
    "pagination": {
        "enabled": true,
        "selector": ".paginator ul.pagination li a",
        "type": "numbered",
        "strategy": "loop_pages",
        "max_pages": 342
    },
    "detail": {
        "title_selector": "[{'selector': '.article-header h1.title', 'priority': 1, 'notes': 'Most common (10/12). Class-based and not over\x1fspecific; should match both div and non-div containers.', 'success_rate': 0.83, 'found_on_pages': 10}, {'selector': '.article .article-header h1.title', 'priority': 2, 'notes': 'More specific context inside .article; use if multiple .article-header blocks exist on page.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': 'div.article-header h1.title', 'priority': 3, 'notes': 'Tag-specific variant; fallback for pages where .article-header is explicitly a div and other selectors fail.', 'success_rate': 0.08, 'found_on_pages': 1}]",
        "date_selector": "[{'selector': '.article-header .date', 'priority': 1, 'notes': 'Most common (10/12). Class-based and flexible regarding container tag.', 'success_rate': 0.83, 'found_on_pages': 10}, {'selector': '.article .article-header .date', 'priority': 2, 'notes': 'Adds .article context; safer when multiple .article-header blocks exist.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': 'div.article-header div.date', 'priority': 3, 'notes': 'Tag-specific; use as a last resort when other class-only selectors fail.', 'success_rate': 0.08, 'found_on_pages': 1}]",
        "authors_selector": "[{'selector': '.article-header .author a', 'priority': 1, 'notes': 'Most common (8/9). Directly targets author links within the header.', 'success_rate': 0.67, 'found_on_pages': 8}, {'selector': '.article .article-header .author a', 'priority': 2, 'notes': 'Adds .article context; fallback for pages where author block is nested under .article.', 'success_rate': 0.08, 'found_on_pages': 1}]",
        "lead_selector": "[{'selector': '.article-header .lead', 'priority': 1, 'notes': 'Most common (10/12). Class-based and independent of container tag.', 'success_rate': 0.83, 'found_on_pages': 10}, {'selector': '.article .article-header .lead', 'priority': 2, 'notes': 'More specific context under .article; use when multiple headers exist.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': 'div.article-header div.lead', 'priority': 3, 'notes': 'Tag-specific; fallback for pages with strict div structure.', 'success_rate': 0.08, 'found_on_pages': 1}]",
        "content_selector": "[{'selector': '.article .content .richtext-preview', 'priority': 1, 'notes': 'Most common (11/12). Strong structural context: article > content > richtext-preview.', 'success_rate': 0.92, 'found_on_pages': 11}, {'selector': 'div.article div.content div.richtext-preview', 'priority': 2, 'notes': 'Tag-specific variant; fallback for pages using explicit div structure.', 'success_rate': 0.08, 'found_on_pages': 1}]",
        "category_selector": "[]",
        "tags_selector": "[]",
        "breadcrumbs_selector": "[{'selector': '.frontend-path span a', 'priority': 1, 'notes': 'Most common (9/12). Targets individual breadcrumb links; best for extracting full trail.', 'success_rate': 0.75, 'found_on_pages': 9}, {'selector': 'div.frontend-path span a', 'priority': 2, 'notes': 'Tag-specific variant; fallback when .frontend-path is a div and first selector fails.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': '.frontend-path', 'priority': 3, 'notes': 'Very generic; use only as last resort to capture the whole breadcrumb container if link-level selectors fail.', 'success_rate': 0.17, 'found_on_pages': 2}]",
        "files_selector": "[{'selector': '.article-footer .files-content ul li a', 'priority': 1, 'notes': 'Most frequent file list pattern (4/10). Targets explicit files-content block.', 'success_rate': 0.33, 'found_on_pages': 4}, {'selector': '.article-footer .files ul li a', 'priority': 2, 'notes': 'Second most common (3/10). Generic files list under article footer.', 'success_rate': 0.25, 'found_on_pages': 3}, {'selector': 'div.article-footer div.files ul li a', 'priority': 3, 'notes': 'Tag-specific variant of .files list; fallback for strict div-based markup.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': '.article .picture img', 'priority': 4, 'notes': 'Single occurrence; likely main article image. Use as a low-priority file/media source.', 'success_rate': 0.08, 'found_on_pages': 1}, {'selector': '.article-footer .similar-preview .article-preview .article-title a', 'priority': 5, 'notes': 'Single occurrence; links to similar articles, not primary files. Use only as last resort if other file selectors fail.', 'success_rate': 0.08, 'found_on_pages': 1}]"
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
