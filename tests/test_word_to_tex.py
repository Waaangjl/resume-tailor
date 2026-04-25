"""Tests for word_to_tex.py — docx extraction and LaTeX conversion."""

import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from word_to_tex import _extract_text, convert


class TestExtractText:
    def _make_docx(self, paragraphs: list[str], table_cells: list[str] = None) -> MagicMock:
        doc = MagicMock()
        doc.paragraphs = [MagicMock(text=p) for p in paragraphs]
        if table_cells:
            cell = MagicMock()
            cell.paragraphs = [MagicMock(text=c) for c in table_cells]
            row = MagicMock()
            row.cells = [cell]
            table = MagicMock()
            table.rows = [row]
            doc.tables = [table]
        else:
            doc.tables = []
        return doc

    def test_extracts_paragraph_text(self):
        doc = self._make_docx(["John Doe", "Software Engineer", "Python, Go, SQL"])
        with patch("docx.Document", return_value=doc):
            result = _extract_text(Path("fake.docx"))
        assert "John Doe" in result
        assert "Software Engineer" in result

    def test_deduplicates_text(self):
        doc = self._make_docx(["Repeated line", "Repeated line", "Unique line"])
        with patch("docx.Document", return_value=doc):
            result = _extract_text(Path("fake.docx"))
        assert result.count("Repeated line") == 1

    def test_skips_blank_paragraphs(self):
        doc = self._make_docx(["", "  ", "Real content"])
        with patch("docx.Document", return_value=doc):
            result = _extract_text(Path("fake.docx"))
        assert result.strip() == "Real content"

    def test_extracts_table_cells(self):
        doc = self._make_docx(["Header"], table_cells=["Cell content"])
        with patch("docx.Document", return_value=doc):
            result = _extract_text(Path("fake.docx"))
        assert "Cell content" in result

    def test_raises_when_python_docx_missing(self):
        with patch.dict("sys.modules", {"docx": None}):
            with pytest.raises((RuntimeError, ImportError)):
                _extract_text(Path("fake.docx"))


class TestConvert:
    def test_calls_llm_and_strips_fence(self, tmp_path):
        template_file = tmp_path / "template.tex"
        template_file.write_text("\\documentclass{article}\n\\end{document}", encoding="utf-8")

        docx_path = tmp_path / "resume.docx"

        fake_doc = MagicMock()
        fake_doc.paragraphs = [MagicMock(text="Jane Smith"), MagicMock(text="Python developer")]
        fake_doc.tables = []

        with patch("docx.Document", return_value=fake_doc):
            with patch("llm.call", return_value="\\documentclass{article}\n\\end{document}") as mock_llm:
                result = convert(docx_path, model="sonnet", template_path=template_file)

        mock_llm.assert_called_once()
        assert "\\documentclass" in result

    def test_raises_on_empty_docx(self, tmp_path):
        template_file = tmp_path / "t.tex"
        template_file.write_text("\\documentclass{article}", encoding="utf-8")

        docx_path = tmp_path / "empty.docx"

        fake_doc = MagicMock()
        fake_doc.paragraphs = [MagicMock(text=""), MagicMock(text="  ")]
        fake_doc.tables = []

        with patch("docx.Document", return_value=fake_doc):
            with pytest.raises(ValueError, match="No text found"):
                convert(docx_path, model="sonnet", template_path=template_file)
