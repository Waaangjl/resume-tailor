"""Tests for fetch.py — JD retrieval and HTML stripping."""

import textwrap
from unittest.mock import MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetch import _strip_html, get_jd
from llm import LLMError


class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello world</p>") == "Hello world"

    def test_removes_script_blocks(self):
        raw = "<p>Keep this</p><script>var x=1;</script><p>And this</p>"
        result = _strip_html(raw)
        assert "var x" not in result
        assert "Keep this" in result

    def test_removes_style_blocks(self):
        raw = "<style>.foo { color: red; }</style><p>Content</p>"
        result = _strip_html(raw)
        assert ".foo" not in result
        assert "Content" in result

    def test_collapses_whitespace(self):
        result = _strip_html("<p>a   b\t\tc</p>")
        assert "a b c" in result

    def test_collapses_blank_lines(self):
        raw = "<p>para1</p>\n\n\n\n<p>para2</p>"
        result = _strip_html(raw)
        assert "\n\n\n" not in result

    def test_unescapes_entities(self):
        result = _strip_html("<p>Rock &amp; Roll</p>")
        assert "&amp;" not in result
        assert "Rock & Roll" in result

    def test_empty_string(self):
        assert _strip_html("") == ""

    def test_no_html(self):
        assert _strip_html("plain text") == "plain text"


class TestGetJd:
    def test_returns_file_content(self, tmp_path):
        jd_file = tmp_path / "job.txt"
        jd_file.write_text("Software Engineer at Acme Corp", encoding="utf-8")
        result = get_jd(str(jd_file))
        assert result == "Software Engineer at Acme Corp"

    def test_treats_nonexistent_path_as_raw_text(self):
        raw = "Build APIs and ship features."
        result = get_jd(raw)
        assert result == raw

    def test_fetches_url(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><body><p>Software Engineer</p></body></html>"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_jd("https://example.com/job")
        assert "Software Engineer" in result

    def test_url_fetch_failure_raises_llmerror(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            with pytest.raises(LLMError, match="Could not fetch URL"):
                get_jd("https://example.com/job")
