"""Tests for discover.py — keyword parsing, JD formatting, dedup, Adzuna client."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm import LLMError
import discover
from discover import (
    _format_profile,
    _format_salary,
    adzuna_search,
    extract_titles,
    format_jd_file,
    looks_remote,
    parse_titles_response,
    write_new_jds,
)


# ---------------------------------------------------------------------------
# parse_titles_response
# ---------------------------------------------------------------------------

class TestParseTitlesResponse:
    def test_valid_json(self):
        raw = '{"titles": ["ML Engineer", "Data Scientist", "Researcher"]}'
        assert parse_titles_response(raw) == ["ML Engineer", "Data Scientist", "Researcher"]

    def test_caps_at_5(self):
        raw = '{"titles": ["A","B","C","D","E","F","G"]}'
        assert parse_titles_response(raw) == ["A", "B", "C", "D", "E"]

    def test_drops_empty_and_whitespace(self):
        raw = '{"titles": ["", "  ", "Real Title", null, "Another"]}'
        assert parse_titles_response(raw) == ["Real Title", "Another"]

    def test_returns_empty_on_garbage(self):
        assert parse_titles_response("nope") == []

    def test_returns_empty_on_invalid_json(self):
        assert parse_titles_response('{"titles": [unclosed') == []

    def test_returns_empty_when_field_missing(self):
        assert parse_titles_response('{"other": "field"}') == []

    def test_returns_empty_when_titles_not_list(self):
        assert parse_titles_response('{"titles": "not a list"}') == []

    def test_handles_surrounding_prose(self):
        raw = 'Sure! Here you go:\n{"titles": ["X"]}\nLet me know.'
        assert parse_titles_response(raw) == ["X"]


# ---------------------------------------------------------------------------
# extract_titles (LLM call mocked)
# ---------------------------------------------------------------------------

class TestExtractTitles:
    def test_returns_titles_on_valid_response(self):
        with patch("discover.llm.call", return_value='{"titles": ["A", "B"]}'):
            assert extract_titles("resume", "profile", "sonnet") == ["A", "B"]

    def test_raises_on_empty_titles(self):
        with patch("discover.llm.call", return_value='{"titles": []}'):
            with pytest.raises(LLMError, match="--query"):
                extract_titles("resume", "profile", "sonnet")

    def test_raises_on_unparseable(self):
        with patch("discover.llm.call", return_value="garbage no json"):
            with pytest.raises(LLMError, match="--query"):
                extract_titles("resume", "profile", "sonnet")


# ---------------------------------------------------------------------------
# _format_salary
# ---------------------------------------------------------------------------

class TestFormatSalary:
    def test_range(self):
        assert _format_salary({"salary_min": 100000, "salary_max": 150000}) == "$100,000-$150,000"

    def test_min_only(self):
        assert _format_salary({"salary_min": 80000}) == "$80,000+"

    def test_neither(self):
        assert _format_salary({}) == ""

    def test_zero_min_treated_as_missing(self):
        # Adzuna sometimes returns 0 as "unknown"; treat falsy as missing
        assert _format_salary({"salary_min": 0, "salary_max": 0}) == ""

    def test_min_equals_max_shown_as_single(self):
        # Don't display "$82,839-$82,839" when min == max
        assert _format_salary({"salary_min": 82839, "salary_max": 82839}) == "$82,839"


# ---------------------------------------------------------------------------
# format_jd_file
# ---------------------------------------------------------------------------

class TestFormatJDFile:
    def _result(self, **overrides):
        base = {
            "id": "12345",
            "title": "Senior ML Engineer",
            "company":  {"display_name": "Acme"},
            "location": {"display_name": "San Francisco, CA"},
            "created":  "2026-04-28T12:00:00Z",
            "salary_min": 120000, "salary_max": 160000,
            "redirect_url": "https://www.adzuna.com/abc",
            "description": "<p>Build cool ML stuff.</p>",
        }
        base.update(overrides)
        return base

    def test_includes_all_header_fields(self):
        out = format_jd_file(self._result())
        assert "Company: Acme" in out
        assert "Role: Senior ML Engineer" in out
        assert "Location: San Francisco, CA" in out
        assert "Posted: 2026-04-28" in out
        assert "Salary: $120,000-$160,000" in out
        assert "Source: https://www.adzuna.com/abc" in out

    def test_separator_present(self):
        assert "\n---\n" in format_jd_file(self._result())

    def test_strips_html_in_body(self):
        out = format_jd_file(self._result(description="<p>Hello <strong>World</strong></p>"))
        assert "<p>" not in out
        assert "Hello" in out and "World" in out

    def test_omits_salary_line_when_missing(self):
        out = format_jd_file(self._result(salary_min=None, salary_max=None))
        assert "Salary:" not in out

    def test_handles_missing_company_gracefully(self):
        out = format_jd_file(self._result(company=None))
        assert "Company: Unknown" in out

    def test_handles_missing_url(self):
        out = format_jd_file(self._result(redirect_url=""))
        assert "Source:" not in out


# ---------------------------------------------------------------------------
# looks_remote
# ---------------------------------------------------------------------------

class TestLooksRemote:
    def test_remote_in_title(self):
        assert looks_remote({"title": "Remote Software Engineer"})

    def test_wfh_in_description(self):
        assert looks_remote({"title": "Engineer", "description": "We support WFH"})

    def test_no_remote_signals(self):
        assert not looks_remote({"title": "On-site Engineer", "description": "Office in SF"})

    def test_telecommute(self):
        assert looks_remote({"title": "Engineer (Telecommute)"})


# ---------------------------------------------------------------------------
# write_new_jds — dedup
# ---------------------------------------------------------------------------

class TestWriteNewJDs:
    def _stub(self, ad_id, company="Acme", title="Engineer"):
        return {
            "id": ad_id, "title": title,
            "company": {"display_name": company}, "location": {"display_name": "L"},
            "created": "2026-04-28T00:00:00Z", "description": "body",
        }

    def test_writes_new_files(self, tmp_path):
        results = [self._stub("a"), self._stub("b", title="Other Role")]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (2, 0, 0)
        assert (tmp_path / "adzuna_a.txt").exists()
        assert (tmp_path / "adzuna_b.txt").exists()

    def test_skips_existing(self, tmp_path):
        (tmp_path / "adzuna_a.txt").write_text("preexisting")
        results = [self._stub("a"), self._stub("b", title="Other Role")]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (1, 1, 0)
        assert (tmp_path / "adzuna_a.txt").read_text() == "preexisting"

    def test_skips_missing_id(self, tmp_path):
        results = [self._stub("a"), {"title": "no id"}]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (1, 0, 0)
        assert list(tmp_path.iterdir()) == [tmp_path / "adzuna_a.txt"]

    def test_creates_dir_if_missing(self, tmp_path):
        target = tmp_path / "new_subdir"
        write_new_jds([self._stub("a")], target)
        assert target.is_dir()

    def test_collapses_in_batch_duplicates(self, tmp_path):
        """Adzuna often returns the same (company, title) under different ids."""
        results = [
            self._stub("1", "SimVentions", "Schedule Analyst"),
            self._stub("2", "SimVentions", "Schedule Analyst"),
            self._stub("3", "SimVentions", "Schedule Analyst"),
            self._stub("4", "Acme",        "Engineer"),
        ]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (2, 0, 2)
        assert (tmp_path / "adzuna_1.txt").exists()
        assert not (tmp_path / "adzuna_2.txt").exists()
        assert not (tmp_path / "adzuna_3.txt").exists()
        assert (tmp_path / "adzuna_4.txt").exists()

    def test_dedup_is_case_insensitive(self, tmp_path):
        results = [
            self._stub("1", "Acme Corp", "ML Engineer"),
            self._stub("2", "ACME CORP", "ml engineer"),  # same job, weird casing
        ]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (1, 0, 1)

    def test_same_company_different_title_not_deduped(self, tmp_path):
        results = [
            self._stub("1", "Acme", "Engineer I"),
            self._stub("2", "Acme", "Engineer II"),
        ]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (2, 0, 0)

    def test_missing_company_or_title_not_deduped(self, tmp_path):
        # Don't false-positive when both fields are blank — dedup key incomplete
        results = [
            {"id": "1", "title": "", "company": {"display_name": ""}, "description": ""},
            {"id": "2", "title": "", "company": {"display_name": ""}, "description": ""},
        ]
        n_new, n_skip, n_dup = write_new_jds(results, tmp_path)
        assert (n_new, n_skip, n_dup) == (2, 0, 0)


# ---------------------------------------------------------------------------
# adzuna_search — HTTP mocked
# ---------------------------------------------------------------------------

class TestAdzunaSearch:
    def _mock_urlopen(self, payload: dict, status: int = 200):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__ = lambda self: self
        mock_resp.__exit__  = lambda self, *a: None
        return patch("discover.urllib.request.urlopen", return_value=mock_resp)

    def test_returns_results(self):
        payload = {"results": [{"id": "1", "title": "Eng"}]}
        with self._mock_urlopen(payload):
            r = adzuna_search(
                country="us", app_id="i", app_key="k",
                titles=["Engineer"], where="", distance_km=50,
                days=14, results_per_page=10, remote_only=False,
            )
        assert len(r) == 1 and r[0]["id"] == "1"

    def test_remote_only_filters(self):
        payload = {"results": [
            {"id": "1", "title": "Remote Engineer", "description": ""},
            {"id": "2", "title": "Onsite Engineer", "description": "Office"},
        ]}
        with self._mock_urlopen(payload):
            r = adzuna_search(
                country="us", app_id="i", app_key="k",
                titles=["E"], where="", distance_km=50,
                days=14, results_per_page=10, remote_only=True,
            )
        assert [x["id"] for x in r] == ["1"]

    def test_caps_results_per_page_at_50(self):
        # Verify the request URL would contain results_per_page=50 even if asked for 200
        captured = {}
        def fake_urlopen(req, timeout):  # noqa: ARG001
            captured["url"] = req.full_url
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"results": []}'
            mock_resp.__enter__ = lambda self: self
            mock_resp.__exit__  = lambda self, *a: None
            return mock_resp
        with patch("discover.urllib.request.urlopen", side_effect=fake_urlopen):
            adzuna_search(
                country="us", app_id="i", app_key="k",
                titles=["E"], where="", distance_km=50,
                days=14, results_per_page=200, remote_only=False,
            )
        assert "results_per_page=50" in captured["url"]

    def test_includes_where_when_provided(self):
        captured = {}
        def fake_urlopen(req, timeout):  # noqa: ARG001
            captured["url"] = req.full_url
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"results": []}'
            mock_resp.__enter__ = lambda self: self
            mock_resp.__exit__  = lambda self, *a: None
            return mock_resp
        with patch("discover.urllib.request.urlopen", side_effect=fake_urlopen):
            adzuna_search(
                country="us", app_id="i", app_key="k",
                titles=["E"], where="New York", distance_km=30,
                days=14, results_per_page=10, remote_only=False,
            )
        assert "where=New+York" in captured["url"]
        assert "distance=30" in captured["url"]

    def test_omits_where_when_empty(self):
        captured = {}
        def fake_urlopen(req, timeout):  # noqa: ARG001
            captured["url"] = req.full_url
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"results": []}'
            mock_resp.__enter__ = lambda self: self
            mock_resp.__exit__  = lambda self, *a: None
            return mock_resp
        with patch("discover.urllib.request.urlopen", side_effect=fake_urlopen):
            adzuna_search(
                country="us", app_id="i", app_key="k",
                titles=["E"], where="", distance_km=50,
                days=14, results_per_page=10, remote_only=False,
            )
        assert "where=" not in captured["url"]
        assert "distance=" not in captured["url"]

    def test_401_raises_clear_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="x", code=401, msg="Unauthorized",
            hdrs={}, fp=MagicMock(read=lambda: b'{"error":"bad creds"}'),
        )
        with patch("discover.urllib.request.urlopen", side_effect=err):
            with pytest.raises(LLMError, match="401"):
                adzuna_search(
                    country="us", app_id="x", app_key="x",
                    titles=["E"], where="", distance_km=50,
                    days=14, results_per_page=10, remote_only=False,
                )

    def test_429_raises_budget_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="x", code=429, msg="Too Many Requests",
            hdrs={}, fp=MagicMock(read=lambda: b'{}'),
        )
        with patch("discover.urllib.request.urlopen", side_effect=err):
            with pytest.raises(LLMError, match="429"):
                adzuna_search(
                    country="us", app_id="x", app_key="x",
                    titles=["E"], where="", distance_km=50,
                    days=14, results_per_page=10, remote_only=False,
                )


# ---------------------------------------------------------------------------
# _format_profile (mirrors match.py behavior)
# ---------------------------------------------------------------------------

class TestFormatProfile:
    def test_drops_name_and_non_strings(self):
        out = _format_profile({"name": "X", "motivation": "find good role", "age": 28})
        assert "MOTIVATION: find good role" in out
        assert "NAME" not in out
        assert "AGE" not in out

    def test_empty_returns_placeholder(self):
        assert _format_profile({}) == "(no profile.yaml provided)"
