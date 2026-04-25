# resume-tailor

Tailor a LaTeX resume to a job description and generate a human-sounding cover letter — locally, with no server required.

**What it does:**
1. Reads your job description (URL, file, or pasted text)
2. Rewrites your resume bullets to match JD keywords — without fabricating anything
3. Generates a cover letter in your personal voice, using a story you've pre-written

**What it doesn't do:** invent skills, change your job titles, or write a cover letter that sounds like ChatGPT.

---

## Requirements

- **Python 3.11+**
- **[Claude Code CLI](https://claude.ai/code)** — the `claude` command must be in your PATH  
  *(or set `model` in `config.yaml` to a LiteLLM-compatible model string like `openai/gpt-4o`)*
- **LaTeX** (optional, for PDF output) — install [BasicTeX](https://www.tug.org/mactex/morepackages.html) or [TeX Live](https://tug.org/texlive/)

---

## Setup

```bash
git clone https://github.com/Waaangjl/resume-tailor
cd resume-tailor
pip install -r requirements.txt
```

### 1. Add your resume

Put your LaTeX resume in `resumes/`. A sample Jake-style template is at `resumes/sample_resume.tex`.

### 2. Fill in your profile

```bash
cp profile.example.yaml profile.yaml
```

Edit `profile.yaml`. This is what makes the cover letter sound like you. Be honest and specific — vague answers produce generic letters.

### 3. Fill in your story bank

```bash
cp story_bank.example.yaml story_bank.yaml
```

Edit `story_bank.yaml`. Write 3–8 real moments from your career. The tool picks the most relevant one automatically per job. You fill this once and reuse it forever.

### 4. (Optional) Add writing samples for style matching

Drop `.txt` files of your own writing into `writing_samples/`. On the first run the tool extracts a style guide and caches it at `writing_samples/style_guide.md`. If this directory is empty, a sensible default style is used.

### 5. (Optional) Switch LLM

Edit `config.yaml`:

```yaml
# Use a LiteLLM-compatible string to switch providers
model: openai/gpt-4o        # needs OPENAI_API_KEY in env
model: ollama/llama3.1      # local, needs Ollama running
model: sonnet               # default — uses claude -p CLI
```

---

## Usage

```bash
# From a file
python tailor.py --resume resumes/your_resume.tex --jd jds/company_role.txt

# From a URL
python tailor.py --resume resumes/your_resume.tex --jd https://jobs.lever.co/company/role

# Skip cover letter
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --no-cover-letter

# Skip PDF compilation
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --no-pdf

# Use a different model
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --model opus
```

Output lands in `output/<Company>_<Role>_<date>/`:

```
output/Acme_Software_Engineer_20260101/
  resume.tex       ← tailored LaTeX
  resume.pdf       ← compiled PDF (if LaTeX installed)
  resume.diff      ← what changed from your base resume
  cover_letter.md  ← cover letter in Markdown
```

---

## Project layout

```
resume-tailor/
├── tailor.py              # main CLI
├── build.py               # PDF compilation, folder management, diff
├── fetch.py               # fetch JD from URL or file
├── llm.py                 # LLM backend (claude -p or LiteLLM)
├── prompts.py             # all LLM prompts
├── config.yaml            # model + output_dir settings
├── profile.example.yaml   # → copy to profile.yaml
├── story_bank.example.yaml → copy to story_bank.yaml
├── resumes/
│   └── sample_resume.tex  # Jake-style template to start from
├── writing_samples/       # (optional) .txt files in your voice
└── output/                # generated output (gitignored)
```

---

## How it works

### Resume tailoring

The LLM rewrites bullet text to incorporate JD keywords where the underlying fact is unchanged. It cannot add skills, change titles/dates, or invent metrics. Every run produces a `.diff` so you can see exactly what changed.

### Cover letter

The cover letter is built in three steps:
1. **Story selection** — the LLM picks the most relevant story from your bank for this JD
2. **Resume highlights** — the LLM condenses your `.tex` to plain-text talking points
3. **Letter generation** — the LLM writes a 3-paragraph, 280–320 word letter in your voice

Steps 1 and 2 run in parallel. The cover letter prompt bans hollow phrases ("passionate about", "leverage", "synergies", etc.) and requires dramatic sentence-length variation.

### Writing style

If you put `.txt` files of your own writing in `writing_samples/`, the tool extracts a style guide on the first run and caches it. This guide is injected into every cover letter prompt.

---

## Running tests

```bash
pip install pytest
pytest tests/
```

---

## License

MIT
