"""Tests for build.py — metadata extraction, folder naming, diff, strip_tex_fence."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from build import JDMeta, _slugify, make_diff, output_folder, strip_tex_fence


class TestSlugify:
    def test_spaces_become_underscores(self):
        assert _slugify("Business Analyst") == "Business_Analyst"

    def test_ampersand_becomes_and(self):
        assert _slugify("McKinsey & Company") == "McKinsey_and_Company"

    def test_strips_special_chars(self):
        assert _slugify("role/title!") == "roletitle"

    def test_truncates_at_40(self):
        result = _slugify("A" * 50)
        assert len(result) == 40

    def test_empty_string(self):
        assert _slugify("") == ""


class TestOutputFolder:
    def test_creates_folder_with_metadata(self, tmp_path):
        meta = JDMeta(company="Acme", role="Engineer")
        folder = output_folder(meta, tmp_path)
        assert folder.exists()
        assert "Acme" in folder.name
        assert "Engineer" in folder.name

    def test_fallback_name_when_meta_empty(self, tmp_path):
        meta = JDMeta(company="", role="")
        folder = output_folder(meta, tmp_path)
        assert folder.exists()
        # empty company/role → folder name is just the date (YYYYMMDD)
        assert folder.name.isdigit() and len(folder.name) == 8

    def test_creates_nested_dirs(self, tmp_path):
        meta = JDMeta(company="Corp", role="Analyst")
        base = tmp_path / "deep" / "nested"
        folder = output_folder(meta, base)
        assert folder.exists()


class TestStripTexFence:
    def test_removes_triple_backtick_fence(self):
        tex = "```latex\n\\documentclass{article}\n\\end{document}\n```"
        result = strip_tex_fence(tex)
        assert result.startswith("\\documentclass")
        assert "```" not in result

    def test_removes_preamble_before_documentclass(self):
        tex = "Here is your tailored resume:\n\n\\documentclass{article}\n\\end{document}"
        result = strip_tex_fence(tex)
        assert result.startswith("\\documentclass")

    def test_removes_postamble_after_end_document(self):
        tex = "\\documentclass{article}\n\\end{document}\n\nSome commentary."
        result = strip_tex_fence(tex)
        assert result.endswith("\\end{document}")
        assert "commentary" not in result

    def test_passthrough_clean_tex(self):
        tex = "\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}"
        assert strip_tex_fence(tex) == tex

    def test_strips_percent_dashes_marker(self):
        tex = "Some preamble\n%---\n\\documentclass{article}\n\\end{document}"
        result = strip_tex_fence(tex)
        assert result.startswith("%---")


class TestMakeDiff:
    def test_unchanged_files_produce_empty_diff(self):
        text = "line1\nline2\n"
        assert make_diff(text, text) == ""

    def test_detects_added_line(self):
        diff = make_diff("line1\n", "line1\nline2\n")
        assert "+line2" in diff

    def test_detects_removed_line(self):
        diff = make_diff("line1\nline2\n", "line1\n")
        assert "-line2" in diff

    def test_diff_header_filenames(self):
        diff = make_diff("a\n", "b\n")
        assert "original.tex" in diff
        assert "tailored.tex" in diff
