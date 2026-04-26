"""PDF compilation, output folder management, diff utilities."""

import difflib
import html
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


# ---------------------------------------------------------------------------
# Plan B diff: single-column inline track-changes
# ---------------------------------------------------------------------------

_HTML_EXTRA_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
  :root {
    --bg: #fafaf7; --paper: #ffffff; --ink: #1a1a17; --ink-2: #56534b;
    --ink-3: #8a8780; --line: #e7e5dd;
    --add-bg: #dcfce7; --add-fg: #16a34a;
    --sub-bg: #fee2e2; --sub-fg: #dc2626;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--ink);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.55; }
  body { padding: 56px 24px 120px; }
  .wrap { max-width: 880px; margin: 0 auto; }

  header.doc-header { margin-bottom: 32px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }
  .eyebrow { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace;
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-3); margin-bottom: 10px; }
  h1.title { font-size: 24px; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.015em; }
  .subtitle { font-size: 13px; color: var(--ink-2); }
  .arrow { color: var(--ink-3); margin: 0 6px; }
  .legend { display: flex; gap: 16px; margin-top: 16px; font-size: 12px; color: var(--ink-2); flex-wrap: wrap; }
  .legend .item { display: inline-flex; align-items: center; gap: 7px; }
  .legend .swatch { display: inline-block; width: 14px; height: 10px; border-radius: 2px; }
  .stats { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; font-size: 11px; color: var(--ink-3); }
  .stats .plus { color: var(--add-fg); } .stats .minus { color: var(--sub-fg); }

  .seclabel { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace;
    font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--ink-3); margin: 36px 0 14px; padding-bottom: 6px;
    border-bottom: 1px solid var(--line); font-weight: 500; }
  .seclabel:first-of-type { margin-top: 0; }
  .jobline { font-size: 14px; font-weight: 500; color: var(--ink); margin: 22px 0 10px; }

  .bullet { padding: 6px 0 6px 22px; position: relative; font-size: 14px; line-height: 1.7; }
  .bullet::before { content: '•'; position: absolute; left: 6px; top: 6px; color: var(--ink-3); }
  .para { padding: 4px 0; font-size: 14px; line-height: 1.7; color: var(--ink-2); }

  ins, del { text-decoration: none; }
  ins { background: var(--add-bg); color: var(--add-fg); padding: 1px 3px; border-radius: 2px; }
  del { background: var(--sub-bg); color: var(--sub-fg); padding: 1px 3px; border-radius: 2px;
    text-decoration: line-through; text-decoration-color: rgba(220,38,38,.45); text-decoration-thickness: 1px; }

  .bullet.added { background: linear-gradient(90deg, rgba(220,252,231,.4), transparent 60%);
    border-left: 2px solid var(--add-fg); margin-left: -10px; padding-left: 32px; }
  .bullet.added::before { left: 16px; }
  .bullet.removed { background: linear-gradient(90deg, rgba(254,226,226,.4), transparent 60%);
    border-left: 2px solid var(--sub-fg); margin-left: -10px; padding-left: 32px; }
  .bullet.removed::before { left: 16px; color: var(--sub-fg); }
  .para.removed, .jobline.removed, .seclabel.removed {
    background: linear-gradient(90deg, rgba(254,226,226,.4), transparent 60%);
    border-left: 2px solid var(--sub-fg); margin-left: -10px; padding-left: 10px;
    color: var(--sub-fg); text-decoration: line-through; }
</style>
"""

_WORD_RE = re.compile(r"\s+|\S+")
_BULLET_RE  = re.compile(r"^\s*•\s+(.*)$")
_SECTION_RE = re.compile(r"^\s*===\s*(.+?)\s*===\s*$")
# Matches the subheading format produced by _tex_to_plain: "Company — Role (Year)"
_JOBLINE_SEP = " — "


def _inline_word_diff(a: str, b: str) -> str:
    ta, tb = _WORD_RE.findall(a), _WORD_RE.findall(b)
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    out: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(html.escape("".join(ta[i1:i2])))
        elif tag == "delete":
            out.append("<del>" + html.escape("".join(ta[i1:i2])) + "</del>")
        elif tag == "insert":
            out.append("<ins>" + html.escape("".join(tb[j1:j2])) + "</ins>")
        elif tag == "replace":
            out.append("<del>" + html.escape("".join(ta[i1:i2])) + "</del>")
            out.append("<ins>" + html.escape("".join(tb[j1:j2])) + "</ins>")
    return "".join(out)


def _classify(line: str) -> tuple[str, str]:
    if not line.strip():
        return "blank", ""
    m = _SECTION_RE.match(line)
    if m:
        return "section", m.group(1)
    m = _BULLET_RE.match(line)
    if m:
        return "bullet", m.group(1)
    if _JOBLINE_SEP in line and "(" in line:
        return "jobline", line.strip()
    return "para", line.strip()


_KIND_CLASS = {"section": "seclabel", "jobline": "jobline", "bullet": "bullet", "para": "para"}


def _wrap_line(kind: str, payload_html: str, mod: str = "") -> str:
    if kind == "blank":
        return ""
    cls = _KIND_CLASS.get(kind, "para")
    if mod:
        cls += f" {mod}"
    return f'<div class="{cls}">{payload_html}</div>'


def _render_body(orig_lines: list[str], mod_lines: list[str]) -> tuple[str, int, int]:
    sm = difflib.SequenceMatcher(a=orig_lines, b=mod_lines, autojunk=False)
    out: list[str] = []
    n_ins = n_del = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for line in orig_lines[i1:i2]:
                kind, payload = _classify(line)
                out.append(_wrap_line(kind, html.escape(payload)))

        elif tag == "delete":
            for line in orig_lines[i1:i2]:
                kind, payload = _classify(line)
                if kind == "blank":
                    continue
                n_del += 1
                out.append(_wrap_line(kind, html.escape(payload), mod="removed"))

        elif tag == "insert":
            for line in mod_lines[j1:j2]:
                kind, payload = _classify(line)
                if kind == "blank":
                    continue
                n_ins += 1
                out.append(_wrap_line(kind, html.escape(payload), mod="added" if kind == "bullet" else ""))

        elif tag == "replace":
            block_a = [l for l in orig_lines[i1:i2] if l.strip()]
            block_b = [l for l in mod_lines[j1:j2] if l.strip()]
            paired = min(len(block_a), len(block_b))
            for a_line, b_line in zip(block_a[:paired], block_b[:paired]):
                kind_a, pa = _classify(a_line)
                kind_b, pb = _classify(b_line)
                kind = kind_b if kind_b != "para" else kind_a
                out.append(_wrap_line(kind, _inline_word_diff(pa, pb)))
                n_ins += 1
                n_del += 1
            for line in block_a[paired:]:
                kind, payload = _classify(line)
                n_del += 1
                out.append(_wrap_line(kind, html.escape(payload), mod="removed"))
            for line in block_b[paired:]:
                kind, payload = _classify(line)
                n_ins += 1
                out.append(_wrap_line(kind, html.escape(payload), mod="added" if kind == "bullet" else ""))

    return "\n".join(out), n_ins, n_del


def make_html_diff(
    original: str,
    modified: str,
    *,
    company: str = "",
    role: str = "",
    date: str = "",
) -> str:
    """Return a self-contained Plan-B style diff HTML page."""
    orig_lines = _tex_to_plain(original).splitlines()
    mod_lines  = _tex_to_plain(modified).splitlines()
    body_html, n_ins, n_del = _render_body(orig_lines, mod_lines)

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    subtitle_parts = [p for p in [company.replace("_", " "), role.replace("_", " "), date] if p]
    subtitle = " &nbsp;·&nbsp; ".join(html.escape(p) for p in subtitle_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><title>Resume Changes</title>
{_HTML_EXTRA_CSS}
</head>
<body><div class="wrap">
<header class="doc-header">
  <div class="eyebrow">resume changes</div>
  <h1 class="title">Original <span class="arrow">&rarr;</span> Tailored</h1>
  {f'<div class="subtitle">{subtitle}</div>' if subtitle else ''}
  <div class="legend">
    <span class="item"><span class="swatch" style="background:var(--add-bg)"></span>added</span>
    <span class="item"><span class="swatch" style="background:var(--sub-bg)"></span>removed</span>
    <span class="item stats"><span class="plus">+{n_ins} inserts</span> &nbsp;·&nbsp;
      <span class="minus">&minus;{n_del} removals</span></span>
  </div>
</header>
{body_html}
</div></body></html>
"""
