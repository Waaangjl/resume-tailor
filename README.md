# resume-tailor

[中文说明](README.zh.md)

**AI-powered LaTeX resume tailoring and cover letter generator for job applications.**

Paste a job description → get a tailored `.tex` resume + human-sounding cover letter in under 2 minutes. Runs locally with no server. Uses [Claude Code](https://claude.ai/code) (`claude -p`) by default, or any OpenAI/Ollama/LiteLLM-compatible model.

**What it does:**
1. Extracts keywords and requirements from any job description (URL, file, or pasted text)
2. Rewrites your resume bullets to match — without fabricating skills, changing titles, or inflating metrics
3. Generates a cover letter in your personal voice using a story bank you write once and reuse forever

**What it doesn't do:** invent skills, change job titles or dates, or produce a cover letter that sounds like it was written by an AI.

> Works with any LaTeX resume. Includes a [Jake's Resume](https://github.com/jakegut/resume)-style template to get started.

---

## Requirements

- **Python 3.11+**
- **[Claude Code CLI](https://claude.ai/code)** — the `claude` command must be in your PATH  
  *(or set `model` in `config.yaml` to a LiteLLM model string like `openai/gpt-4o` or `ollama/llama3.1`)*
- **LaTeX** (optional, for PDF compilation) — [BasicTeX](https://www.tug.org/mactex/morepackages.html) (140 MB) or [TeX Live](https://tug.org/texlive/)

---

## Quick start

**New to this?** Clone the repo, open [SETUP_PROMPT.md](SETUP_PROMPT.md), and paste the prompt into Claude Code or Codex. The AI will walk you through the full setup interactively — no manual file editing required.

**Familiar with the project?**

```bash
git clone https://github.com/Waaangjl/resume-tailor
cd resume-tailor
pip install -r requirements.txt

# Set up your profile and story bank
cp profile.example.yaml profile.yaml
cp story_bank.example.yaml story_bank.yaml

# Run on a job description URL or file
python tailor.py --resume resumes/your_resume.tex --jd https://jobs.lever.co/company/role
python tailor.py --resume resumes/your_resume.tex --jd jds/google_swe.txt
```

Output lands in `output/<Company>_<Role>_<date>/`:

```
output/Google_Software_Engineer_20260101/
  resume.tex       ← tailored LaTeX resume
  resume.pdf       ← compiled PDF (if LaTeX installed)
  resume.diff      ← exactly what changed from your base
  cover_letter.md  ← cover letter in Markdown
```

---

## Setup

### 1. Add your resume

**Have a Word document?** Pass it directly — the tool converts it automatically:

```bash
python tailor.py --resume resumes/your_resume.docx --jd jds/role.txt
```

A `.tex` version is saved to `resumes/` automatically for future runs.

**Want a specific template?** Browse [Overleaf's resume template gallery](https://www.overleaf.com/latex/templates?q=resume), open one you like, download the source (menu → Download Source), and drop the `.tex` file into `resumes/`. Any standard LaTeX resume works.

**Built-in templates** (pick one as a starting point):

| File | Best for |
|------|----------|
| `resumes/sample_resume.tex` | Tech / SWE / data / PM |
| `resumes/template_finance.tex` | Finance / consulting (education-first, Leadership section) |
| `resumes/template_with_summary.tex` | Career changers or candidates with 3+ years of experience |

### 2. Fill in your profile

```bash
cp profile.example.yaml profile.yaml
```

Edit `profile.yaml` with your background, motivation, and edge. This is injected into every cover letter — the more specific you are, the better it sounds.

### 3. Fill in your story bank

```bash
cp story_bank.example.yaml story_bank.yaml
```

Write 3–8 real moments from your career. Each story is 2–4 sentences — one specific thing you observed, did, or realized. The tool picks the most relevant story per job description automatically. Fill this once, reuse forever.

### 4. (Optional) Add writing samples for style matching

Drop `.txt` files of your own writing into `writing_samples/`. On first run, the tool extracts a personal style guide and caches it. If the directory is empty, a sensible default style is used.

### 5. (Optional) Switch LLM

Edit `config.yaml`:

```yaml
model: sonnet               # default — uses claude -p CLI (no API key needed)
model: openai/gpt-4o        # needs OPENAI_API_KEY in env
model: ollama/llama3.1      # fully local, needs Ollama running
model: anthropic/claude-sonnet-4-5  # direct Anthropic API (needs ANTHROPIC_API_KEY)
```

---

## Usage

```bash
# Tailor from a URL
python tailor.py --resume resumes/your_resume.tex --jd https://jobs.lever.co/company/role

# Tailor from a saved job description file
python tailor.py --resume resumes/your_resume.tex --jd jds/company_role.txt

# Resume only, no cover letter
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --no-cover-letter

# Skip PDF compilation
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --no-pdf

# Use a specific model
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --model opus
```

---

## How it works

### Resume tailoring

The LLM rewrites bullet point text to incorporate JD keywords where the underlying fact is unchanged. Hard constraints: no new skills, no changed titles or dates, no invented metrics. Every run produces a `.diff` so you can see exactly what changed before submitting.

### Cover letter generation

Built in three steps (steps 1 and 2 run in parallel):
1. **Story selection** — picks the most relevant story from your bank for this specific JD
2. **Resume highlights** — condenses your `.tex` to plain-text talking points
3. **Letter generation** — writes a 3-paragraph, 280–320 word letter in your voice

The cover letter prompt explicitly bans hollow phrases ("passionate about", "leverage", "synergies", "results-driven", "thought leader") and requires dramatic sentence-length variation to avoid sounding AI-generated.

### ATS keyword optimization

The resume tailoring prompt prioritizes: (1) most recent experience bullets, (2) Skills section keyword density, (3) older experience, (4) research. It rewrites in STAR format (Situation→Task→Action→Result) when possible and reorders bullets within each job to put the most JD-relevant ones first.

---

## Project layout

```
resume-tailor/
├── tailor.py               # JD → tailored resume + cover letter
├── match.py                # rank existing jds/ against a base resume
├── discover.py             # pull fresh JDs from Adzuna into jds/
├── build.py                # PDF compilation, folder management, diff
├── fetch.py                # fetch JD from URL or local file
├── llm.py                  # LLM backend (claude -p or LiteLLM)
├── prompts.py              # all LLM prompts
├── secrets.py              # env + yaml secret loader
├── config.yaml             # model + output_dir config
├── profile.example.yaml    # → copy to profile.yaml and fill in
├── secrets.example.yaml    # → copy to secrets.yaml and fill in (Adzuna keys)
├── story_bank.example.yaml # → copy to story_bank.yaml and fill in
├── resumes/
│   └── sample_resume.tex   # Jake-style LaTeX template
├── writing_samples/        # (optional) .txt files in your voice
├── jds/                    # (gitignored) your saved job descriptions
└── output/                 # (gitignored) tailored resumes + match reports
```

---

## Discovering jobs from Adzuna

Pull fresh JDs from Adzuna based on your resume and drop them into `jds/` so `match.py` can rank them:

```bash
python discover.py --resume resumes/your_resume.tex
python discover.py --resume resumes/your_resume.tex --query "ML engineer,data scientist"
python discover.py --resume resumes/your_resume.tex --country gb --where London
python discover.py --resume resumes/your_resume.tex --dry-run    # call API, don't write
python discover.py --resume resumes/your_resume.tex --match      # chain match.py after
```

**Setup** (one-time):

1. Get free credentials at [developer.adzuna.com](https://developer.adzuna.com/) (250 calls/day)
2. `cp secrets.example.yaml secrets.yaml` and fill in `app_id` + `app_key` (or set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` env vars — env wins over yaml)

**How it works**:

1. LLM extracts 3-5 plausible **job titles** from your resume (not skills — skill matching is `match.py`'s job)
2. Hits Adzuna's search API with `what_or=<titles>`, `where`, `distance`, `max_days_old`
3. Writes new results to `jds/adzuna_<id>.txt` (header: company / role / location / posted / salary / URL; body: stripped JD text)
4. Dedups by filename **and** by `(company, title)` within a batch — Adzuna often returns 10-20 identical postings under different ids
5. Optional `--match` chains `match.py` on the full `jds/` corpus

**Flags**:
- `--query Q` — comma-separated job titles, skips LLM extraction
- `--country C` / `--where W` / `--distance N` — override `secrets.yaml` defaults
- `--days N` — only include JDs posted within N days (default: 14)
- `--limit N` — max results per run (default + cap: 50)
- `--remote-only` — keep only listings that look remote
- `--dry-run` — call Adzuna once, print what would be saved, don't write
- `--match` — run `match.py` after saving

**Coverage gap**: Adzuna does not cover China mainland. For CN roles, use `tailor.py` directly with pasted URLs (Layer 4 will add Greenhouse/Lever public boards later).

---

## Ranking JDs against your resume

Once you've collected a few JDs in `jds/`, rank them by fit before deciding which to tailor:

```bash
python match.py --resume resumes/your_resume.tex
python match.py --resume resumes/your_resume.tex --top 10
python match.py --resume resumes/your_resume.tex --auto-tailor
```

Output lands in `output/matches_<YYYYMMDD>.md`:

```
| Rank | Score | Bucket | Company    | Role            | Why                          |
| 1    | 87    | must   | World Bank | Product Analyst | strong project-fin fit, ...  |
| 2    | 64    | maybe  | …          | …               | …                            |
```

Each entry has a 0-100 score, a bucket label (`must` ≥80, `yes` 65-79, `maybe` 50-64, `skip` <50), a one-line rationale, and 2-3 concrete gaps.

**`jds/` accepts**:
- `*.txt` — pasted JD text
- `*.url` — single URL on the first line; the tool fetches and parses it

**Flags**:
- `--top N` — only keep the N best matches (also caps `--auto-tailor`)
- `--model` — same routing as `tailor.py`
- `--auto-tailor` — run `tailor.py` on each top-N match after ranking (off by default)

Cost: ~$0.003/JD on Sonnet via `claude -p`, runs 8 in parallel. 30 JDs → ~20s wall time, ~$0.10.

---

## Running tests

```bash
pip install pytest
pytest tests/
```

147 tests covering HTML parsing, URL fetching, LaTeX fence stripping, diff generation, LLM routing, JD match scoring, secrets loading, and Adzuna client + dedup.

---

## Related

- [Jake's Resume](https://github.com/jakegut/resume) — LaTeX template this tool is designed to work with
- [Claude Code](https://claude.ai/code) — the `claude -p` CLI used as the default LLM backend
- [LiteLLM](https://github.com/BerriAI/litellm) — optional drop-in for OpenAI, Ollama, and other providers

---

## License

MIT
