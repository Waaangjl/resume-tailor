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


# ---------------------------------------------------------------------------
# Human-readable HTML diff
# ---------------------------------------------------------------------------

def _tex_to_plain(tex: str) -> str:
    """Strip LaTeX commands, return readable plain text for diffing."""
    tex = re.sub(r'%[^\n]*', '', tex)                                   # comments
    tex = re.sub(r'\\section\{([^}]+)\}', r'\n=== \1 ===\n', tex)      # section headings
    tex = re.sub(                                                         # job/edu subheadings
        r'\\resumeSubheading\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{[^}]*\}',
        r'\n\1 — \3 (\2)', tex,
    )
    tex = re.sub(                                                         # project headings
        r'\\resumeProjectHeading\{([^}]*)\}\{[^}]*\}',
        r'\n\1', tex,
    )
    tex = re.sub(r'\\resumeItem\{([^}]+)\}', r'  • \1', tex)            # bullets
    tex = re.sub(r'\\[a-zA-Z]+\*?\{([^}]*)\}', r'\1', tex)             # other {content} cmds
    tex = re.sub(r'\\[a-zA-Z@]+\*?', '', tex)                           # bare commands
    tex = re.sub(r'[{}$&#^_~]', '', tex)                                # special chars
    tex = re.sub(r'\n{3,}', '\n\n', tex)
    tex = re.sub(r'[ \t]+', ' ', tex)
    return tex.strip()


_HTML_EXTRA_CSS = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         font-size: 14px; background: #fafafa; margin: 0; padding: 24px; }
  h2   { font-size: 15px; color: #333; margin: 0 0 16px; }
  p    { color: #666; font-size: 13px; margin: 0 0 20px; }
  table.diff { border-collapse: collapse; width: 100%; background: #fff;
               border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden;
               box-shadow: 0 1px 4px rgba(0,0,0,.06); }
  td   { padding: 3px 10px; vertical-align: top; white-space: pre-wrap;
         word-break: break-word; font-family: "SF Mono", Consolas, monospace;
         font-size: 12.5px; border: 1px solid #f0f0f0; }
  td.diff_header { background: #f5f5f5; color: #888; font-size: 11px;
                   text-align: right; width: 36px; padding: 3px 6px; }
  th   { background: #f0f0f0; padding: 6px 10px; font-size: 12px;
         text-align: left; color: #555; }
  span.diff_add  { background: #d4f0d4; }
  span.diff_chg  { background: #fff0b3; }
  span.diff_sub  { background: #ffd4d4; }
  td.diff_add    { background: #f0fff0; }
  td.diff_chg    { background: #fffff0; }
  td.diff_sub    { background: #fff0f0; }
  td.diff_next   { background: #e8e8e8; }
</style>
"""


def make_html_diff(original: str, modified: str) -> str:
    """Return a self-contained HTML file showing a readable side-by-side diff."""
    orig_lines = _tex_to_plain(original).splitlines()
    mod_lines  = _tex_to_plain(modified).splitlines()
    differ = difflib.HtmlDiff(wrapcolumn=72)
    html = differ.make_file(
        orig_lines, mod_lines,
        fromdesc="Original resume",
        todesc="Tailored resume",
        context=True,
        numlines=2,
    )
    # inject nicer CSS right before </head>
    html = html.replace("</head>", _HTML_EXTRA_CSS + "</head>", 1)
    return html
