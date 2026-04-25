"""PDF compilation, output folder management, diff utilities."""

import difflib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import llm
from prompts import JD_META_PROMPT


class JDMeta(NamedTuple):
    company: str
    role: str


def extract_jd_meta(jd_text: str, model: str) -> JDMeta:
    """Ask LLM to extract company and role name from a job description."""
    try:
        raw = llm.call(JD_META_PROMPT.format(jd=jd_text[:3000]), model, timeout=60)
        m = re.search(r'\{[^}]+\}', raw)
        data = json.loads(m.group()) if m else {}
        return JDMeta(
            company=_slugify(data.get("company", "")),
            role=_slugify(data.get("role", "")),
        )
    except Exception:
        return JDMeta("", "")


def output_folder(meta: JDMeta, base_dir: Path) -> Path:
    """Create and return a named output folder from JD metadata."""
    date = datetime.now().strftime("%Y%m%d")
    parts = [p for p in [meta.company, meta.role, date] if p]
    name = "_".join(parts) if parts else f"application_{date}"
    folder = base_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _slugify(s: str) -> str:
    s = s.strip().replace(" ", "_").replace("&", "and")
    s = re.sub(r"[^a-zA-Z0-9_-]", "", s)
    return s[:40]


@lru_cache(maxsize=1)
def _find_latex() -> str | None:
    """Find pdflatex/xelatex; result is cached for the process lifetime."""
    candidate = shutil.which("pdflatex") or shutil.which("xelatex")
    if candidate:
        return candidate
    years = (2026, 2025)
    editions = ("", "basic")
    for year in years:
        for ed in editions:
            prefix = f"/usr/local/texlive/{year}{ed}/bin/universal-darwin"
            for name in ("pdflatex", "xelatex"):
                p = Path(prefix) / name
                if p.exists():
                    return str(p)
    for name in ("pdflatex", "xelatex"):
        p = Path("/Library/TeX/texbin") / name
        if p.exists():
            return str(p)
    return None


def compile_pdf(tex_path: Path) -> Path | None:
    """Compile .tex to PDF. Returns PDF path, or None if LaTeX not installed."""
    compiler = _find_latex()
    if not compiler:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        shutil.copy(tex_path, tmp_path / tex_path.name)
        try:
            for _ in range(2):  # two passes so cross-references resolve
                subprocess.run(
                    [compiler, "-interaction=nonstopmode", tex_path.name],
                    cwd=tmp_path,
                    capture_output=True,
                    timeout=60,
                )
            pdf_tmp = tmp_path / tex_path.with_suffix(".pdf").name
            if pdf_tmp.exists():
                pdf_out = tex_path.with_suffix(".pdf")
                shutil.copy(pdf_tmp, pdf_out)
                return pdf_out
        except Exception:
            pass
    return None


def strip_tex_fence(text: str) -> str:
    """Remove markdown fences and any preamble/postamble the model added."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
        if text.endswith("```"):
            text = text[:-3].rstrip()
    for marker in ("%----", "%---", "\\documentclass", "%!TEX"):
        idx = text.find(marker)
        if idx > 0:
            text = text[idx:]
            break
    end_doc = text.rfind("\\end{document}")
    if end_doc != -1:
        text = text[:end_doc + len("\\end{document}")]
    return text.strip()


def make_diff(original: str, modified: str) -> str:
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile="original.tex",
        tofile="tailored.tex",
        n=2,
    ))
