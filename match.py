#!/usr/bin/env python3
"""
match.py: rank JDs in jds/ by fit against a base resume.

Usage:
  python match.py --resume resumes/your_resume.tex
  python match.py --resume resumes/base.tex --top 10
  python match.py --resume resumes/base.tex --auto-tailor
"""

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import fetch
import llm
from llm import LLMError
from prompts import MATCH_SYSTEM, MATCH_USER
from tailor import _resolve_path, load_config, load_profile

ROOT = Path(__file__).parent

# (label, lower-bound). Order from highest to lowest.
BUCKETS = [("must", 80), ("yes", 65), ("maybe", 50), ("skip", 0)]


def bucket_for(score: int) -> str:
    for label, threshold in BUCKETS:
        if score >= threshold:
            return label
    return "skip"


def load_jd(path: Path) -> str:
    """Load JD text from a .txt or .url file. .url files contain a single URL."""
    if path.suffix.lower() == ".url":
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"empty .url file: {path.name}")
        url = content.splitlines()[0].strip()
        return fetch.get_jd(url)
    return path.read_text(encoding="utf-8")


def parse_match_response(raw: str) -> dict | None:
    """Extract a match-score JSON object from an LLM response.

    Returns a normalized dict with keys company/role/score/rationale/gaps, or
    None if the response cannot be parsed into a valid score record.
    """
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "score" not in data:
        return None
    try:
        score = int(data["score"])
    except (TypeError, ValueError):
        return None
    gaps = data.get("gaps") or []
    if not isinstance(gaps, list):
        gaps = []
    return {
        "company":   str(data.get("company") or "Unknown").strip() or "Unknown",
        "role":      str(data.get("role") or "Unknown").strip() or "Unknown",
        "score":     max(0, min(100, score)),
        "rationale": str(data.get("rationale") or "").strip(),
        "gaps":      [str(g).strip() for g in gaps if g is not None and str(g).strip()],
    }


def score_jd(jd_path: Path, resume: str, profile_text: str, model: str) -> dict | None:
    """Score one JD. Returns dict with company/role/score/rationale/gaps/source, or None on failure."""
    try:
        jd = load_jd(jd_path)
    except Exception as e:
        sys.stderr.write(f"  skip   : {jd_path.name} ({type(e).__name__}: {e})\n")
        return None
    if not jd.strip():
        return None

    base_prompt = MATCH_SYSTEM + "\n\n" + MATCH_USER.format(
        profile=profile_text, resume=resume, jd=jd[:8000],
    )
    raw = llm.call(base_prompt, model, timeout=180)
    data = parse_match_response(raw)
    if data is None:
        # one stricter retry — the original framing already says "ONLY JSON",
        # so a bare reminder is enough without doubling token spend
        retry = base_prompt + "\n\nReturn ONLY the JSON object. No prose, no markdown."
        raw = llm.call(retry, model, timeout=180)
        data = parse_match_response(raw)
    if data is None:
        sys.stderr.write(f"  skip   : {jd_path.name} (could not parse LLM response)\n")
        return None
    data["source"] = str(jd_path)
    return data


def collect_jd_paths(jds_dir: Path) -> list[Path]:
    return sorted(
        p for p in jds_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".txt", ".url")
    )


def render_report(matches: list[dict], resume_name: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    if not matches:
        return f"# Matches — {date}\n\nNo JDs scored.\n"

    lines = [
        f"# Matches — {date}",
        "",
        f"Resume: `{resume_name}` · {len(matches)} JD(s) scored",
        "",
        "## Top picks",
        "",
        "| Rank | Score | Bucket | Company | Role | Why |",
        "|------|-------|--------|---------|------|-----|",
    ]
    for i, m in enumerate(matches, 1):
        why = m["rationale"].replace("|", "/")
        lines.append(
            f"| {i} | {m['score']} | {bucket_for(m['score'])} | "
            f"{m['company']} | {m['role']} | {why} |"
        )

    lines += ["", "## Detailed", ""]
    for i, m in enumerate(matches, 1):
        bucket = bucket_for(m["score"])
        lines.append(f"### {i}. {m['company']} — {m['role']} ({m['score']} · {bucket})")
        lines.append("")
        if m["rationale"]:
            lines.append(f"**Why**: {m['rationale']}")
            lines.append("")
        if m["gaps"]:
            lines.append("**Gaps**:")
            lines += [f"- {g}" for g in m["gaps"]]
            lines.append("")
        lines.append(f"**Source**: `{m['source']}`")
        lines.append("")
    return "\n".join(lines)


def _format_profile(profile: dict) -> str:
    parts = [
        f"{k.upper()}: {v.strip()}"
        for k, v in profile.items()
        if isinstance(v, str) and v.strip() and k.lower() != "name"
    ]
    return "\n".join(parts) or "(no profile.yaml provided)"


def main():
    cfg = load_config()
    profile = load_profile()

    ap = argparse.ArgumentParser(
        description="Rank JDs by fit against a base resume.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python match.py --resume resumes/jialong_wang.tex
  python match.py --resume resumes/jialong_wang.tex --top 10
  python match.py --resume resumes/jialong_wang.tex --auto-tailor
""",
    )
    ap.add_argument("--resume", required=True, help="Base resume .tex file")
    ap.add_argument("--jds",    default="jds",
                    help="Directory of JD .txt/.url files (default: jds/)")
    ap.add_argument("--top",    type=int, default=None,
                    help="Limit output (and --auto-tailor) to top N matches (must be >= 1)")
    ap.add_argument("--model",  default=cfg.get("model", "sonnet"),
                    help="'sonnet'/'opus' or LiteLLM model string")
    ap.add_argument("--auto-tailor", action="store_true",
                    help="Run tailor.py on each top-N match after ranking (off by default)")
    args = ap.parse_args()

    if args.top is not None and args.top < 1:
        sys.exit(f"--top must be >= 1 (got {args.top})")

    resume_path = _resolve_path(args.resume)
    if not resume_path.exists():
        sys.exit(f"Resume not found: {resume_path}")
    if resume_path.suffix.lower() != ".tex":
        sys.exit(f"Resume must be a .tex file (got {resume_path.suffix}): {resume_path}")
    resume_tex = resume_path.read_text(encoding="utf-8")

    jds_dir = _resolve_path(args.jds)
    if not jds_dir.is_dir():
        sys.exit(f"JDs directory not found: {jds_dir}")

    jd_paths = collect_jd_paths(jds_dir)
    if not jd_paths:
        sys.exit(f"No .txt or .url files found in {jds_dir}/")

    profile_text = _format_profile(profile)

    print("[match]")
    print(f"  model  : {args.model}")
    print(f"  resume : {resume_path.name}")
    print(f"  jds    : {jds_dir} ({len(jd_paths)} file(s))")

    matches: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(score_jd, p, resume_tex, profile_text, args.model): p
            for p in jd_paths
        }
        for fut in as_completed(futures):
            jd_path = futures[fut]
            try:
                m = fut.result()
            except LLMError as e:
                sys.stderr.write(f"  skip   : {jd_path.name} ({e})\n")
                continue
            if m is not None:
                matches.append(m)
                print(f"  scored : {jd_path.name} → {m['score']} ({bucket_for(m['score'])})")

    matches.sort(key=lambda m: m["score"], reverse=True)
    if args.top:
        matches = matches[: args.top]

    base_dir = ROOT / cfg.get("output_dir", "output")
    base_dir.mkdir(parents=True, exist_ok=True)
    out_path = base_dir / f"matches_{datetime.now().strftime('%Y%m%d')}.md"
    out_path.write_text(render_report(matches, resume_path.name), encoding="utf-8")
    print(f"\n  done → {out_path}")

    if args.auto_tailor and matches:
        print(f"\n[auto-tailor] running tailor.py on {len(matches)} match(es) sequentially...")
        for m in matches:
            print(f"  → {m['company']} — {m['role']} ({m['score']})")
            subprocess.run(
                [sys.executable, str(ROOT / "tailor.py"),
                 "--resume", str(resume_path),
                 "--jd",     m["source"],
                 "--model",  args.model],
                check=False,
            )


if __name__ == "__main__":
    try:
        main()
    except LLMError as e:
        sys.exit(str(e))
