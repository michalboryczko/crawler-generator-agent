# Crawl Plan for pism.pl

Target: **https://pism.pl/publikacje**

This plan is based on:
- Stored target URL
- Browser Agent output: extracted article records + pagination info
- Selector Agent output: verified listing & pagination selectors, inferred detail-page selectors
- Accessibility Agent output: HTTP vs browser requirement analysis

---

## 1. Scope & Objectives

**Goal:** Collect all articles/publications from this section, including:
- URL
- Date
- Lead
- Files
- Title
- Images
- Authors
- Content

**Coverage:**
- Listing pages: `https://pism.pl/publikacje` (pagination to be determined)
- Article detail pages: `https://pism.pl/publikacje/<slug>`

---

## 2. Start URLs

- Primary start URL:
  `https://pism.pl/publikacje`

---

## 3. Listing Pages

### 3.1. Main content container

**Purpose:** Focus extraction on the main listing area, excluding headers/sidebars/footers.

**Container selector:**
```css
div.articles.index.content
```

**Usage:** Before extracting articles, narrow the DOM to this container to avoid
picking up "featured" or "recent" articles from headers/sidebars.

### 3.2. Article blocks & links

**Purpose:** Discover article detail URLs and basic metadata from listing pages.

**Article link selector (verified):**
```css
div.article-preview div.article-title > a[href^="/publikacje/"]
```
- **Confidence**: 0

**Usage:**
- Within the container, select all matching `<a>` elements.
- Extract:
  - `url`: resolve relative `href` against base URL
  - `title`: `textContent` of the `<a>`

**Additional listing-level selectors (as chains):**

- **pagination:**
  ```css
  div.paginator ul.pagination li a
  ```
  (+ 1 fallback selectors)

- **article_link:**
  ```css
  div.article-preview div.article-title > a[href^="/publikacje/"]
  ```

- **article_list:**
  ```css
  div.articles.index.content div.frontend-list-content > div.row
  ```
  (+ 1 fallback selectors)

- **article_category:**
  ```css
  div.article-preview div.article-title div.article-type > a
  ```
  (+ 1 fallback selectors)

- **listing_container:**
  ```css
  div.articles.index.content
  ```

---

## 4. Pagination

### 4.1. Pagination type

- **Type:** `none`
### 4.2. Pagination selector

**All pagination links:**
```css
None
```

### 4.3. Pagination strategy

Recommended approach:

Single page - extract all articles from the start URL.

---

## 5. Article Detail Pages

Selectors below are discovered from analyzing multiple article pages.
Each field has a **selector chain** - an ordered list of selectors to try until one matches.

### 5.1. Date

**Selector chain** (try in order until match):

1. `.article-header .date` *(success: 100%)* - Publication date element in the article header; stable across all samples.

### 5.2. Lead

**Selector chain** (try in order until match):

1. `.article-header .lead` *(success: 100%)* - Intro/summary text directly under the header; consistently present.

### 5.3. Tags

**Selector chain** (try in order until match):

1. `` - No tag list or tag-specific markup was observed on sampled detail pages.

### 5.4. Files

**Selector chain** (try in order until match):

1. `.article-footer .files-content a[href$='.pdf'], .article-footer .files-content a[href$='.doc'], .article-footer .files-content a[href$='.docx'], .article-footer .files-content a[href$='.xls'], .article-footer .files-content a[href$='.xlsx'], .article-footer .files-content a[href$='.zip']` *(success: 50%)* - Most precise selector for downloadable attachments in the footer files block.
2. `.article-footer .files-content ul li a` *(success: 30%)* - Same footer area without extension filter; good structural fallback.
3. `.article a[href$='.pdf'], .article a[href$='.doc'], .article a[href$='.docx'], .article a[href$='.xls'], .article a[href$='.xlsx'], .article a[href$='.zip']` *(success: 10%)* - Extension-based links anywhere inside the article; used when footer block is absent.
4. `a[href$='.pdf'], a[href$='.doc'], a[href$='.docx'], a[href$='.xls'], a[href$='.xlsx'], a[href$='.zip']` *(success: 10%)* - Global extension-based fallback; least scoped and may capture non-article links.

### 5.5. Title

**Selector chain** (try in order until match):

1. `.article-header h1.title` *(success: 100%)* - Main article title in the header; present and correct on all sampled articles.

### 5.6. Images

**Selector chain** (try in order until match):

1. `.article .picture img` *(success: 100%)* - Main article image in the header/lead area; present on all sampled pages.
2. `.article .content .richtext-preview img` *(success: 10%)* - Inline images inside the article body; observed on the weekly bulletin page.

### 5.7. Authors

**Selector chain** (try in order until match):

1. `.article-header .author a` *(success: 90%)* - Linked author name(s) in the header; missing only on the weekly bulletin page.

### 5.8. Content

**Selector chain** (try in order until match):

1. `.article .content .richtext-preview` *(success: 90%)* - Primary article body container; scoped to .article for precision.
2. `.content .richtext-preview` *(success: 10%)* - Broader fallback when the .article wrapper is not present or differs.

### 5.9. Category

**Selector chain** (try in order until match):

1. `` - No reliable per-article category element was found on sampled detail pages.

---

## 6. Data Model

Recommended fields per article (based on discovered selectors):

```json
{
  "url": "https://pism.pl/publikacje/example-article",
  "date": "2024-01-15",
  "lead": "Article summary/lead paragraph",
  "files": [{"name": "document.pdf", "url": "/files/doc.pdf"}],
  "title": "Article Title",
  "images": [{"src": "/img/photo.jpg", "alt": "Photo"}],
  "authors": ["Author Name"],
  "content": "<p>Article content...</p>",
  "source_listing_page": "https://pism.pl/publikacje?page=1"
}
```

Notes:
- `date`/`publication_date` should come from the detail page, not the listing.
- `files`/`attachments` contain downloadable documents found on the page.
- `source_listing_page` is optional but useful for debugging.

---

## 7. Crawler Configuration

```python
config = {
    "start_url": "https://pism.pl/publikacje",
    "listing": {
        "container_selector": "div.articles.index.content",  # Focus on main content
        "article_link_selector": "div.article-preview div.article-title > a[href^="/publikacje/"]",
    },
    "pagination": {
        "enabled": false,
        "selector": "None",
        "type": "none",
        "strategy": "follow_next",
        "max_pages": 100
    },
    "detail": {
        "date": [".article-header .date"],
        "lead": [".article-header .lead"],
        "files": [".article-footer .files-content a[href$='.pdf'], .article-footer .files-content a[href$='.doc'], .article-footer .files-content a[href$='.docx'], .article-footer .files-content a[href$='.xls'], .article-footer .files-content a[href$='.xlsx'], .article-footer .files-content a[href$='.zip']", ".article-footer .files-content ul li a", ".article a[href$='.pdf'], .article a[href$='.doc'], .article a[href$='.docx'], .article a[href$='.xls'], .article a[href$='.xlsx'], .article a[href$='.zip']", "a[href$='.pdf'], a[href$='.doc'], a[href$='.docx'], a[href$='.xls'], a[href$='.xlsx'], a[href$='.zip']"],
        "title": [".article-header h1.title"],
        "images": [".article .picture img", ".article .content .richtext-preview img"],
        "authors": [".article-header .author a"],
        "content": [".article .content .richtext-preview", ".content .richtext-preview"]
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

**Note:**
- Use `container_selector` first to narrow DOM to main content area (excludes header/sidebar articles)
- Detail selectors use chains - try each selector in order until one matches

---

## 8. Accessibility & Requirements

**Browser Required:** Yes

This site requires JavaScript rendering for full functionality.

- Listing pages accessible via HTTP: No
- Article pages accessible via HTTP: No

**Recommendation:** We have own headfull browser accessible via api. While implementation you should check `tech/headfull-chrome.md`.
That is our internal documentation for headfull browser usage you will find docs in repo.

---

## 9. Sample Articles

No articles extracted yet.

---

## 10. Known Limitations / Notes

- **JavaScript Required:** Site content is dynamically loaded.
- **Rate Limiting:** Implement delays between requests to avoid blocks.
- **Anti-bot Protection:** May need to handle Cloudflare or similar.
- **Selector Validation:** Detail page selectors are inferred; validate on sample pages before production crawl.
- **Pagination Bounds:** Verify max pages dynamically if content is frequently updated.

This plan provides the foundation for implementing a complete site crawler.
