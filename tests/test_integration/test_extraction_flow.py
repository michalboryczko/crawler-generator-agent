"""Integration tests for extraction flow with CSS selectors."""

from unittest.mock import Mock

import pytest

from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService
from src.tools.extraction import (
    BatchExtractArticlesTool,
    BatchExtractListingsTool,
    RunExtractionAgentTool,
    RunListingExtractionAgentTool,
)


@pytest.fixture
def memory_service():
    """Create fresh memory service for each test."""
    repo = InMemoryRepository()
    return MemoryService(repo, "test-session", "test-agent")


@pytest.fixture
def mock_llm():
    """Create mock LLM that returns formatted JSON."""
    llm = Mock()
    llm.chat = Mock(
        return_value={
            "content": '{"title": "Test Article", "content": "Full content here", "date": "2024-01-15", "authors": ["Author One"]}'
        }
    )
    return llm


@pytest.fixture
def sample_article_html():
    """Sample article HTML with multiple paragraphs."""
    return """
    <html>
    <body>
        <article>
            <h1 class="article-title">Sample Article Title</h1>
            <time class="pub-date">January 15, 2024</time>
            <span class="author">John Doe</span>
            <div class="article-body">
                <p>First paragraph of the article with important information.</p>
                <p>Second paragraph with more detailed content and explanations.</p>
                <p>Third paragraph concluding the article with summary points.</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_listing_html():
    """Sample listing page HTML with article links."""
    return """
    <html>
    <body>
        <main class="listing">
            <a class="article-link" href="/article/1">Article One</a>
            <a class="article-link" href="/article/2">Article Two</a>
            <a class="article-link" href="/article/3">Article Three</a>
        </main>
    </body>
    </html>
    """


class TestSelectorExtraction:
    """Tests verifying CSS selector extraction without LLM."""

    def test_extraction_with_selectors_skips_llm(
        self, memory_service, mock_llm, sample_article_html
    ):
        """Verify extraction uses selectors only, no LLM call."""
        # Setup
        memory_service.write(
            "html-1", {"url": "https://example.com/article1", "html": sample_article_html}
        )
        memory_service.write(
            "detail_selectors",
            {
                "title": [{"selector": "h1.article-title", "success_rate": 1.0}],
                "content": [{"selector": "div.article-body", "success_rate": 0.95}],
                "date": [{"selector": "time.pub-date", "success_rate": 0.9}],
            },
        )

        tool = RunExtractionAgentTool(mock_llm, memory_service)
        result = tool.execute(html_memory_key="html-1", output_memory_key="extracted-1")

        # Verify selector extraction happened, LLM NOT called
        assert result["success"] is True
        assert result["extraction_method"] == "selector"
        mock_llm.chat.assert_not_called()

    def test_extraction_without_selectors_uses_llm_fallback(
        self, memory_service, mock_llm, sample_article_html
    ):
        """Verify extraction falls back to LLM when no selectors."""
        memory_service.write(
            "html-1", {"url": "https://example.com/article1", "html": sample_article_html}
        )
        # No detail_selectors written

        tool = RunExtractionAgentTool(mock_llm, memory_service)
        result = tool.execute(html_memory_key="html-1", output_memory_key="extracted-1")

        assert result["success"] is True
        assert result["extraction_method"] == "llm"
        mock_llm.chat.assert_called_once()

    def test_extraction_stores_selector_results_in_memory(
        self, memory_service, mock_llm, sample_article_html
    ):
        """Verify selector extraction stores actual extracted text."""
        memory_service.write(
            "html-1", {"url": "https://example.com/article1", "html": sample_article_html}
        )
        memory_service.write(
            "detail_selectors",
            {
                "title": [{"selector": "h1.article-title", "success_rate": 1.0}],
                "content": [{"selector": "div.article-body", "success_rate": 0.95}],
            },
        )

        tool = RunExtractionAgentTool(mock_llm, memory_service)
        tool.execute(html_memory_key="html-1", output_memory_key="extracted-1")

        stored = memory_service.read("extracted-1")
        assert stored is not None
        assert stored["type"] == "article"
        assert stored["url"] == "https://example.com/article1"
        # Verify actual extracted content
        assert stored["expected"]["title"] == "Sample Article Title"
        assert "First paragraph" in stored["expected"]["content"]
        assert "Third paragraph" in stored["expected"]["content"]


class TestBatchExtractionWithSelectors:
    """Tests for batch extraction with selector parameters."""

    def test_batch_extract_accepts_detail_selectors_param(
        self, memory_service, mock_llm, sample_article_html
    ):
        """Verify batch extract accepts and uses detail_selectors parameter."""
        # Store multiple articles
        for i in range(3):
            memory_service.write(
                f"articles-{i + 1}",
                {"url": f"https://example.com/article{i + 1}", "html": sample_article_html},
            )

        selectors = {
            "title": [{"selector": "h1.article-title", "success_rate": 1.0}],
            "content": [{"selector": "div.article-body", "success_rate": 0.95}],
        }

        tool = BatchExtractArticlesTool(mock_llm, memory_service)
        result = tool.execute(
            html_key_prefix="articles", output_key_prefix="extracted", detail_selectors=selectors
        )

        assert result["success"] is True
        assert result["extracted_count"] == 3

        # Verify selectors were stored in memory for sub-tools
        stored_selectors = memory_service.read("detail_selectors")
        assert stored_selectors == selectors

    def test_batch_extract_falls_back_to_memory_selectors(
        self, memory_service, mock_llm, sample_article_html
    ):
        """Verify batch extract reads from memory if no param provided."""
        memory_service.write(
            "articles-1", {"url": "https://example.com/article1", "html": sample_article_html}
        )
        memory_service.write(
            "detail_selectors",
            {"title": [{"selector": "h1", "success_rate": 0.9}]},
        )

        tool = BatchExtractArticlesTool(mock_llm, memory_service)
        result = tool.execute(html_key_prefix="articles")

        assert result["success"] is True


class TestListingExtraction:
    """Tests for listing page URL extraction."""

    def test_listing_extraction_with_selector_uses_code(
        self, memory_service, mock_llm, sample_listing_html
    ):
        """Verify URL extraction uses CSS selector when provided."""
        memory_service.write(
            "listing-1", {"url": "https://example.com/news", "html": sample_listing_html}
        )

        tool = RunListingExtractionAgentTool(mock_llm, memory_service)
        result = tool.execute(
            html_memory_key="listing-1",
            output_memory_key="extracted-listing-1",
            article_selector="a.article-link",
        )

        assert result["success"] is True
        assert result["article_count"] == 3
        assert result["extraction_method"] == "selector"

        # URLs should be absolute
        assert "https://example.com/article/1" in result["article_urls"]
        assert "https://example.com/article/2" in result["article_urls"]
        assert "https://example.com/article/3" in result["article_urls"]

    def test_listing_extraction_falls_back_to_llm(self, memory_service, sample_listing_html):
        """Verify extraction falls back to LLM when selector fails."""
        memory_service.write(
            "listing-1", {"url": "https://example.com/news", "html": sample_listing_html}
        )

        # Mock LLM to return URLs
        mock_llm = Mock()
        mock_llm.chat = Mock(
            return_value={"content": '{"article_urls": ["https://example.com/llm-found-1"]}'}
        )

        tool = RunListingExtractionAgentTool(mock_llm, memory_service)
        result = tool.execute(
            html_memory_key="listing-1",
            output_memory_key="extracted-listing-1",
            article_selector=".non-existent-selector",  # Won't match anything
        )

        assert result["success"] is True
        assert result["extraction_method"] == "llm"

    def test_listing_extraction_deduplicates_urls(self, memory_service, mock_llm):
        """Verify duplicate URLs are removed."""
        html = """
        <div>
            <a class="link" href="/article/1">Link 1</a>
            <a class="link" href="/article/1">Duplicate</a>
            <a class="link" href="/article/2">Link 2</a>
        </div>
        """
        memory_service.write("listing-1", {"url": "https://example.com/", "html": html})

        tool = RunListingExtractionAgentTool(mock_llm, memory_service)
        result = tool.execute(
            html_memory_key="listing-1",
            output_memory_key="extracted-listing-1",
            article_selector="a.link",
        )

        assert result["article_count"] == 2
        assert len(result["article_urls"]) == 2


class TestBatchListingExtraction:
    """Tests for batch listing extraction with selector parameters."""

    def test_batch_listing_accepts_listing_selectors_param(
        self, memory_service, mock_llm, sample_listing_html
    ):
        """Verify batch listing extract accepts listing_selectors parameter."""
        memory_service.write(
            "listings-1", {"url": "https://example.com/page1", "html": sample_listing_html}
        )

        listing_selectors = {
            "listing_container": [{"selector": "main.listing", "success_rate": 0.95}],
            "article_link": [{"selector": "a.article-link", "success_rate": 1.0}],
        }

        tool = BatchExtractListingsTool(mock_llm, memory_service)
        result = tool.execute(
            html_key_prefix="listings",
            listing_selectors=listing_selectors,
        )

        assert result["success"] is True
        assert result["total_article_urls"] == 3

        # Verify container selector was stored
        stored_container = memory_service.read("listing_container_selector")
        assert stored_container == "main.listing"

    def test_batch_listing_extracts_article_selector_from_chain(
        self, memory_service, mock_llm, sample_listing_html
    ):
        """Verify article_selector is extracted from listing_selectors chain."""
        memory_service.write(
            "listings-1", {"url": "https://example.com/page1", "html": sample_listing_html}
        )

        listing_selectors = {
            "article_link": [
                {"selector": "a.article-link", "success_rate": 1.0},
                {"selector": "a.fallback", "success_rate": 0.5},
            ],
        }

        tool = BatchExtractListingsTool(mock_llm, memory_service)
        result = tool.execute(
            html_key_prefix="listings",
            listing_selectors=listing_selectors,
        )

        # Should use the first (highest priority) selector from chain
        assert result["success"] is True
        assert result["total_article_urls"] == 3
