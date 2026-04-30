"""Tests for match.py — JSON parsing, bucket thresholds, file discovery, report rendering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from match import (
    bucket_for,
    collect_jd_paths,
    load_jd,
    parse_match_response,
    render_report,
    _format_profile,
)


# ---------------------------------------------------------------------------
# bucket_for
# ---------------------------------------------------------------------------

class TestBucketFor:
    def test_must_at_80_plus(self):
        assert bucket_for(80) == "must"
        assert bucket_for(95) == "must"
        assert bucket_for(100) == "must"

    def test_yes_in_65_to_79(self):
        assert bucket_for(65) == "yes"
        assert bucket_for(79) == "yes"

    def test_maybe_in_50_to_64(self):
        assert bucket_for(50) == "maybe"
        assert bucket_for(64) == "maybe"

    def test_skip_below_50(self):
        assert bucket_for(0) == "skip"
        assert bucket_for(49) == "skip"


# ---------------------------------------------------------------------------
# parse_match_response
# ---------------------------------------------------------------------------

class TestParseMatchResponse:
    def test_valid_json(self):
        raw = '{"company":"Acme","role":"PM","score":78,"rationale":"good fit","gaps":["a","b"]}'
        d = parse_match_response(raw)
        assert d["company"] == "Acme"
        assert d["role"] == "PM"
        assert d["score"] == 78
        assert d["rationale"] == "good fit"
        assert d["gaps"] == ["a", "b"]

    def test_json_with_surrounding_prose(self):
        raw = (
            'Sure! Here is the score:\n'
            '{"company":"X","role":"Y","score":50,"gaps":[]}\n'
            'Let me know if you need more.'
        )
        d = parse_match_response(raw)
        assert d is not None
        assert d["score"] == 50

    def test_returns_none_on_garbage(self):
        assert parse_match_response("nope") is None

    def test_returns_none_on_invalid_json(self):
        assert parse_match_response('{"score": not-a-number}') is None

    def test_returns_none_when_score_missing(self):
        assert parse_match_response('{"company":"X","role":"Y"}') is None

    def test_returns_none_when_score_unparseable(self):
        assert parse_match_response('{"company":"X","role":"Y","score":"high"}') is None

    def test_score_clamped_to_0_100(self):
        assert parse_match_response('{"score":150}')["score"] == 100
        assert parse_match_response('{"score":-5}')["score"] == 0

    def test_score_string_digit_coerced(self):
        d = parse_match_response('{"score":"82"}')
        assert d["score"] == 82

    def test_gaps_normalized_when_not_list(self):
        d = parse_match_response('{"score":70,"gaps":"single string"}')
        assert d["gaps"] == []

    def test_gaps_drops_empty_entries(self):
        d = parse_match_response('{"score":70,"gaps":["real gap","",null,"  ","another"]}')
        assert d["gaps"] == ["real gap", "another"]

    def test_missing_optional_fields_defaulted(self):
        d = parse_match_response('{"score":40}')
        assert d["company"] == "Unknown"
        assert d["role"] == "Unknown"
        assert d["rationale"] == ""
        assert d["gaps"] == []


# ---------------------------------------------------------------------------
# collect_jd_paths
# ---------------------------------------------------------------------------

class TestCollectJDPaths:
    def test_picks_only_txt_and_url(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.url").write_text("https://example.com")
        (tmp_path / "c.md").write_text("ignored")
        (tmp_path / "d.json").write_text("{}")
        (tmp_path / "subdir").mkdir()
        names = [p.name for p in collect_jd_paths(tmp_path)]
        assert names == ["a.txt", "b.url"]

    def test_empty_dir_returns_empty(self, tmp_path):
        assert collect_jd_paths(tmp_path) == []

    def test_results_are_sorted(self, tmp_path):
        for n in ("z.txt", "a.txt", "m.txt"):
            (tmp_path / n).write_text("x")
        names = [p.name for p in collect_jd_paths(tmp_path)]
        assert names == ["a.txt", "m.txt", "z.txt"]


# ---------------------------------------------------------------------------
# load_jd
# ---------------------------------------------------------------------------

class TestLoadJD:
    def test_txt_returns_content(self, tmp_path):
        p = tmp_path / "jd.txt"
        p.write_text("hello world", encoding="utf-8")
        assert load_jd(p) == "hello world"

    def test_empty_url_file_raises(self, tmp_path):
        p = tmp_path / "empty.url"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_jd(p)

    def test_whitespace_only_url_file_raises(self, tmp_path):
        p = tmp_path / "ws.url"
        p.write_text("   \n  \n", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_jd(p)


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------

class TestRenderReport:
    def test_empty_returns_no_jds_message(self):
        out = render_report([], "base.tex")
        assert "No JDs scored" in out

    def test_includes_table_and_detail_sections(self):
        matches = [{
            "company": "Acme", "role": "PM", "score": 87,
            "rationale": "strong fit", "gaps": ["g1", "g2"],
            "source": "jds/acme.txt",
        }]
        out = render_report(matches, "base.tex")
        assert "## Top picks" in out
        assert "| 1 | 87 | must | Acme | PM | strong fit |" in out
        assert "## Detailed" in out
        assert "### 1. Acme — PM (87 · must)" in out
        assert "**Why**: strong fit" in out
        assert "- g1" in out
        assert "- g2" in out
        assert "jds/acme.txt" in out

    def test_orders_matches_as_given(self):
        # render_report does NOT sort — the caller is responsible
        matches = [
            {"company": "Low",  "role": "A", "score": 30, "rationale": "", "gaps": [], "source": "s1"},
            {"company": "High", "role": "B", "score": 90, "rationale": "", "gaps": [], "source": "s2"},
        ]
        out = render_report(matches, "base.tex")
        # Rank 1 = first item passed in (Low), rank 2 = High
        assert out.index("Low") < out.index("High")

    def test_pipe_in_rationale_escaped(self):
        matches = [{
            "company": "X", "role": "Y", "score": 50,
            "rationale": "uses pipe | char", "gaps": [], "source": "jds/x.txt",
        }]
        out = render_report(matches, "base.tex")
        table_line = next(ln for ln in out.splitlines() if ln.startswith("| 1 |"))
        # | 1 | 50 | maybe | X | Y | uses pipe / char |  → 7 pipes
        assert table_line.count("|") == 7
        assert "uses pipe / char" in table_line

    def test_bucket_label_appears_in_detail_header(self):
        matches = [
            {"company": "M", "role": "R", "score": 50, "rationale": "", "gaps": [], "source": "s"},
        ]
        out = render_report(matches, "base.tex")
        assert "(50 · maybe)" in out

    def test_no_gaps_section_when_empty(self):
        matches = [{
            "company": "X", "role": "Y", "score": 70,
            "rationale": "fine", "gaps": [], "source": "jds/x.txt",
        }]
        out = render_report(matches, "base.tex")
        assert "**Gaps**" not in out


# ---------------------------------------------------------------------------
# _format_profile
# ---------------------------------------------------------------------------

class TestFormatProfile:
    def test_drops_name_and_empty_fields(self):
        out = _format_profile({
            "name": "Jialong",
            "background": "  finance + ML  ",
            "edge": "",
            "motivation": "long-term roadmap",
            "ignored_int": 42,
        })
        assert "NAME" not in out
        assert "BACKGROUND: finance + ML" in out
        assert "MOTIVATION: long-term roadmap" in out
        assert "EDGE" not in out  # empty string filtered
        assert "IGNORED_INT" not in out  # non-string filtered

    def test_empty_profile_returns_placeholder(self):
        assert _format_profile({}) == "(no profile.yaml provided)"
