# All LLM prompts for resume-tailor.

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
