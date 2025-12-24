"""Plan Draft Provider Tool for guiding crawl plan generation.

Provides an example plan structure template to guide the LLM in generating
properly formatted and comprehensive crawl plans.

The @traced_tool decorator handles all tool instrumentation.
"""

import logging
from typing import Any

from ..observability.decorators import traced_tool
from .base import BaseTool
from .validation import validated_tool

logger = logging.getLogger(__name__)


class PlanDraftProviderTool(BaseTool):
    """Provide example plan structure template for LLM guidance.

    This tool returns a comprehensive crawl plan template that guides the
    PlanGeneratorAgent in creating well-structured plan.md files with all
    required sections and proper formatting.
    """

    name = "plan_draft_provider"
    description = (
        "Get an example plan.md structure template with all required sections. "
        "Use this to understand the expected format before generating a crawl plan."
    )

    @traced_tool(name="plan_draft_provider")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Get the plan template structure.

        Returns:
            dict with success status and template string
        """
        template = self._get_plan_template()
        section_descriptions = self._get_section_descriptions()

        return {
            "success": True,
            "template": template,
            "section_descriptions": section_descriptions,
            "notes": (
                "Fill in each section with data from collected_information. "
                "The crawler configuration JSON in section 7 must be valid and complete."
            ),
        }

    def _get_plan_template(self) -> str:
        """Get the full plan template structure."""
        return """# Crawl Plan for {site_name}

## 1. Scope & Objectives

**Target Site:** {target_url}
**Task Name:** {task_name}
**Generated:** {timestamp}

### Objectives
- {objective_1}
- {objective_2}
- {objective_3}

### Scope Constraints
- Maximum pages: {max_pages}
- Content types: {content_types}
- Language: {language}

---

## 2. Start URLs

| URL | Purpose | Notes |
|-----|---------|-------|
| {start_url_1} | Main listing page | Primary entry point |
| {start_url_2} | Category page | Optional secondary |

---

## 3. Listing Pages

### Container Structure
- **Container Selector:** `{listing_container_selector}`
- **Article Link Selector:** `{article_link_selector}`

### Listing Fields
| Field | Selector | Confidence |
|-------|----------|------------|
| article_link | `{article_link_selector}` | {confidence}% |
| title_preview | `{title_preview_selector}` | {confidence}% |
| date_preview | `{date_preview_selector}` | {confidence}% |

---

## 4. Pagination

**Pagination Enabled:** {pagination_enabled}
**Pagination Type:** {pagination_type}

| Property | Value |
|----------|-------|
| Selector | `{pagination_selector}` |
| Strategy | {pagination_strategy} |
| Max Pages | {max_pages} |

---

## 5. Article Detail Pages

### Content Selectors
| Field | Selectors | Priority | Notes |
|-------|-----------|----------|-------|
| title | `{title_selector}` | Primary | Required field |
| date | `{date_selector}` | Primary | Publication date |
| authors | `{authors_selector}` | Secondary | May be multiple |
| content | `{content_selector}` | Primary | Main article body |
| lead | `{lead_selector}` | Secondary | Article summary |
| category | `{category_selector}` | Optional | Article category |
| tags | `{tags_selector}` | Optional | Article tags |
| images | `{images_selector}` | Optional | Inline images |
| files | `{files_selector}` | Optional | PDF/document attachments |

---

## 6. Data Model

### Required Fields
- `url` (string): Article URL
- `title` (string): Article title
- `content` (string): Main article content
- `date` (string): Publication date

### Optional Fields
- `authors` (array): List of author names
- `lead` (string): Article summary/lead paragraph
- `category` (string): Article category
- `tags` (array): Article tags
- `images` (array): Image URLs
- `files` (array): Attachment URLs

---

## 7. Crawler Configuration

```json
{crawler_config_json}
```

---

## 8. Accessibility & Requirements

### Browser Requirements
- **Requires JavaScript:** {requires_browser}
- **Reason:** {browser_reason}

### Request Configuration
| Setting | Value |
|---------|-------|
| Wait between requests | {wait_seconds}s |
| Max concurrent requests | {max_concurrent} |
| Timeout | {timeout_seconds}s |

### Content Accessibility
{accessibility_notes}

---

## 9. Sample Articles

### Sample 1
- **URL:** {sample_url_1}
- **Title:** {sample_title_1}
- **Date:** {sample_date_1}

### Sample 2
- **URL:** {sample_url_2}
- **Title:** {sample_title_2}
- **Date:** {sample_date_2}

---

## 10. Notes & Recommendations

### Implementation Notes
- {note_1}
- {note_2}

### Potential Issues
- {issue_1}
- {issue_2}

### Recommendations
- {recommendation_1}
- {recommendation_2}
"""

    def _get_section_descriptions(self) -> dict[str, str]:
        """Get descriptions for each plan section."""
        return {
            "section_1_scope": (
                "Define the crawl scope including target URL, objectives, "
                "and constraints like max pages and content types."
            ),
            "section_2_start_urls": (
                "List all starting URLs for the crawler with their purpose. "
                "Usually the main listing page and any category pages."
            ),
            "section_3_listing_pages": (
                "Document the listing page structure with container and article "
                "link selectors from the Selector Agent output."
            ),
            "section_4_pagination": (
                "Describe pagination mechanism, type, selector, and strategy "
                "from Discovery Agent findings."
            ),
            "section_5_detail_pages": (
                "List all content selectors for article detail pages with "
                "priority levels and confidence scores from Selector Agent."
            ),
            "section_6_data_model": (
                "Define the expected data model with required and optional fields "
                "that will be extracted from articles."
            ),
            "section_7_crawler_config": (
                "Provide the complete crawler configuration JSON that can be "
                "directly used by the crawler. Use prepare_crawler_configuration tool."
            ),
            "section_8_accessibility": (
                "Document browser requirements and request settings from "
                "Accessibility Agent findings."
            ),
            "section_9_samples": (
                "Include sample articles from Data Prep Agent for validation "
                "and testing of the plan."
            ),
            "section_10_notes": (
                "Add implementation notes, potential issues discovered during "
                "analysis, and recommendations for crawler operation."
            ),
        }
