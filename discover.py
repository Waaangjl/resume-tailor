#!/usr/bin/env python3
"""
discover.py: pull fresh JDs from Adzuna based on a base resume.

Usage:
  python discover.py --resume resumes/your_resume.tex
  python discover.py --resume resumes/your_resume.tex --query "ML engineer"
  python discover.py --resume resumes/your_resume.tex --country gb --where London
  python discover.py --resume resumes/your_resume.tex --match     # chain match.py
  python discover.py --resume resumes/your_resume.tex --dry-run   # no writes
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import fetch
import llm
import secrets as secrets_mod
from llm import LLMError
from prompts import DISCOVER_KEYWORDS_PROMPT
from tailor import _resolve_path, load_config, load_profile

ROOT = Path(__file__).parent

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"
ADZUNA_MAX_PER_PAGE = 50

# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def extract_titles(resume_tex: str, profile_text: str, model: str) -> list[str]:
    """Ask the LLM for 3-5 plausible job titles. Raises LLMError if unparseable."""
    raw = llm.call(
        DISCOVER_KEYWORDS_PROMPT.format(resume=resume_tex, profile=profile_text),
        model, timeout=120,
    )
    titles = parse_titles_response(raw)
    if not titles:
        raise LLMError("LLM returned no titles — try --query \"job title\"")
    return titles


def parse_titles_response(raw: str) -> list[str]:
    """Extract list of titles from an LLM response. Returns [] on failure."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("titles") or []
    if not isinstance(items, list):
        return []
    return [str(t).strip() for t in items if t is not None and str(t).strip()][:5]


# ---------------------------------------------------------------------------
# Adzuna client
# ---------------------------------------------------------------------------

def adzuna_search(
    *, country: str, app_id: str, app_key: str,
    titles: list[str], where: str, distance_km: int,
    days: int, results_per_page: int,
    remote_only: bool,
) -> list[dict]:
    """Call Adzuna search API. Returns the raw result dicts."""
    params = {
        "app_id":           app_id,
        "app_key":          app_key,
        "results_per_page": min(results_per_page, ADZUNA_MAX_PER_PAGE),
        # Adzuna's what_or accepts comma-separated terms; titles with spaces
        # work as phrase-ish matches. urlencode handles escaping.
        "what_or":          ",".join(titles),
        "max_days_old":     days,
        "content-type":     "application/json",
    }
    if where:
        params["where"]    = where
        params["distance"] = distance_km

    url = f"{ADZUNA_BASE}/{country}/search/1?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "resume-tailor"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise LLMError(
                "Adzuna 401 — credentials rejected. Rotate keys at "
                "https://developer.adzuna.com/ and update secrets.yaml."
            ) from e
        if e.code == 429:
            raise LLMError("Adzuna 429 — daily 250-call budget exhausted; try tomorrow.") from e
        body = e.read().decode("utf-8", errors="replace")[:200]
        raise LLMError(f"Adzuna HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"Adzuna network error: {e.reason}") from e

    results = data.get("results") or []
    if remote_only:
        results = [r for r in results if looks_remote(r)]
    return results


_REMOTE_RE = re.compile(r"\b(remote|work[\s-]?from[\s-]?home|wfh|telecommute)\b", re.I)


def looks_remote(r: dict) -> bool:
    title = r.get("title") or ""
    desc  = r.get("description") or ""
    return bool(_REMOTE_RE.search(title) or _REMOTE_RE.search(desc[:500]))


# ---------------------------------------------------------------------------
# JD file formatting + persistence
# ---------------------------------------------------------------------------

def format_jd_file(r: dict) -> str:
    """Format an Adzuna result as a JD file (header + body)."""
    company  = (r.get("company")  or {}).get("display_name") or "Unknown"
    location = (r.get("location") or {}).get("display_name") or ""
    posted   = (r.get("created")  or "")[:10]  # YYYY-MM-DD
    title    = r.get("title")        or ""
    url      = r.get("redirect_url") or ""
    salary   = _format_salary(r)
    body     = fetch._strip_html(r.get("description") or "")

    header = [
        f"Company: {company}",
        f"Role: {title}",
        f"Location: {location}",
        f"Posted: {posted}",
    ]
    if salary:
        header.append(f"Salary: {salary}")
    if url:
        header.append(f"Source: {url}")
    return "\n".join(header) + "\n---\n\n" + body + "\n"


def _format_salary(r: dict) -> str:
    smin, smax = r.get("salary_min"), r.get("salary_max")
    if smin and smax:
        return f"${int(smin):,}-${int(smax):,}"
    if smin:
        return f"${int(smin):,}+"
    return ""


def write_new_jds(results: list[dict], jds_dir: Path) -> tuple[int, int]:
    """Persist new JDs, skipping those whose adzuna_<id>.txt already exists.

    Returns (n_new_written, n_skipped_existing).
    """
    jds_dir.mkdir(parents=True, exist_ok=True)
    n_new = n_skipped = 0
    for r in results:
        ad_id = r.get("id")
        if not ad_id:
            continue
        path = jds_dir / f"adzuna_{ad_id}.txt"
        if path.exists():
            n_skipped += 1
            continue
        path.write_text(format_jd_file(r), encoding="utf-8")
        n_new += 1
    return n_new, n_skipped


# ---------------------------------------------------------------------------
# Profile formatting (mirrors match.py — keep them aligned)
# ---------------------------------------------------------------------------

def _format_profile(profile: dict) -> str:
    parts = [
        f"{k.upper()}: {v.strip()}"
        for k, v in profile.items()
        if isinstance(v, str) and v.strip() and k.lower() != "name"
    ]
    return "\n".join(parts) or "(no profile.yaml provided)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cfg = load_config()
    profile = load_profile()

    ap = argparse.ArgumentParser(
        description="Pull fresh JDs from Adzuna and drop them into jds/.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python discover.py --resume resumes/jialong_wang.tex
  python discover.py --resume resumes/jialong_wang.tex --query "ML engineer,data scientist"
  python discover.py --resume resumes/jialong_wang.tex --country gb --where London
  python discover.py --resume resumes/jialong_wang.tex --dry-run
  python discover.py --resume resumes/jialong_wang.tex --match
""",
    )
    ap.add_argument("--resume", required=True, help="Base resume .tex (used for keyword extraction)")
    ap.add_argument("--query",  default=None,
                    help="Override LLM keyword extraction (comma-separated job titles)")
    ap.add_argument("--country", default=None,
                    help="Adzuna country code (us/gb/ca/au/sg/de/nl/in/...)")
    ap.add_argument("--where",   default=None, help="City / state filter (empty = nationwide)")
    ap.add_argument("--distance", type=int, default=None, help="Search radius in km")
    ap.add_argument("--days",   type=int, default=14, help="Only JDs posted within N days (default: 14)")
    ap.add_argument("--limit",  type=int, default=50,
                    help=f"Max results to save (default 50, capped at {ADZUNA_MAX_PER_PAGE} for MVP)")
    ap.add_argument("--remote-only", action="store_true", help="Only keep JDs that look remote")
    ap.add_argument("--match",       action="store_true", help="After saving, run match.py")
    ap.add_argument("--dry-run",     action="store_true", help="Call Adzuna but do not write files")
    ap.add_argument("--model", default=cfg.get("model", "sonnet"),
                    help="Model for keyword extraction")
    args = ap.parse_args()

    if args.limit < 1:
        sys.exit(f"--limit must be >= 1 (got {args.limit})")
    if args.days < 1:
        sys.exit(f"--days must be >= 1 (got {args.days})")

    app_id, app_key = secrets_mod.adzuna_creds()
    if not app_id or not app_key:
        sys.exit(
            "Missing Adzuna credentials.\n"
            "  Option 1: cp secrets.example.yaml secrets.yaml  (then fill in app_id + app_key)\n"
            "  Option 2: export ADZUNA_APP_ID=...  ADZUNA_APP_KEY=...\n"
            "  Get keys at https://developer.adzuna.com/"
        )

    defaults = secrets_mod.adzuna_defaults()
    country = (args.country or defaults.get("country", "us")).lower()
    where = args.where if args.where is not None else defaults.get("where", "") or ""
    distance_km = args.distance if args.distance is not None else defaults.get("distance_km", 50)

    resume_path = _resolve_path(args.resume)
    if not resume_path.exists():
        sys.exit(f"Resume not found: {resume_path}")
    if resume_path.suffix.lower() != ".tex":
        sys.exit(f"Resume must be .tex (got {resume_path.suffix}): {resume_path}")
    resume_tex = resume_path.read_text(encoding="utf-8")
    profile_text = _format_profile(profile)

    print("[discover]")
    print(f"  resume : {resume_path.name}")
    print(f"  region : {country}{(' / ' + where) if where else ' (nationwide)'}, {distance_km}km")

    if args.query:
        titles = [t.strip() for t in args.query.split(",") if t.strip()]
        if not titles:
            sys.exit("--query is empty after splitting on commas")
        print(f"  titles : {titles}  (manual)")
    else:
        print("  titles : extracting from resume...")
        titles = extract_titles(resume_tex, profile_text, args.model)
        print(f"  titles : {titles}  (LLM)")

    print(f"  adzuna : calling {country} (days≤{args.days}, limit={args.limit})...")
    results = adzuna_search(
        country=country, app_id=app_id, app_key=app_key,
        titles=titles, where=where, distance_km=distance_km,
        days=args.days, results_per_page=args.limit,
        remote_only=args.remote_only,
    )
    print(f"  adzuna : {len(results)} result(s) returned")

    jds_dir = ROOT / "jds"

    if args.dry_run:
        print("\n  [dry-run] would write:")
        for r in results[: args.limit]:
            ad_id   = r.get("id") or "?"
            company = (r.get("company") or {}).get("display_name", "?")
            title   = r.get("title", "?")
            mark    = "skip" if (jds_dir / f"adzuna_{ad_id}.txt").exists() else "new"
            print(f"    [{mark}] adzuna_{ad_id}.txt  {company} — {title}")
        return

    n_new, n_skipped = write_new_jds(results[: args.limit], jds_dir)
    print(f"\n  saved  : {n_new} new · {n_skipped} already in jds/")

    if args.match:
        if n_new == 0:
            print("  match  : skipped (no new JDs)")
            return
        print("\n[match] running match.py on full jds/ ...")
        subprocess.run(
            [sys.executable, str(ROOT / "match.py"),
             "--resume", str(resume_path),
             "--model",  args.model],
            check=False,
        )


if __name__ == "__main__":
    try:
        main()
    except LLMError as e:
        sys.exit(str(e))
