#!/usr/bin/env python3
"""
resume-tailor: JD → tailored LaTeX resume + human-sounding cover letter.

Usage:
  python tailor.py --jd <url|file|text> --resume resumes/base.tex
  python tailor.py --jd jds/google.txt  --resume resumes/base.tex --no-cover-letter
  python tailor.py --jd https://company.com/job --resume resumes/base.tex --model opus
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import yaml

import build
import fetch
import llm
import word_to_tex
from llm import LLMError
from prompts import (
    COVER_LETTER_SYSTEM,
    COVER_LETTER_USER,
    RESUME_HIGHLIGHTS_PROMPT,
    RESUME_REFIT_COMPRESS,
    RESUME_REFIT_EXPAND,
    RESUME_SYSTEM,
    RESUME_USER,
    STORY_DRAFT_PROMPT,
    STORY_SELECTION_PROMPT,
    STYLE_EXTRACTION_PROMPT,
)

ROOT = Path(__file__).parent

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_yaml(filename: str, default: dict) -> dict:
    p = ROOT / filename
    return yaml.safe_load(p.read_text()) if p.exists() else default


def load_config() -> dict:
    return _load_yaml("config.yaml", {})


def load_profile() -> dict:
    return _load_yaml("profile.yaml", {"name": "Applicant"})


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_path(arg: str) -> Path:
    """Resolve a CLI path argument: try cwd first, then script ROOT."""
    p = Path(arg)
    if p.is_absolute():
        return p
    if p.exists():
        return p
    candidate = ROOT / p
    if candidate.exists():
        return candidate
    return p  # let caller handle missing file


# ---------------------------------------------------------------------------
# Style guide
# ---------------------------------------------------------------------------

SAMPLES_DIR = ROOT / "writing_samples"
STYLE_CACHE = SAMPLES_DIR / "style_guide.md"

DEFAULT_STYLE = """\
Direct and precise. Mixes short punchy observations with longer analytical sentences that
build to a point. Comfortable with nuance; avoids overstatement. Reads like someone who
has thought carefully and is now explaining, not performing. Occasionally dry.
Uses specific examples rather than abstractions. Confident without being boastful."""


def get_style_guide(model: str) -> str:
    if STYLE_CACHE.exists():
        return STYLE_CACHE.read_text(encoding="utf-8")
    samples = [
        f.read_text(encoding="utf-8")
        for f in SAMPLES_DIR.glob("*.txt")
        if f.stat().st_size < 50_000  # skip oversized files
    ]
    if not samples:
        return DEFAULT_STYLE
    print("  [first run] extracting your writing style from samples...")
    guide = llm.call(STYLE_EXTRACTION_PROMPT.format(samples="\n\n---\n\n".join(samples)), model, timeout=120)
    STYLE_CACHE.parent.mkdir(exist_ok=True)
    STYLE_CACHE.write_text(guide, encoding="utf-8")
    return guide


# ---------------------------------------------------------------------------
# Resume tailoring
# ---------------------------------------------------------------------------

def tailor_resume(jd: str, resume_tex: str, model: str) -> str:
    prompt = RESUME_SYSTEM + "\n\n" + RESUME_USER.format(jd=jd, resume=resume_tex)
    return build.strip_tex_fence(llm.call(prompt, model))


# ---------------------------------------------------------------------------
# Page-fit loop
# ---------------------------------------------------------------------------

# Last page may be up to 15% shorter than base before we trigger an expand refit.
PAGE_FILL_TOLERANCE = 0.15

Verdict = Literal["ok", "expand", "compress"]


def _expand_info(target_pages, current_pages, target_fill, current_fill, deficit):
    return "expand", {
        "target_pages": target_pages,
        "current_pages": current_pages,
        "target_fill": target_fill,
        "current_fill": current_fill,
        "deficit": deficit,
    }


def _classify_fit(
    base: tuple[int, list[int]],
    tailored: tuple[int, list[int]],
) -> tuple[Verdict, dict]:
    """Compare metrics. Returns (verdict, info-payload-for-refit-prompt)."""
    base_pages, base_lines = base
    tail_pages, tail_lines = tailored
    full_cap = max(base_lines) if base_lines else 55
    base_last = base_lines[-1] if base_lines else 0
    tail_last = tail_lines[-1] if tail_lines else 0

    if tail_pages > base_pages:
        return "compress", {
            "target_pages": base_pages,
            "current_pages": tail_pages,
            "overflow": sum(tail_lines[base_pages:]),
        }
    if tail_pages < base_pages:
        deficit = (base_pages - tail_pages) * full_cap + max(0, base_last - tail_last)
        return _expand_info(
            base_pages, tail_pages,
            int(full_cap * (1 - PAGE_FILL_TOLERANCE)), tail_last, deficit,
        )
    # same page count — expand only if the last page is meaningfully short
    target_fill = max(int(base_last * (1 - PAGE_FILL_TOLERANCE)), int(full_cap * 0.6))
    if tail_last < target_fill:
        return _expand_info(
            base_pages, tail_pages, target_fill, tail_last, target_fill - tail_last,
        )
    return "ok", {}


def _refit_call(verdict: Verdict, info: dict, jd: str, base_tex: str, current_tex: str, model: str) -> str:
    if verdict == "expand":
        prompt = RESUME_REFIT_EXPAND.format(jd=jd, base=base_tex, current=current_tex, **info)
    else:
        prompt = RESUME_REFIT_COMPRESS.format(current=current_tex, **info)
    return build.strip_tex_fence(llm.call(prompt, model))


def tailor_with_fit(
    jd: str,
    base_tex: str,
    model: str,
    max_retries: int = 2,
) -> tuple[str, bytes | None, str]:
    """Tailor + iteratively refit so the PDF matches the base's page footprint.

    Returns (final_tex, final_pdf_bytes_or_None, summary). The PDF bytes come from
    the last fit-loop compile, so the caller can write them straight to disk and
    avoid a redundant pdflatex run.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        base_future = pool.submit(build.compile_and_measure, base_tex)
        tailored = tailor_resume(jd, base_tex, model)
        base = base_future.result()

    if base is None:
        return tailored, None, "skipped (no LaTeX or pdftotext)"

    base_metrics = (base[0], base[1])
    for attempt in range(max_retries + 1):
        tail = build.compile_and_measure(tailored)
        if tail is None:
            return tailored, None, f"skipped after pass {attempt} (compile failed)"
        verdict, info = _classify_fit(base_metrics, (tail[0], tail[1]))
        terminal = verdict == "ok" or attempt == max_retries
        if terminal:
            status = "ok" if verdict == "ok" else f"gave up ({verdict})"
            summary = (
                f"target {base[0]}p/{base[1][-1]}L · "
                f"got {tail[0]}p/{tail[1][-1]}L · {status} pass {attempt}"
            )
            return tailored, tail[2], summary
        print(f"  refit  : pass {attempt+1} → {verdict} (target {info['target_pages']}p)")
        tailored = _refit_call(verdict, info, jd, base_tex, tailored, model)

    raise RuntimeError("unreachable")  # max_retries < 0


# ---------------------------------------------------------------------------
# Story bank
# ---------------------------------------------------------------------------

def load_stories() -> list[dict]:
    p = ROOT / "story_bank.yaml"
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text(encoding="utf-8")).get("stories", [])


def pick_story(jd: str, stories: list[dict], model: str) -> dict | None:
    if not stories:
        return None
    if len(stories) == 1:
        return stories[0]
    stories_text = "\n\n".join(
        f"id: {s['id']}\ntags: {s.get('tags', [])}\ntext: {s['text'].strip()}"
        for s in stories
    )
    chosen_id = llm.call(
        STORY_SELECTION_PROMPT.format(stories=stories_text, jd=jd[:1500]),
        model, timeout=120,
    ).strip().strip('"').strip("'")
    return next((s for s in stories if s["id"] == chosen_id), stories[0])


def draft_stories(resume_tex: str, jd_text: str, model: str) -> list[dict]:
    """Draft candidate STAR stories from a resume + JD, for users who haven't
    written any of their own yet. Returns a list of {id, tags, text} dicts."""
    raw = llm.call(
        STORY_DRAFT_PROMPT.format(resume=resume_tex, jd=jd_text[:3000]),
        model, timeout=180,
    )
    m = re.search(r"\[\s*\{.*\}\s*\]", raw, re.S)
    if not m:
        raise LLMError("Could not parse drafted stories — try again.")
    try:
        items = json.loads(m.group())
    except json.JSONDecodeError as e:
        raise LLMError("Could not parse drafted stories — try again.") from e
    out = []
    for i, s in enumerate(items, 1):
        text = (s.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "id":   s.get("id") or f"draft_{i}",
            "tags": [t for t in (s.get("tags") or []) if isinstance(t, str)],
            "text": text,
        })
    return out


# ---------------------------------------------------------------------------
# Cover letter generation
# ---------------------------------------------------------------------------

def generate_cover_letter(
    jd: str,
    resume_tex: str,
    meta: build.JDMeta,
    model: str,
    profile: dict,
    style_guide: str,
    stories: list[dict] | None = None,
) -> str:
    name = profile.get("name", "Applicant")

    with ThreadPoolExecutor(max_workers=2) as pool:
        story_future = pool.submit(pick_story, jd, stories if stories is not None else load_stories(), model)
        highlights_future = pool.submit(
            llm.call,
            RESUME_HIGHLIGHTS_PROMPT.format(role=meta.role, company=meta.company, resume=resume_tex),
            model, 120,
        )
        story = story_future.result()
        resume_highlights = highlights_future.result()

    story_text = story["text"].strip() if story else "(no story available)"
    print(f"  story  : {story['id'] if story else 'none'}")

    profile_text = "\n".join(
        f"{k.upper()}: {v.strip()}"
        for k, v in profile.items()
        if k != "name" and v
    )
    system = COVER_LETTER_SYSTEM.format(name=name, style_guide=style_guide, profile=profile_text)
    user = COVER_LETTER_USER.format(
        story=story_text, jd=jd, resume_highlights=resume_highlights, name=name,
    )
    return llm.call(system + "\n\n" + user, model)


# ---------------------------------------------------------------------------
# Side-task helpers (invoked from main, in parallel)
# ---------------------------------------------------------------------------

def _build_diffs(resume_tex: str, tailored_tex: str, meta: build.JDMeta, out_dir: Path) -> int:
    diff = build.make_diff(resume_tex, tailored_tex)
    if not diff:
        return 0
    changed = sum(1 for ln in diff.splitlines() if ln.startswith(("+ ", "- ")))
    (out_dir / "resume.diff").write_text(diff, encoding="utf-8")
    (out_dir / "resume_changes.html").write_text(
        build.make_html_diff(
            resume_tex, tailored_tex,
            company=meta.company, role=meta.role,
        ),
        encoding="utf-8",
    )
    return changed


def _build_cover_letter(
    jd_text: str, resume_tex: str, meta: build.JDMeta, model: str, profile: dict,
) -> str:
    style_guide = get_style_guide(model)
    return generate_cover_letter(jd_text, resume_tex, meta, model, profile, style_guide)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cfg = load_config()
    profile = load_profile()

    ap = argparse.ArgumentParser(
        description="Tailor LaTeX resume + generate cover letter for a job",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python tailor.py --resume resumes/base.tex --jd jds/google.txt
  python tailor.py --resume resumes/base.tex --jd https://jobs.lever.co/company/role
  python tailor.py --resume resumes/base.tex --jd jds/mckinsey.txt --no-cover-letter
""",
    )
    ap.add_argument("--resume", required=True, help="Base resume: .tex or .docx")
    ap.add_argument("--jd", required=True, help="JD: URL, file path, or pasted text")
    ap.add_argument("--model", default=cfg.get("model", "sonnet"),
                    help="'sonnet'/'opus' or LiteLLM model string (e.g. ollama/llama3.1)")
    ap.add_argument("--no-cover-letter", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-diff", action="store_true")
    ap.add_argument("--template", default=None,
                    help="LaTeX template to use when converting from .docx (default: sample_resume.tex)")
    args = ap.parse_args()

    resume_path = _resolve_path(args.resume)
    if not resume_path.exists():
        sys.exit(f"Resume not found: {resume_path}")

    print("[resume-tailor]")
    print(f"  model  : {args.model}")

    if resume_path.suffix.lower() == ".docx":
        template_path = _resolve_path(args.template) if args.template else None
        print("  converting Word → LaTeX...")
        resume_tex = word_to_tex.convert(resume_path, args.model, template_path)
        tex_out = ROOT / "resumes" / resume_path.with_suffix(".tex").name
        tex_out.write_text(resume_tex, encoding="utf-8")
        print(f"  saved  : resumes/{tex_out.name}  (reuse with --resume resumes/{tex_out.name})")
    else:
        resume_tex = resume_path.read_text(encoding="utf-8")

    jd_arg = args.jd
    if not jd_arg.startswith(("http://", "https://")):
        jd_arg = str(_resolve_path(jd_arg))
    jd_text = fetch.get_jd(jd_arg)
    jd_label = args.jd if len(args.jd) < 60 else args.jd[:57] + "..."
    print(f"  jd     : {jd_label}")

    base_dir = ROOT / cfg.get("output_dir", "output")
    print("  parallel: meta + tailor (+ cover letter, diff)...")

    with ThreadPoolExecutor(max_workers=4) as pool:
        meta_future = pool.submit(build.extract_jd_meta, jd_text, args.model)
        tailor_future = pool.submit(tailor_with_fit, jd_text, resume_tex, args.model)

        # Cover letter prompt embeds {role}/{company}, so it needs meta — but it
        # does NOT depend on the tailored tex, so kick it off as soon as meta lands.
        meta = meta_future.result()
        out_dir = build.output_folder(meta, base_dir)
        print(f"  folder : {out_dir}")
        cl_future = (
            pool.submit(_build_cover_letter, jd_text, resume_tex, meta, args.model, profile)
            if not args.no_cover_letter else None
        )

        tailored_tex, fit_pdf_bytes, fit_summary = tailor_future.result()
        tex_path = out_dir / "resume.tex"
        tex_path.write_text(tailored_tex, encoding="utf-8")
        print(f"  saved  : {tex_path.name}")
        print(f"  fit    : {fit_summary}")

        diff_future = (
            pool.submit(_build_diffs, resume_tex, tailored_tex, meta, out_dir)
            if not args.no_diff else None
        )

        if not args.no_pdf:
            pdf_path = tex_path.with_suffix(".pdf")
            if fit_pdf_bytes:
                pdf_path.write_bytes(fit_pdf_bytes)
                print(f"  pdf    : {pdf_path.name}")
            elif build.compile_pdf(tex_path):
                print(f"  pdf    : {pdf_path.name}")
            else:
                print("  pdf    : skipped (pdflatex not found — install TeX Live or MiKTeX)")

        if diff_future is not None:
            changed = diff_future.result()
            if changed:
                print(f"  diff   : resume_changes.html  ({changed} lines changed)")

        if cl_future is not None:
            cover_letter = cl_future.result()
            cl_path = out_dir / "cover_letter.md"
            cl_path.write_text(cover_letter, encoding="utf-8")
            print(f"  saved  : {cl_path.name}")

    print(f"\n  done → {out_dir}/")
    for f in sorted(out_dir.iterdir()):
        print(f"    {f.name}")


if __name__ == "__main__":
    try:
        main()
    except LLMError as e:
        sys.exit(str(e))


