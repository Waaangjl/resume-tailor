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

Put your `.tex` resume in `resumes/`. A sample Jake-style template is at `resumes/sample_resume.tex` if you need a starting point.

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
├── tailor.py               # main CLI entry point
├── build.py                # PDF compilation, folder management, diff
├── fetch.py                # fetch JD from URL or local file
├── llm.py                  # LLM backend (claude -p or LiteLLM)
├── prompts.py              # all LLM prompts
├── config.yaml             # model + output_dir config
├── profile.example.yaml    # → copy to profile.yaml and fill in
├── story_bank.example.yaml # → copy to story_bank.yaml and fill in
├── resumes/
│   └── sample_resume.tex   # Jake-style LaTeX template
├── writing_samples/        # (optional) .txt files in your voice
├── jds/                    # (gitignored) your saved job descriptions
└── output/                 # (gitignored) generated tailored resumes
```

---

## Running tests

```bash
pip install pytest
pytest tests/
```

38 tests covering HTML parsing, URL fetching, LaTeX fence stripping, diff generation, and LLM routing.

---

## Related

- [Jake's Resume](https://github.com/jakegut/resume) — LaTeX template this tool is designed to work with
- [Claude Code](https://claude.ai/code) — the `claude -p` CLI used as the default LLM backend
- [LiteLLM](https://github.com/BerriAI/litellm) — optional drop-in for OpenAI, Ollama, and other providers

---

## License

MIT
