# Plan: Resume → Job Discovery (Layer 2, Adzuna)

Active discovery: given a base resume, pull fresh JDs from public APIs and
drop them into `jds/` so `match.py` can rank them.

This is **Layer 2** of the staged plan in `MATCH_PLAN.md`. Layer 1 (rank
existing JDs) shipped on 2026-04-30 as `match.py`.

---

## Why Adzuna first

- Free 250 calls/day, one app key per developer
- Single API covers 18 countries (US, GB, CA, AU, SG, DE, NL, IN, etc.)
- Stable, official API — no scraping, no ToS risk
- One credential, one endpoint shape — minimum surface area for MVP

**What Adzuna does NOT cover**: China mainland. Once Jialong returns to
Shenzhen, Layer 4 (Greenhouse / Lever public boards) becomes the
substitute. MVP scope is the OPT-window job search.

---

## CLI shape

```bash
python discover.py --resume resumes/jialong_wang.tex
python discover.py --resume resumes/jialong_wang.tex --query "ESG analyst"
python discover.py --resume resumes/jialong_wang.tex --country gb --limit 30
python discover.py --resume resumes/jialong_wang.tex --match           # chain to match.py
```

**Flags**:

| Flag | Default | Purpose |
|------|---------|---------|
| `--resume`        | required          | Base resume `.tex` for keyword extraction |
| `--query Q`       | (LLM extracts)    | Override LLM keyword extraction with manual query |
| `--country C`     | from `secrets.yaml` (us) | Adzuna country code (us/gb/ca/au/sg/de/nl/in/...) |
| `--where W`       | from `secrets.yaml` (empty = nationwide) | City / state |
| `--distance N`    | 50                | Search radius in km (Adzuna `distance` param) |
| `--days N`        | 14                | Only include JDs posted within last N days |
| `--limit N`       | 50                | Max new JDs to save per run (Adzuna max page = 50) |
| `--remote-only`   | off               | Filter to remote roles |
| `--match`         | off               | Chain into `match.py` after saving |
| `--model M`       | from `config.yaml`| Used for keyword extraction (cheap call) |
| `--dry-run`       | off               | Show what would be saved, don't write files or call API |

---

## Decisions — the 5 design points

### 1. Keywords → "role titles" extracted from resume, not skills

LLM extracts **3-5 plausible job titles** the candidate could fill. These
are joined with `OR` into Adzuna's `what_or` parameter.

**Why titles, not skills**:
- Adzuna search is text matching across the JD. Skills AND'd → near-zero
  hits ("python AND tensorflow AND aws AND docker AND kubernetes" → 3 hits).
  Skills OR'd → too noisy.
- Job titles are the market's vocabulary. A "Climate Finance Analyst" JD
  reliably contains the phrase "climate finance" or "ESG analyst" in the
  title or first paragraph.
- Skill-level matching is `match.py`'s job downstream.

**Manual override**: `--query "..."` skips LLM extraction. Useful when
candidate is changing direction (resume says "energy analyst" but they
want "ML engineer" roles).

**New prompt** (added to `prompts.py`):

```
DISCOVER_KEYWORDS_PROMPT — given resume text, return JSON
{"titles": ["...", "...", "..."]} with 3-5 plausible job titles
the candidate could realistically apply to. Use only their
demonstrated experience, no aspirational stretches.
```

### 2. Location → `secrets.yaml` config + CLI override

```yaml
adzuna:
  app_id:  "..."
  app_key: "..."
  country: us
  where: ""           # empty = nationwide
  distance_km: 50
```

Country is required (Adzuna's per-country endpoint design). `where` empty
means nationwide search. CLI `--country/--where/--distance` override
config per run.

**Why config not flag**: location is a stable preference, not a per-run
decision. Defaults belong in config.

### 3. Result count + time window → 50 results / 14 days, configurable

Adzuna single page = 50 results max. Default 14 days is recent enough to
matter, wide enough to backfill the first run.

**Pagination**: not in MVP. If `--limit > 50`, paginate up to 4 pages
(200 max), warn if Adzuna says more results exist. 250/day budget covers
this.

### 4. Dedup → filename-based, no separate cache

JDs land at `jds/adzuna_<adzuna_id>.txt`. Before each fetch:

```python
if (jds_dir / f"adzuna_{ad['id']}.txt").exists():
    skip
```

`jds/` IS the cache. Deleting a file = "re-evaluate this JD next run".
No `.discover_seen.json`, no SQLite, no schema migrations. The simplest
thing that works.

### 5. JD file format → header + body

```
Company: Acme Corp
Role: Senior Climate Finance Analyst
Location: Washington, DC
Posted: 2026-04-28
Salary: $120K-$160K (if available)
Source: https://www.adzuna.com/...
---

[full JD body here]
```

Header is regular text — `match.py`'s `load_jd` reads the whole file as
JD context. The model sees the header naturally; humans get a quick
preview without opening the URL.

**Filename namespace**: prefix-by-source so future layers don't collide.
- `adzuna_<id>.txt`     ← Layer 2
- `hn_<thread>_<comment>.txt`  ← Layer 3
- `greenhouse_<co>_<id>.txt`   ← Layer 4

---

## Architecture

**New files**:
- `discover.py` — CLI entry. Loads secrets, extracts keywords (or uses
  `--query`), calls Adzuna, dedups against `jds/`, writes new JD files.
- `secrets.example.yaml` — template; user copies → `secrets.yaml`
- `tests/test_discover.py` — keyword parsing, Adzuna response shape,
  filename dedup, JD formatter, env-var-vs-yaml secret loading.

**Modified files**:
- `prompts.py` — add `DISCOVER_KEYWORDS_PROMPT`
- `.gitignore` — add `secrets.yaml`
- `requirements.txt` — `requests` (Adzuna API client)
- `README.md` — "Discovering jobs" section

**Reused (no changes)**:
- `llm.call`             — model routing for keyword extraction
- `fetch._strip_html`    — clean Adzuna's `description` HTML
- `match.py` (via `--match` flag, subprocess call)

---

## Adzuna API call shape

```
GET https://api.adzuna.com/v1/api/jobs/{country}/search/1
  ?app_id={app_id}
  &app_key={app_key}
  &results_per_page=50
  &what_or=climate+finance+analyst,ESG+analyst,sustainability+consultant
  &where={where}
  &distance={distance_km}
  &max_days_old={days}
  &content-type=application/json
```

Response shape (per result):
```json
{
  "id": "4567890123",
  "title": "Senior Climate Finance Analyst",
  "company": {"display_name": "Acme Corp"},
  "location": {"display_name": "Washington, DC"},
  "salary_min": 120000, "salary_max": 160000,
  "created": "2026-04-28T12:34:56Z",
  "redirect_url": "https://www.adzuna.com/...",
  "description": "..."  // truncated by Adzuna; redirect_url has full
}
```

---

## Cost / latency

- Per run: 1 LLM call (keywords, ~$0.001) + 1 Adzuna call ($0)
- With `--match`: + N × $0.003 LLM scoring per new JD (Layer 1's cost)
- Daily budget: 250 Adzuna calls / day. Five runs/day with pagination
  off uses 5; ample room.

---

## Failure modes — how to handle each

| Failure                           | Behavior                                  |
|-----------------------------------|-------------------------------------------|
| `secrets.yaml` missing            | `sys.exit` with copy-from-example hint    |
| `app_id` / `app_key` empty        | `sys.exit` pointing to dashboard URL      |
| Adzuna 401 (bad creds)            | `sys.exit` "rotate keys at adzuna..."     |
| Adzuna 429 (rate limit)           | `sys.exit` "wait or check daily budget"   |
| Network timeout                   | `sys.exit`, suggest `--dry-run` to retry  |
| LLM keyword extraction fails JSON | Fall back to title from `profile.yaml.target_role` if set, else exit with prompt for `--query` |
| Zero results                      | Exit 0, print "no new JDs"                |
| All N results already in jds/     | Exit 0, print "0 new / N already known"   |
| Some JDs already known            | Print "X new / Y already known"           |

---

## Out of scope (defer to later layers)

- Multi-country in a single run (loop over countries)
- HN "Who is hiring" parser (Layer 3)
- Greenhouse / Lever per-company boards (Layer 4)
- Daily-budget tracking file
- Webhook / cron scheduling
- LinkedIn / Indeed scraping (explicitly not pursued)

---

## Smaller decisions (called for completeness — override if any seem wrong)

1. **Keyword extraction model**: same as `config.yaml` model (sonnet by
   default). Small ~$0.001 call, no reason to differ.
2. **`--match` chaining**: subprocess to `match.py`, not in-process
   import. Keeps the two CLIs independent and matches how
   `match.py --auto-tailor` already invokes `tailor.py`.
3. **`profile.yaml` use in keyword extraction**: yes — pass
   `motivation` / `edge` / any `target_role` field through to bias
   toward the candidate's stated direction, not just what the resume
   looks backward at. This is the whole reason `profile.yaml` exists.
4. **`--dry-run` scope**: skip writing files, but DO call Adzuna once.
   Shows real result counts, costs ~1 of 250 daily calls.

---

## Effort estimate

~1 day. Concretely:
- 0.5 h — secrets loader (env var + yaml fallback) + smoke test
- 1 h   — Adzuna client + response parser + JD file writer
- 1 h   — keyword extraction prompt + LLM call + JSON parse
- 0.5 h — dedup + main flow + `--match` chaining
- 1.5 h — tests (HTTP mocks, parse edges, dedup, secret loading)
- 1 h   — end-to-end smoke against real Adzuna + bug fixes
- 0.5 h — README + this plan's "DONE" markers + commit

Dependencies: `requests` (new — single line in `requirements.txt`).

~250 LOC.
