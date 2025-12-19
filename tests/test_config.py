"""Tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.config import (
    BrowserConfig,
    OpenAIConfig,
    OutputConfig,
    url_to_dirname,
)


class TestUrlToDirname:
    """Tests for url_to_dirname function."""

    def test_basic_url(self):
        """Test basic URL conversion."""
        assert url_to_dirname("https://example.com") == "example_com"

    def test_www_prefix_removed(self):
        """Test www prefix is removed."""
        assert url_to_dirname("https://www.example.com") == "example_com"

    def test_port_removed(self):
        """Test port is removed."""
        assert url_to_dirname("http://localhost:8080") == "localhost"

    def test_path_ignored(self):
        """Test URL path doesn't affect dirname."""
        assert url_to_dirname("https://example.com/path/to/page") == "example_com"

    def test_special_chars_replaced(self):
        """Test special characters are replaced with underscore."""
        assert url_to_dirname("https://my-site.example.co.uk") == "my_site_example_co_uk"

    def test_consecutive_underscores_collapsed(self):
        """Test consecutive underscores are collapsed."""
        assert url_to_dirname("https://a--b..c.com") == "a_b_c_com"

    def test_result_lowercase(self):
        """Test result is lowercase."""
        assert url_to_dirname("https://MyExample.COM") == "myexample_com"


class TestOutputConfig:
    """Tests for OutputConfig."""

    def test_init_basic(self):
        """Test basic initialization."""
        config = OutputConfig(base_dir=Path("/tmp/output"))
        assert config.base_dir == Path("/tmp/output")
        assert config.template_dir is None

    def test_init_with_template_dir(self):
        """Test initialization with template directory."""
        config = OutputConfig(
            base_dir=Path("/tmp/output"),
            template_dir=Path("/tmp/templates"),
        )
        assert config.base_dir == Path("/tmp/output")
        assert config.template_dir == Path("/tmp/templates")

    def test_from_env_defaults(self):
        """Test from_env with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = OutputConfig.from_env()
            assert config.base_dir == Path("./plans_output")
            assert config.template_dir is None

    def test_from_env_custom(self):
        """Test from_env with custom values."""
        env = {
            "PLANS_OUTPUT_DIR": "/custom/output",
            "PLANS_TEMPLATE_DIR": "/custom/templates",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OutputConfig.from_env()
            assert config.base_dir == Path("/custom/output")
            assert config.template_dir == Path("/custom/templates")

    def test_get_output_dir(self):
        """Test get_output_dir generates correct path with timestamp."""
        import re

        config = OutputConfig(base_dir=Path("/tmp/output"))
        output_dir = config.get_output_dir("https://example.com/page")
        # Format: {base_dir}/{dirname}_{timestamp}
        # Example: /tmp/output/example_com_20250116_153045
        assert output_dir.parent == Path("/tmp/output")
        assert re.match(r"example_com_\d{8}_\d{6}", output_dir.name)


class TestBrowserConfig:
    """Tests for BrowserConfig."""

    def test_init_defaults(self):
        """Test default values."""
        config = BrowserConfig()
        assert config.host == "localhost"
        assert config.port == 9222
        assert config.timeout == 30

    def test_init_custom(self):
        """Test custom values."""
        config = BrowserConfig(host="chrome", port=9223, timeout=60)
        assert config.host == "chrome"
        assert config.port == 9223
        assert config.timeout == 60

    def test_from_env_defaults(self):
        """Test from_env with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = BrowserConfig.from_env()
            assert config.host == "localhost"
            assert config.port == 9222
            assert config.timeout == 30

    def test_from_env_custom(self):
        """Test from_env with custom values."""
        env = {
            "CDP_HOST": "remote-chrome",
            "CDP_PORT": "9333",
            "CDP_TIMEOUT": "120",
        }
        with patch.dict(os.environ, env, clear=True):
            config = BrowserConfig.from_env()
            assert config.host == "remote-chrome"
            assert config.port == 9333
            assert config.timeout == 120

    def test_from_env_with_cdp_url(self):
        """Test from_env with CDP_URL extracts host and port."""
        env = {"CDP_URL": "ws://docker-chrome:9333"}
        with patch.dict(os.environ, env, clear=True):
            config = BrowserConfig.from_env()
            assert config.host == "docker-chrome"
            assert config.port == 9333
            assert config.url == "ws://docker-chrome:9333"

    def test_websocket_url_property_with_url(self):
        """Test websocket_url property returns URL when set."""
        config = BrowserConfig(host="localhost", port=9222, url="ws://custom:8888")
        assert config.websocket_url == "ws://custom:8888"

    def test_websocket_url_property_without_url(self):
        """Test websocket_url property builds from host/port."""
        config = BrowserConfig(host="chrome", port=9333)
        assert config.websocket_url == "ws://chrome:9333"


class TestOpenAIConfig:
    """Tests for OpenAIConfig."""

    def test_init_defaults(self):
        """Test default values."""
        config = OpenAIConfig(api_key="test-key")
        assert config.api_key == "test-key"
        assert config.model == "gpt-5.1"
        assert config.temperature == 0.0

    def test_init_custom(self):
        """Test custom values."""
        config = OpenAIConfig(
            api_key="custom-key",
            model="gpt-4o-mini",
            temperature=0.7,
        )
        assert config.api_key == "custom-key"
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7

    def test_from_env_with_openai_api_key(self):
        """Test from_env with OPENAI_API_KEY."""
        env = {"OPENAI_API_KEY": "sk-test123"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenAIConfig.from_env()
            assert config.api_key == "sk-test123"

    def test_from_env_with_openai_key(self):
        """Test from_env with OPENAI_KEY (alternate name)."""
        env = {"OPENAI_KEY": "sk-alt123"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenAIConfig.from_env()
            assert config.api_key == "sk-alt123"

    def test_from_env_no_key_raises(self):
        """Test from_env raises when no API key found."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="OpenAI API key not found"),
        ):
            OpenAIConfig.from_env()

    def test_from_env_custom_model(self):
        """Test from_env with custom model."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4o-mini",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenAIConfig.from_env()
            assert config.model == "gpt-4o-mini"

    def test_from_env_default_model_fallback(self):
        """Test from_env falls back to DEFAULT_MODEL."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "DEFAULT_MODEL": "custom-model",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenAIConfig.from_env()
            assert config.model == "custom-model"

    def test_from_env_custom_temperature(self):
        """Test from_env with custom temperature."""
        env = {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_TEMPERATURE": "0.5",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenAIConfig.from_env()
            assert config.temperature == 0.5
