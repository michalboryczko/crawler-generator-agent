# Scratchpad - Complex Reasoning & Debugging

## Phase 8: Selector Agent Refactoring

### Tool Design Decisions

**ListingPagesGeneratorTool:**
- 2% sampling with min 5, max 20 is purely mathematical
- URL pattern construction (adding ?page=N) is deterministic
- **Decision**: Pure logic, no LLM needed

**ArticlePagesGeneratorTool:**
- URL pattern grouping requires understanding URL structure
- LLM can identify semantic patterns (e.g., /publikacje/{slug} vs /news/{year}/{slug})
- **Decision**: LLM-based for pattern grouping, math for sampling percentages

### Isolated Context Implementation

Each extraction tool needs:
1. Fresh LLM conversation (no history from previous pages)
2. Browser navigation to the specific URL
3. Return structured data back to main agent

**Decision**: Single LLM call per page with structured JSON output (simpler than mini-agents)

### Storage Strategy

Current approach: Everything in MemoryStore under generic keys
**Better approach:**
- listing-selectors-page-{N} for each listing page
- article-selectors-{index} for each article page
- Final aggregation combines all

---

## Implementation Order

1. **ListingPagesGeneratorTool** (pure math)
   - Calculate: 2% of max_pages, min 5, max 20
   - Generate URL list spread across range
   - No LLM needed

2. **ArticlePagesGeneratorTool** (LLM for grouping)
   - LLM groups URLs by pattern
   - Sample 20% per group (min 3)
   - Return with pattern metadata

3. **ListingPageExtractorTool** (browser + LLM)
   - Navigate, get HTML
   - Fresh LLM call to find selectors
   - Return {selectors, article_urls}

4. **ArticlePageExtractorTool** (browser + LLM)
   - Navigate, get HTML
   - Fresh LLM call for detail selectors
   - Return {detail_selectors}

5. **SelectorAggregatorTool** (LLM)
   - Compare all selectors
   - Choose most consistent
   - Return final set with confidence

---

## Debug Log

(Empty - will be used for troubleshooting)
