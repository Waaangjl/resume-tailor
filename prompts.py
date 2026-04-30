# All LLM prompts for resume-tailor.

# ---------------------------------------------------------------------------
# Word → LaTeX conversion
# ---------------------------------------------------------------------------

WORD_TO_LATEX_PROMPT = """\
Convert the resume text below into a complete LaTeX resume file.

Use the template provided as your structural guide — keep every \\command, \\resumeItem, \
\\resumeSubheading, and environment exactly as shown in the template. \
Only swap in the candidate's real content.

STRICT RULES:
1. Preserve EVERY fact from the original: dates, company names, job titles, metrics, skills
2. Do NOT add, invent, or drop any information
3. Map content to the correct commands:
   - Jobs/internships/education → \\resumeSubheading{{Company}}{{Date}}{{Title}}{{Location}}
   - Bullet points → \\resumeItem{{...}}
   - Projects → \\resumeProjectHeading
   - Skills → the \\begin{{itemize}} block at the bottom
4. If the original has a section the template lacks (e.g. Publications, Certifications), \
add it following the same \\section + \\resumeSubHeadingListStart pattern
5. Return ONLY the complete .tex file. No explanation. No markdown fences. \
Start with the very first character of the file.

TEMPLATE (use this exact LaTeX structure):
{template}

RESUME TEXT TO CONVERT:
{resume_text}"""

# ---------------------------------------------------------------------------
# Resume tailoring
# ---------------------------------------------------------------------------

RESUME_SYSTEM = """You are an expert resume consultant specializing in ATS optimization and targeted resume writing.

Your task: tailor a LaTeX resume to better match a specific job description.

STRICT RULES — violating any of these is unacceptable:
1. NEVER add skills, tools, projects, or experiences not already in the original
2. NEVER change job titles, company names, dates, or degree information
3. NEVER invent or inflate metrics
4. Do NOT add or remove \\resumeItem entries — only rewrite the text inside existing ones

WHAT YOU MAY DO:
- Reword \\resumeItem bullet text to incorporate JD keywords where the underlying fact is unchanged
- Reorder \\resumeItem bullets within a job block to put the most JD-relevant ones first
- Reorder items in the Skills / Strengths section to front-load the most relevant tools
- Strengthen STAR format (Situation→Task→Action→Result) on existing bullets
- If a summary/objective section exists, rewrite it for this specific role

SECTION PRIORITIES (most to least important to modify):
1. Most recent job / internship bullet points — highest ATS signal
2. Skills & Strengths section — keyword density
3. Older experience bullets — only if a direct keyword match exists
4. Research experience — preserve academic language; only light keyword additions
5. Education / Leadership — do not modify

LaTeX-specific: preserve every \\command, {{brace}}, and environment exactly — only change plain prose text inside them.

Return ONLY the complete modified .tex file. No explanation. No markdown fences. Begin with the very first character of the file."""

RESUME_USER = """\
=== JOB DESCRIPTION ===
{jd}

=== MY RESUME (.tex) ===
{resume}"""

# ---------------------------------------------------------------------------
# Page-fit refit prompts
# ---------------------------------------------------------------------------

RESUME_REFIT_EXPAND = """\
The tailored resume below currently produces a PDF that is shorter than the target.
TARGET: exactly {target_pages} full page(s); the last page must be at least {target_fill} non-blank lines.
CURRENT: {current_pages} page(s), last page has {current_fill} non-blank lines (deficit ~{deficit} lines).

Expand the existing bullets so the resume fills the target. Do this by:
- Restoring substantive detail from the BASE resume into bullets that were trimmed
- Lengthening each \\resumeItem's prose with concrete specifics already present in the base
- NEVER inventing facts, metrics, skills, tools, or experiences not in the base
- KEEPING the exact same number of \\resumeItem entries as the current tailored version
- KEEPING all section structure, \\command names, and brace nesting unchanged

=== JOB DESCRIPTION ===
{jd}

=== BASE RESUME (source of truth for facts) ===
{base}

=== CURRENT TAILORED RESUME (expand this) ===
{current}

Return ONLY the complete modified .tex file. No explanation. No markdown fences."""

RESUME_REFIT_COMPRESS = """\
The tailored resume below currently produces a PDF that is longer than the target.
TARGET: exactly {target_pages} full page(s).
CURRENT: {current_pages} page(s) (overflow ~{overflow} lines on the extra page).

Compress bullet prose to fit on exactly {target_pages} page(s). Do this by:
- Shortening the most verbose bullets — strip redundant phrasing, prefer specifics over connectives
- KEEPING the exact same number of \\resumeItem entries
- KEEPING all factual content: companies, dates, titles, metrics, technologies
- KEEPING all section structure, \\command names, and brace nesting unchanged
- Avoiding unbreakable strings (no super-long URLs / unhyphenated tokens that LaTeX cannot break across lines)

=== CURRENT TAILORED RESUME (compress this) ===
{current}

Return ONLY the complete modified .tex file. No explanation. No markdown fences."""

# ---------------------------------------------------------------------------
# JD metadata extraction (company name + role title for folder naming)
# ---------------------------------------------------------------------------

JD_META_PROMPT = """\
Extract the company name and job title from this job description.
Return ONLY a JSON object with two keys: "company" and "role".
Example: {{"company": "McKinsey", "role": "Business Analyst"}}
Use short names (no "& Company", no "Inc.", no "LLC").
If you cannot determine one, use "Unknown".

Job description:
{jd}"""

# ---------------------------------------------------------------------------
# Writing style extraction (run once on user's writing samples)
# ---------------------------------------------------------------------------

STYLE_EXTRACTION_PROMPT = """\
Analyze the writing samples below and extract a concise personal style guide.

Focus on:
1. Sentence rhythm — short and punchy? long and reflective? how does this person mix them?
2. Tone — formal, casual, dry, warm, direct, measured?
3. Vocabulary — simple words or complex? any characteristic word choices?
4. Structural habits — how do they open paragraphs? how do they close arguments?
5. Personality signals — confident, self-deprecating, curious, analytical?
6. What makes their writing feel distinctly theirs (NOT generic)?

Output a style guide of 150-200 words that can be given to an LLM to reproduce this person's voice.
Be specific. Quote 2-3 short phrases from the samples as examples.

WRITING SAMPLES:
{samples}"""

# ---------------------------------------------------------------------------
# Story drafting — generate candidate stories from the resume when the user
# hasn't written any yet
# ---------------------------------------------------------------------------

STORY_DRAFT_PROMPT = """\
You are drafting candidate cover-letter opening stories for a job applicant who
has not written any of their own yet. Use ONLY facts from their resume below;
the JD is context for which experiences to emphasize.

STRICT RULES:
1. Use ONLY experiences, projects, metrics, companies, and dates that appear in
   the resume. Do NOT invent anything.
2. Each story is one specific moment — a project, a decision, a finding, a
   tradeoff — not a general claim about the person.
3. Each story is 50-80 words, 2-4 sentences. No bullet points.
4. Write in first person, plain prose, no markdown.
5. Do NOT use any of these words: leverage, passionate, dedicated, results-driven,
   fast-paced, innovative, holistic, synergies, impactful, spearheaded.
6. Generate TWO distinct stories highlighting different experiences. Each gets
   2-3 short tags from this list (lowercase, no spaces): research, engineering,
   data, ml, leadership, finance, consulting, strategy, startup, policy, product.
7. Mark each story with id "draft_1" and "draft_2".
8. The user will edit them, so leave anything you're unsure about as a clearly
   editable placeholder in [brackets] rather than fabricating.

Return ONLY a JSON array, no preamble, no markdown fences:
[
  {{"id": "draft_1", "tags": ["...", "..."], "text": "..."}},
  {{"id": "draft_2", "tags": ["...", "..."], "text": "..."}}
]

=== RESUME ===
{resume}

=== JOB DESCRIPTION ===
{jd}"""

# ---------------------------------------------------------------------------
# Story selection — pick the best story from the bank for a given JD
# ---------------------------------------------------------------------------

STORY_SELECTION_PROMPT = """\
You are choosing the best opening story for a cover letter.

Here are the available stories (each has an id and tags):
{stories}

Job description:
{jd}

Pick the ONE story that would make the strongest, most natural opening for a cover letter
for this specific role. Consider: relevance to the role, strength as a hook, specificity.

Return ONLY the story id. Nothing else. Example: citic_policy_judgment"""

# ---------------------------------------------------------------------------
# Cover letter generation
# ---------------------------------------------------------------------------

COVER_LETTER_SYSTEM = """\
You are writing a cover letter on behalf of {name}.
Write in their authentic personal voice — not a generic professional tone.

MANDATORY STYLE RULES (each violation makes it sound AI-generated):
1. VARY sentence length dramatically. Short punchy sentences. Then longer reflective ones that show real thought. Then short again. Never three sentences the same length in a row.
2. BANNED WORDS — do not use any of these:
   leverage, synergies, passionate about, dedicated to, results-driven, team player,
   fast-paced environment, thought leader, game-changer, proven track record,
   delighted to apply, I am writing to express my interest, excited to announce,
   holistic approach, paradigm shift, innovative, best practices, end-to-end,
   seamlessly, robust, streamline, impactful, spearheaded (unless quoting resume directly)
3. NO em-dashes (—). Use commas, semicolons, or short sentences instead.
4. NO bullet points. This is a letter, not a slide deck.
5. Opening paragraph: use the provided story as the hook. Adapt its wording naturally — do not copy verbatim, but do not change the facts.
6. Reference ONE detail from the JD that most applicants would overlook or ignore.
7. Length: exactly 3 paragraphs, 280-320 words total.
8. Close with genuine curiosity about the work — not "I look forward to hearing from you."

THEIR WRITING STYLE:
{style_guide}

BACKGROUND (use these facts — do not invent others):
{profile}"""

COVER_LETTER_USER = """\
Opening story to use (adapt naturally, keep the facts):
{story}

Job Description:
{jd}

Key points from their resume relevant to this role:
{resume_highlights}

Write the cover letter now. 280-320 words. Sound like {name} wrote it after actually reading the JD."""

# ---------------------------------------------------------------------------
# Resume highlights extraction (condense .tex → readable summary for CL prompt)
# ---------------------------------------------------------------------------

RESUME_HIGHLIGHTS_PROMPT = """\
From this LaTeX resume, extract the 5-7 most relevant achievements and experiences for the following job description.
Write them as plain sentences (no LaTeX, no bullets, no markdown).
Be concrete — keep numbers and specifics from the original.

Job: {role} at {company}

Resume (.tex):
{resume}"""
