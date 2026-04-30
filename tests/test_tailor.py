"""Unit tests for tailor.py — focused on _classify_fit (page-fit decision logic)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tailor import PAGE_FILL_TOLERANCE, _classify_fit


# ---------------------------------------------------------------------------
# Same page count, last page well-filled → "ok"
# ---------------------------------------------------------------------------

def test_same_pages_full_fill_is_ok():
    base = (2, [50, 48])
    tail = (2, [50, 47])
    verdict, _ = _classify_fit(base, tail)
    assert verdict == "ok"


def test_one_page_well_filled_is_ok():
    base = (1, [50])
    tail = (1, [48])
    verdict, _ = _classify_fit(base, tail)
    assert verdict == "ok"


# ---------------------------------------------------------------------------
# Tailored has fewer pages → expand
# ---------------------------------------------------------------------------

def test_fewer_pages_triggers_expand():
    base = (2, [55, 50])
    tail = (1, [40])
    verdict, info = _classify_fit(base, tail)
    assert verdict == "expand"
    assert info["target_pages"] == 2
    assert info["current_pages"] == 1
    assert info["deficit"] > 0


# ---------------------------------------------------------------------------
# Tailored overflows to extra page → compress
# ---------------------------------------------------------------------------

def test_more_pages_triggers_compress():
    base = (1, [55])
    tail = (2, [55, 8])
    verdict, info = _classify_fit(base, tail)
    assert verdict == "compress"
    assert info["target_pages"] == 1
    assert info["current_pages"] == 2
    assert info["overflow"] == 8


def test_two_to_three_pages_triggers_compress():
    base = (2, [55, 50])
    tail = (3, [55, 55, 12])
    verdict, info = _classify_fit(base, tail)
    assert verdict == "compress"
    assert info["overflow"] == 12


# ---------------------------------------------------------------------------
# Same page count but last page meaningfully short → expand
# ---------------------------------------------------------------------------

def test_same_pages_short_last_triggers_expand():
    base = (2, [55, 50])
    # Tailored last page is much shorter than base last page.
    tail = (2, [55, 20])
    verdict, info = _classify_fit(base, tail)
    assert verdict == "expand"
    assert info["target_pages"] == 2
    assert info["current_pages"] == 2
    assert info["target_fill"] >= 30
    assert info["current_fill"] == 20


def test_same_pages_within_tolerance_is_ok():
    # base last = 50; 15% tolerance → 42 acceptable
    base = (2, [55, 50])
    tail = (2, [55, 45])  # only 10% short
    verdict, _ = _classify_fit(base, tail)
    assert verdict == "ok"


# ---------------------------------------------------------------------------
# Edge case: very short base last page (single line) — full_cap floor kicks in
# ---------------------------------------------------------------------------

def test_short_base_last_uses_full_cap_floor():
    # Base ends with a tiny last page (1 line). Without the floor we'd accept
    # any 1-line tail; with floor at 60% of full_cap (55), target ≈ 33 lines.
    base = (2, [55, 1])
    tail = (2, [55, 5])
    verdict, info = _classify_fit(base, tail)
    assert verdict == "expand"
    assert info["target_fill"] >= int(55 * 0.6)


# ---------------------------------------------------------------------------
# Tolerance constant sanity check
# ---------------------------------------------------------------------------

def test_tolerance_constant_in_range():
    assert 0 < PAGE_FILL_TOLERANCE < 0.5
