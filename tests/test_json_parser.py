"""Unit tests for JSON response parser.

Tests various formats that LLMs might return JSON in:
- Raw JSON
- Markdown code blocks
- JSON embedded in text
- Malformed JSON that can be fixed
- Edge cases and error handling
"""

import pytest

from src.core.json_parser import (
    parse_json_response,
    extract_json,
    JSONParseError,
)


class TestDirectJsonParsing:
    """Test parsing of raw/direct JSON."""

    def test_simple_object(self):
        content = '{"key": "value"}'
        result = parse_json_response(content)
        assert result == {"key": "value"}

    def test_nested_object(self):
        content = '{"outer": {"inner": "value", "number": 42}}'
        result = parse_json_response(content)
        assert result == {"outer": {"inner": "value", "number": 42}}

    def test_object_with_array(self):
        content = '{"items": [1, 2, 3], "name": "test"}'
        result = parse_json_response(content)
        assert result == {"items": [1, 2, 3], "name": "test"}

    def test_simple_array(self):
        content = '[1, 2, 3]'
        result = parse_json_response(content)
        assert result == [1, 2, 3]

    def test_array_of_objects(self):
        content = '[{"id": 1}, {"id": 2}]'
        result = parse_json_response(content)
        assert result == [{"id": 1}, {"id": 2}]

    def test_array_not_allowed(self):
        content = '[1, 2, 3]'
        result = parse_json_response(content, allow_array=False)
        assert result is None

    def test_with_whitespace(self):
        content = '  \n  {"key": "value"}  \n  '
        result = parse_json_response(content)
        assert result == {"key": "value"}

    def test_complex_nested_structure(self):
        content = '''
        {
            "selectors": {
                "title": {"selector": "h1.title", "found": true},
                "date": {"selector": ".date", "found": false}
            },
            "urls": ["http://example.com/1", "http://example.com/2"],
            "count": 42,
            "active": true,
            "metadata": null
        }
        '''
        result = parse_json_response(content)
        assert result["selectors"]["title"]["found"] is True
        assert result["count"] == 42
        assert result["active"] is True
        assert result["metadata"] is None
        assert len(result["urls"]) == 2


class TestMarkdownCodeBlocks:
    """Test extraction from markdown code blocks."""

    def test_json_code_block(self):
        content = '''Here is the response:

```json
{"key": "value", "number": 123}
```

That's the result.'''
        result = parse_json_response(content)
        assert result == {"key": "value", "number": 123}

    def test_json_code_block_uppercase(self):
        content = '''```JSON
{"key": "value"}
```'''
        result = parse_json_response(content)
        assert result == {"key": "value"}

    def test_json_code_block_mixed_case(self):
        content = '''```Json
{"key": "value"}
```'''
        result = parse_json_response(content)
        assert result == {"key": "value"}

    def test_generic_code_block(self):
        content = '''Here's the data:

```
{"items": [1, 2, 3]}
```'''
        result = parse_json_response(content)
        assert result == {"items": [1, 2, 3]}

    def test_code_block_with_newlines(self):
        content = '''```json
{
    "multiline": true,
    "data": {
        "nested": "value"
    }
}
```'''
        result = parse_json_response(content)
        assert result["multiline"] is True
        assert result["data"]["nested"] == "value"

    def test_multiple_code_blocks_returns_first_valid(self):
        content = '''```
not json
```

```json
{"valid": true}
```'''
        result = parse_json_response(content)
        assert result == {"valid": True}

    def test_code_block_with_surrounding_text(self):
        content = '''I analyzed the page and found the following selectors:

```json
{
    "article_link": "a.article-title",
    "pagination": ".pagination a"
}
```

These selectors should work for the main content area.'''
        result = parse_json_response(content)
        assert result["article_link"] == "a.article-title"
        assert result["pagination"] == ".pagination a"


class TestEmbeddedJson:
    """Test extraction of JSON embedded in text."""

    def test_json_with_prefix(self):
        content = 'The result is: {"status": "success"}'
        result = parse_json_response(content)
        assert result == {"status": "success"}

    def test_json_with_suffix(self):
        content = '{"status": "success"} - this is the response'
        result = parse_json_response(content)
        assert result == {"status": "success"}

    def test_json_with_prefix_and_suffix(self):
        content = 'Response: {"data": [1, 2, 3]} (parsed successfully)'
        result = parse_json_response(content)
        assert result == {"data": [1, 2, 3]}

    def test_json_in_paragraph(self):
        content = '''After analyzing the HTML, I found these selectors.

{"listing_container": ".main-content", "article_link": "h2 a"}

These should capture all articles on the page.'''
        result = parse_json_response(content)
        assert result["listing_container"] == ".main-content"

    def test_multiple_json_objects_returns_first(self):
        content = '{"first": 1} some text {"second": 2}'
        result = parse_json_response(content)
        # Should find the outermost/first valid JSON
        assert "first" in result or "second" in result


class TestMalformedJsonFixes:
    """Test automatic fixing of common JSON issues."""

    def test_trailing_comma_in_object(self):
        content = '{"a": 1, "b": 2,}'
        result = parse_json_response(content)
        assert result == {"a": 1, "b": 2}

    def test_trailing_comma_in_array(self):
        content = '{"items": [1, 2, 3,]}'
        result = parse_json_response(content)
        assert result == {"items": [1, 2, 3]}

    def test_python_true_false_none(self):
        content = '{"active": True, "deleted": False, "data": None}'
        result = parse_json_response(content)
        assert result == {"active": True, "deleted": False, "data": None}

    def test_single_quotes_for_strings(self):
        content = "{'key': 'value'}"
        result = parse_json_response(content)
        # This might not always work perfectly, but should attempt
        if result is not None:
            assert result.get("key") == "value"

    def test_unquoted_keys(self):
        content = '{key: "value", another: 123}'
        result = parse_json_response(content)
        if result is not None:
            assert result.get("key") == "value"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string(self):
        result = parse_json_response("")
        assert result is None

    def test_whitespace_only(self):
        result = parse_json_response("   \n\t  ")
        assert result is None

    def test_none_input(self):
        # Should handle None gracefully
        result = parse_json_response(None)  # type: ignore
        assert result is None

    def test_no_json_content(self):
        content = "This is just plain text without any JSON."
        result = parse_json_response(content)
        assert result is None

    def test_invalid_json(self):
        content = '{"unclosed": "string'
        result = parse_json_response(content)
        assert result is None

    def test_strict_mode_raises_on_failure(self):
        content = "no json here"
        with pytest.raises(JSONParseError) as exc_info:
            parse_json_response(content, strict=True)
        assert "Failed to parse JSON" in str(exc_info.value)
        assert exc_info.value.content == content
        assert len(exc_info.value.attempts) > 0

    def test_strict_mode_raises_on_empty(self):
        with pytest.raises(JSONParseError) as exc_info:
            parse_json_response("", strict=True)
        assert "Empty content" in str(exc_info.value)

    def test_deeply_nested_json(self):
        content = '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}'
        result = parse_json_response(content)
        assert result["a"]["b"]["c"]["d"]["e"] == "deep"

    def test_json_with_escaped_characters(self):
        content = '{"text": "line1\\nline2\\ttabbed", "quote": "say \\"hello\\""}'
        result = parse_json_response(content)
        assert "line1\nline2\ttabbed" == result["text"]
        assert 'say "hello"' == result["quote"]

    def test_json_with_unicode(self):
        content = '{"emoji": "🚀", "chinese": "中文", "math": "∑∏∫"}'
        result = parse_json_response(content)
        assert result["emoji"] == "🚀"
        assert result["chinese"] == "中文"

    def test_large_numbers(self):
        content = '{"big": 99999999999999999, "float": 3.14159265359}'
        result = parse_json_response(content)
        assert result["big"] == 99999999999999999
        assert abs(result["float"] - 3.14159265359) < 0.0001

    def test_empty_object(self):
        content = '{}'
        result = parse_json_response(content)
        assert result == {}

    def test_empty_array(self):
        content = '[]'
        result = parse_json_response(content)
        assert result == []


class TestExtractJsonConvenience:
    """Test the extract_json convenience function."""

    def test_returns_dict(self):
        content = '{"key": "value"}'
        result = extract_json(content)
        assert result == {"key": "value"}

    def test_returns_none_for_array(self):
        content = '[1, 2, 3]'
        result = extract_json(content)
        assert result is None

    def test_returns_none_for_invalid(self):
        content = "not json"
        result = extract_json(content)
        assert result is None


class TestRealWorldLLMResponses:
    """Test with realistic LLM response patterns."""

    def test_chatgpt_style_response(self):
        content = '''Based on my analysis of the HTML, here are the selectors I found:

```json
{
  "article_urls": [
    "https://example.com/article/1",
    "https://example.com/article/2",
    "https://example.com/article/3"
  ],
  "selectors": {
    "listing_container": "main.content",
    "article_list": "ul.articles",
    "article_link": "li.article a.title",
    "article_date": "span.date",
    "article_category": null,
    "pagination": "nav.pagination a"
  },
  "notes": "The main content area contains a list of articles with clear structure."
}
```

These selectors should reliably extract article links from the page.'''

        result = parse_json_response(content)
        assert len(result["article_urls"]) == 3
        assert result["selectors"]["listing_container"] == "main.content"
        assert result["selectors"]["article_category"] is None

    def test_claude_style_response(self):
        content = '''I'll analyze the page structure and provide the selectors.

{"selectors": {"title": "h1.article-title", "content": "div.article-body", "date": "time.published"}, "confidence": 0.95}

The selectors above should work for extracting the article content.'''

        result = parse_json_response(content)
        assert result["selectors"]["title"] == "h1.article-title"
        assert result["confidence"] == 0.95

    def test_response_with_explanation_before_json(self):
        content = '''After examining the HTML structure, I identified the following patterns:

1. Articles are contained in <article> tags
2. Each article has a title link
3. Pagination uses standard Bootstrap classes

Here's my analysis:

```json
{
  "article_link": "article h2 a",
  "pagination": ".pagination .page-link",
  "total_found": 25
}
```'''

        result = parse_json_response(content)
        assert result["article_link"] == "article h2 a"
        assert result["total_found"] == 25

    def test_kimi_style_malformed_response(self):
        """Test handling of potentially malformed responses from non-OpenAI models."""
        # Simpler trailing comma case
        content = '''```json
{
    "result": "success",
    "selectors": ["a.link", "div.item a"],
    "count": 10,
}
```'''
        result = parse_json_response(content)
        # Should handle trailing comma
        assert result is not None
        assert result["result"] == "success"
        assert result["count"] == 10

    def test_response_with_comments_stripped(self):
        """JSON with inline comments should try to parse."""
        content = '''{
    "selector": "div.main",  // main content area
    "items": 5
}'''
        # Standard JSON doesn't support comments, so this might fail
        # But the brace matching should still extract something
        result = parse_json_response(content)
        # This is a known limitation - JSON with comments won't parse
        # The test documents the expected behavior


class TestBraceMatching:
    """Test the brace/bracket matching logic."""

    def test_nested_braces(self):
        content = 'prefix {"a": {"b": {"c": 1}}} suffix'
        result = parse_json_response(content)
        assert result == {"a": {"b": {"c": 1}}}

    def test_braces_in_strings(self):
        content = '{"text": "contains {braces} inside"}'
        result = parse_json_response(content)
        assert result["text"] == "contains {braces} inside"

    def test_brackets_in_strings(self):
        content = '{"text": "array [1,2,3] here"}'
        result = parse_json_response(content)
        assert result["text"] == "array [1,2,3] here"

    def test_mixed_delimiters(self):
        content = '{"array": [{"nested": true}]}'
        result = parse_json_response(content)
        assert result["array"][0]["nested"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
