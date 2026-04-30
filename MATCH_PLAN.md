# Plan: Resume → Job Match (Layer 1) — DONE 2026-04-30

Reverse direction of the existing tool: given a base resume, rank existing
JDs in `jds/` by fit and surface what's worth applying to.

**Status**: shipped as `match.py` CLI. See "Decisions made" below.

---

## Why this slice first

- `jds/` is already populated by hand from the regular tailor flow — zero
  data-acquisition work to start.
- The hard part is **judgment** ("which 5 of these 30 are worth my time?"),
  not scraping. LLM ranking is the right tool.
- Validates whether ranking changes user behavior before investing in
  Layer 2 (Adzuna / Greenhouse / Lever pulls) or Layer 3 (which we won't
  pursue — LinkedIn / Indeed scraping is anti-pattern).

## CLI shape

```bash
python match.py --resume resumes/jialong_wang.tex
python match.py --resume resumes/jialong_wang.tex --top 10
python match.py --resume resumes/jialong_wang.tex --jds jds/ --auto-tailor
```

Flags:
- `--resume`         (required) base resume tex
- `--jds DIR`        (default `jds/`) directory to scan for `*.txt`/`*.url`
- `--top N`          limit output to N best matches (default: all)
- `--model MODEL`    same routing as `tailor.py` (`sonnet`/`opus`/LiteLLM)
- `--auto-tailor`    run `tailor.py` on the top-N matches (default: off)

## Output

`output/matches_<YYYYMMDD>.md`:

```
# Matches — 2026-04-30

## Top picks
| Rank | Score | Company       | Role                    | Why                      |
|------|-------|---------------|-------------------------|--------------------------|
| 1    | 87    | World Bank    | Product Analyst         | strong project-fin fit…  |
| 2    | 82    | …             | …                       | …                        |

## Detailed
### 1. World Bank — Product Analyst (87)
- Why: …
- Gaps:
  - missing: SQL deep dive
  - missing: agile certifications
- Source: jds/worldbank_product_analyst.txt
```

## Scoring prompt

System rubric (5 dimensions, weighted):
1. **Skill match** (40%) — overlap with resume's hard skills
2. **Experience depth** (20%) — seniority alignment with role's requirements
3. **Domain relevance** (20%) — industry / sector fit
4. **Logistics** (10%) — visa / location / WFH
5. **Trajectory fit** (10%) — does this role advance the user's stated career direction (pulled from `profile.yaml`)

Per-JD output (LLM): `{score: int 0-100, rationale: str ≤ 25 words, gaps: [str, str, str]}`.

Two-pass guard: reject responses that fail JSON parse and re-prompt once.

## Architecture

New files:
- `match.py` — CLI entry point. Reads resume, walks `jds/`, fans out LLM
  calls in parallel via `ThreadPoolExecutor`, sorts, writes report.
- Tests: `tests/test_match.py` — JSON parsing, ranking sort, output formatter.

Modified files:
- `prompts.py` — add `MATCH_SYSTEM` + `MATCH_USER`.

Reused (no changes):
- `llm.call`            — model routing
- `fetch.get_jd`        — JD URL/file resolution
- `build._slugify`      — folder naming
- `build.extract_jd_meta` — pull company/role for the table

Stretch (only if quick): when `--auto-tailor` is on, trigger
`tailor.tailor_with_fit` on each top-N match in parallel and link the
generated PDF in the report.

## Cost / latency

- Per JD: ~1.5 KB prompt → ~$0.003 (sonnet) → ~3-5 s
- 30 JDs in parallel (max_workers=8) → ~15-25 s wall-time → ~$0.10
- 100 JDs → ~$0.30

If the corpus ever exceeds ~200 JDs, add embedding-based pre-filter
(top 30 by cosine sim → LLM-rank). Not needed for the initial version.

## Out of scope (defer)

- **Layer 2: discovery from public APIs**
  - Adzuna API (free 250/day, global) — would let `match.py` pull *new* JDs
    keyed off resume keywords, then run the same ranking
  - HN "Who is hiring" monthly thread — easy parse, dense tech signal
  - Greenhouse / Lever public board JSON — per-company scraping, opt-in
    via `companies.yaml`
- **Layer 3: LinkedIn / Indeed scraping** — not pursued (ToS, anti-bot,
  brittle). User pastes specific URLs into existing `tailor.py` instead.
- **Vector index** — over-engineered for current scale.

## Decisions made (2026-04-30)

1. **Output format**: Markdown only. JSON deferred until a programmatic
   consumer actually exists.
2. **Scoring scale**: 0-100 numeric *plus* derived bucket label
   (`must` ≥80 / `yes` 65-79 / `maybe` 50-64 / `skip` <50). Both shown in
   the report — numeric for sort, bucket for action.
3. **`--auto-tailor` default**: off. Each run spawns 4 parallel LLM calls
   per match → must be explicit opt-in.
4. **Caching**: deferred. With <50 JDs the full re-score is ~$0.10-0.30 and
   trivially fast in parallel. Add when corpus crosses ~50.

## Deviation from original plan

The plan called for two LLM calls per JD: `build.extract_jd_meta` (company
+ role) and a separate scoring call. **Shipped as one combined prompt**
(`MATCH_SYSTEM` + `MATCH_USER`) returning `{company, role, score, rationale,
gaps}` in a single JSON object. Halves token cost and latency. One stricter
retry tolerates transient JSON-parse failures.

## Effort estimate

~1 day. Concretely:
- 2 h — prompt design + small JSON-parse robustness layer
- 2 h — `match.py` CLI + parallelization + output writer
- 1 h — tests (JSON parse, sort, edge-case empty `jds/`)
- 1 h — README update + sample run on existing `jds/` content

No new dependencies. ~200 LOC.
