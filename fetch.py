"""Fetch job description text from a URL or file."""

import html
import json
import re
import urllib.request
from pathlib import Path

from llm import LLMError


def get_jd(source: str) -> str:
    """Return JD text from a URL, file path, or raw string."""
    if source.startswith(("http://", "https://")):
        return _fetch_url(source)
    p = Path(source)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return source  # treat as raw pasted text


_WORKDAY_RE = re.compile(r"myworkdayjobs\.com", re.I)
_LD_JSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _try_workday(raw: str) -> str:
    """Extract job description from Workday JSON-LD structured data."""
    for block in _LD_JSON_RE.findall(raw):
        try:
            data = json.loads(block)
            desc = data.get("description", "")
            if desc:
                title = data.get("title", "")
                org = data.get("hiringOrganization", {}).get("name", "")
                header = f"{title} at {org}\n\n" if title else ""
                return header + _strip_html(desc)
        except (json.JSONDecodeError, AttributeError):
            continue
    return ""


def _fetch_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise LLMError(f"Could not fetch URL: {e}\nPaste the JD text directly instead.") from e
    if _WORKDAY_RE.search(url):
        text = _try_workday(raw)
        if text:
            return text
    return _strip_html(raw)


_RE_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_RE_TAGS = re.compile(r"<[^>]+>")
_RE_SPACES = re.compile(r"[ \t]+")
_RE_NEWLINES = re.compile(r"\n{3,}")


def _strip_html(raw: str) -> str:
    raw = _RE_SCRIPT.sub(" ", raw)
    text = _RE_TAGS.sub(" ", raw)
    text = _RE_SPACES.sub(" ", text)
    text = _RE_NEWLINES.sub("\n\n", text)
    return html.unescape(text).strip()
