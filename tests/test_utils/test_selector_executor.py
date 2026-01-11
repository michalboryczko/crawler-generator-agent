"""Tests for SelectorExecutor utility class."""

from src.utils.selector_executor import SelectorExecutor


class TestExecuteSelector:
    """Tests for single selector execution."""

    def test_simple_selector_match(self):
        """Test extracting text from a simple CSS selector match."""
        html = '<div class="content"><p>Hello World</p></div>'
        result = SelectorExecutor.execute_selector(html, "div.content")
        assert result == "Hello World"

    def test_nested_text_extraction(self):
        """Test that nested text is extracted with space separator."""
        html = "<article><h1>Title</h1><p>Para 1</p><p>Para 2</p></article>"
        result = SelectorExecutor.execute_selector(html, "article")
        assert result == "Title Para 1 Para 2"

    def test_no_match_returns_none(self):
        """Test that unmatched selector returns None."""
        html = "<div>Content</div>"
        result = SelectorExecutor.execute_selector(html, ".missing")
        assert result is None

    def test_empty_html(self):
        """Test handling of empty HTML."""
        result = SelectorExecutor.execute_selector("", "div")
        assert result is None

    def test_empty_selector(self):
        """Test handling of empty selector."""
        result = SelectorExecutor.execute_selector("<div>x</div>", "")
        assert result is None

    def test_whitespace_normalization(self):
        """Test that leading/trailing whitespace is stripped."""
        html = "<div>  Text with spaces  </div>"
        result = SelectorExecutor.execute_selector(html, "div")
        # BeautifulSoup strips leading/trailing but preserves internal whitespace
        assert result == "Text with spaces"

    def test_complex_article_structure(self):
        """Test extraction from realistic article structure."""
        html = """
        <article class="post">
            <h1>Article Title</h1>
            <div class="content">
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
                <p>Third paragraph with more content.</p>
            </div>
        </article>
        """
        result = SelectorExecutor.execute_selector(html, ".content")
        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "Third paragraph" in result

    def test_select_first_element(self):
        """Test that select_one returns first match only."""
        html = '<div class="item">First</div><div class="item">Second</div>'
        result = SelectorExecutor.execute_selector(html, ".item")
        assert result == "First"


class TestExecuteSelectorChain:
    """Tests for selector chain with fallbacks."""

    def test_first_selector_matches(self):
        """Test that first matching selector is used."""
        html = '<div class="primary">Primary Content</div>'
        chain = [
            {"selector": ".primary", "success_rate": 1.0},
            {"selector": ".fallback", "success_rate": 0.5},
        ]
        result = SelectorExecutor.execute_selector_chain(html, chain)
        assert result == "Primary Content"

    def test_fallback_to_second_selector(self):
        """Test fallback when first selector doesn't match."""
        html = '<div class="fallback">Fallback Content</div>'
        chain = [
            {"selector": ".missing", "success_rate": 0.9},
            {"selector": ".fallback", "success_rate": 0.5},
        ]
        result = SelectorExecutor.execute_selector_chain(html, chain)
        assert result == "Fallback Content"

    def test_empty_chain_returns_none(self):
        """Test empty chain returns None."""
        html = "<div>Content</div>"
        result = SelectorExecutor.execute_selector_chain(html, [])
        assert result is None

    def test_all_selectors_miss(self):
        """Test all selectors missing returns None."""
        html = "<div>Content</div>"
        chain = [
            {"selector": ".a", "success_rate": 0.9},
            {"selector": ".b", "success_rate": 0.5},
        ]
        result = SelectorExecutor.execute_selector_chain(html, chain)
        assert result is None

    def test_chain_with_missing_selector_key(self):
        """Test chain item without selector key is skipped."""
        html = '<div class="valid">Valid</div>'
        chain = [
            {"not_selector": ".something"},
            {"selector": ".valid", "success_rate": 0.9},
        ]
        result = SelectorExecutor.execute_selector_chain(html, chain)
        assert result == "Valid"

    def test_chain_with_empty_selector(self):
        """Test chain item with empty selector is skipped."""
        html = '<div class="valid">Valid</div>'
        chain = [
            {"selector": "", "success_rate": 0.9},
            {"selector": ".valid", "success_rate": 0.8},
        ]
        result = SelectorExecutor.execute_selector_chain(html, chain)
        assert result == "Valid"


class TestExecuteAllSelectors:
    """Tests for multi-field extraction."""

    def test_multiple_fields(self):
        """Test extracting multiple fields."""
        html = """
        <article>
            <h1 class="title">Article Title</h1>
            <div class="content">Full article body text here</div>
            <span class="date">2024-01-15</span>
        </article>
        """
        selectors = {
            "title": [{"selector": "h1.title", "success_rate": 1.0}],
            "content": [{"selector": "div.content", "success_rate": 0.95}],
            "date": [{"selector": "span.date", "success_rate": 0.9}],
        }
        result = SelectorExecutor.execute_all_selectors(html, selectors)

        assert result["title"] == "Article Title"
        assert result["content"] == "Full article body text here"
        assert result["date"] == "2024-01-15"

    def test_missing_field_returns_empty_string(self):
        """Test missing field returns empty string."""
        html = "<h1>Title</h1>"
        selectors = {
            "title": [{"selector": "h1", "success_rate": 1.0}],
            "missing": [{"selector": ".not-found", "success_rate": 0.5}],
        }
        result = SelectorExecutor.execute_all_selectors(html, selectors)

        assert result["title"] == "Title"
        assert result["missing"] == ""

    def test_empty_selectors_dict(self):
        """Test empty selectors returns empty dict."""
        result = SelectorExecutor.execute_all_selectors("<div>x</div>", {})
        assert result == {}

    def test_empty_selector_chain_for_field(self):
        """Test empty selector chain for a field returns empty string."""
        html = "<div>Content</div>"
        selectors = {"field": []}
        result = SelectorExecutor.execute_all_selectors(html, selectors)
        assert result["field"] == ""


class TestExtractAllElements:
    """Tests for extracting from all matching elements."""

    def test_multiple_items(self):
        """Test extracting from multiple matching elements."""
        html = """
        <ul>
            <li class="tag">Python</li>
            <li class="tag">Testing</li>
            <li class="tag">Web</li>
        </ul>
        """
        result = SelectorExecutor.extract_all_elements(html, ".tag")
        assert result == ["Python", "Testing", "Web"]

    def test_empty_elements_filtered(self):
        """Test that empty elements are filtered out."""
        html = (
            '<span class="item">One</span><span class="item"></span><span class="item">Two</span>'
        )
        result = SelectorExecutor.extract_all_elements(html, ".item")
        assert result == ["One", "Two"]

    def test_no_matches(self):
        """Test no matches returns empty list."""
        html = "<div>Content</div>"
        result = SelectorExecutor.extract_all_elements(html, ".missing")
        assert result == []


class TestExtractAttribute:
    """Tests for extracting attributes."""

    def test_href_extraction(self):
        """Test extracting href attribute."""
        html = '<a class="link" href="/article/1">Article</a>'
        result = SelectorExecutor.extract_attribute(html, "a.link", "href")
        assert result == "/article/1"

    def test_src_extraction(self):
        """Test extracting src attribute."""
        html = '<img class="photo" src="/images/photo.jpg">'
        result = SelectorExecutor.extract_attribute(html, "img.photo", "src")
        assert result == "/images/photo.jpg"

    def test_missing_attribute(self):
        """Test missing attribute returns None."""
        html = '<a class="link">No href</a>'
        result = SelectorExecutor.extract_attribute(html, "a.link", "href")
        assert result is None

    def test_missing_element(self):
        """Test missing element returns None."""
        html = "<div>Content</div>"
        result = SelectorExecutor.extract_attribute(html, ".missing", "href")
        assert result is None


class TestExtractAllAttributes:
    """Tests for extracting attributes from all matching elements."""

    def test_multiple_hrefs(self):
        """Test extracting href from multiple links."""
        html = """
        <div>
            <a class="article" href="/article/1">One</a>
            <a class="article" href="/article/2">Two</a>
            <a class="article" href="/article/3">Three</a>
        </div>
        """
        result = SelectorExecutor.extract_all_attributes(html, "a.article", "href")
        assert result == ["/article/1", "/article/2", "/article/3"]

    def test_filters_none_values(self):
        """Test that None attribute values are filtered."""
        html = """
        <a class="link" href="/one">One</a>
        <a class="link">No href</a>
        <a class="link" href="/two">Two</a>
        """
        result = SelectorExecutor.extract_all_attributes(html, "a.link", "href")
        assert result == ["/one", "/two"]

    def test_no_matches(self):
        """Test no matches returns empty list."""
        html = "<div>Content</div>"
        result = SelectorExecutor.extract_all_attributes(html, ".missing", "href")
        assert result == []
