#!/usr/bin/env python3
"""
resume-tailor: JD → tailored LaTeX resume + human-sounding cover letter.

Usage:
  python tailor.py --jd <url|file|text> --resume resumes/base.tex
  python tailor.py --jd jds/google.txt  --resume resumes/base.tex --no-cover-letter
  python tailor.py --jd https://company.com/job --resume resumes/base.tex --model opus
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
    RESUME_SYSTEM,
    RESUME_USER,
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
    stories_text = "\n\n".join(
        f"id: {s['id']}\ntags: {s.get('tags', [])}\ntext: {s['text'].strip()}"
        for s in stories
    )
    chosen_id = llm.call(
        STORY_SELECTION_PROMPT.format(stories=stories_text, jd=jd[:1500]),
        model, timeout=60,
    ).strip().strip('"').strip("'")
    return next((s for s in stories if s["id"] == chosen_id), stories[0])


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
) -> str:
    name = profile.get("name", "Applicant")

    # pick_story and resume_highlights are independent — run in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        story_future = pool.submit(pick_story, jd, load_stories(), model)
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

    if resume_path.suffix.lower() == ".docx":
        template_path = _resolve_path(args.template) if args.template else None
        print("[resume-tailor]")
        print(f"  model  : {args.model}")
        print("  converting Word → LaTeX...")
        resume_tex = word_to_tex.convert(resume_path, args.model, template_path)
        tex_out = ROOT / "resumes" / resume_path.with_suffix(".tex").name
        tex_out.write_text(resume_tex, encoding="utf-8")
        print(f"  saved  : resumes/{tex_out.name}  (reuse with --resume resumes/{tex_out.name})")
    else:
        resume_tex = resume_path.read_text(encoding="utf-8")

    if resume_path.suffix.lower() != ".docx":
        print("[resume-tailor]")
        print(f"  model  : {args.model}")

    jd_arg = args.jd
    if not jd_arg.startswith(("http://", "https://")):
        jd_arg = str(_resolve_path(jd_arg))
    jd_text = fetch.get_jd(jd_arg)
    jd_label = args.jd if len(args.jd) < 60 else args.jd[:57] + "..."
    print(f"  jd     : {jd_label}")

    print("  naming output folder...")
    meta = build.extract_jd_meta(jd_text, args.model)
    base_dir = ROOT / cfg.get("output_dir", "output")
    out_dir = build.output_folder(meta, base_dir)
    print(f"  folder : {out_dir}")

    print("  tailoring resume...")
    tailored_tex = tailor_resume(jd_text, resume_tex, args.model)
    tex_path = out_dir / "resume.tex"
    tex_path.write_text(tailored_tex, encoding="utf-8")
    print(f"  saved  : {tex_path.name}")

    if not args.no_pdf:
        pdf_path = build.compile_pdf(tex_path)
        if pdf_path:
            print(f"  pdf    : {pdf_path.name}")
        else:
            print("  pdf    : skipped (pdflatex not found — install TeX Live or MiKTeX)")

    if not args.no_diff:
        diff = build.make_diff(resume_tex, tailored_tex)
        if diff:
            changed = sum(1 for ln in diff.splitlines() if ln.startswith(("+ ", "- ")))
            diff_path = out_dir / "resume.diff"
            diff_path.write_text(diff, encoding="utf-8")
            html_path = out_dir / "resume_changes.html"
            html_path.write_text(build.make_html_diff(resume_tex, tailored_tex), encoding="utf-8")
            print(f"  diff   : resume_changes.html  ({changed} lines changed)")

    if not args.no_cover_letter:
        style_guide = get_style_guide(args.model)
        print("  writing cover letter...")
        cover_letter = generate_cover_letter(jd_text, resume_tex, meta, args.model, profile, style_guide)
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


