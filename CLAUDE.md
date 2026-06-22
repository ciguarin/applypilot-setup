# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

`~/.applypilot/` is the **user data directory** for ApplyPilot, not the source code. The installed package lives at:

```
C:\Users\ian\applypilot\.venv\Lib\site-packages\applypilot\
```

Source code changes must be made there (or in the upstream repo at https://github.com/Pickle-Pixel/ApplyPilot).

## Key CLI Commands

```bash
# First-time setup
applypilot init

# Run full pipeline (all 6 stages, sequential)
applypilot run

# Run specific stages
applypilot run discover enrich
applypilot run score tailor cover pdf

# Concurrent stage execution (stages overlap via DB as conveyor)
applypilot run --stream

# Validation strictness for tailor/cover (lenient = fastest, fewest API calls)
applypilot run --validation lenient

# Auto-apply via Chrome + Claude Code
applypilot apply
applypilot apply --limit 5 --workers 2 --model haiku

# Diagnostics
applypilot status
applypilot doctor
applypilot dashboard
```

## Architecture

### Pipeline Stages (in order)

`discover → enrich → score → tailor → cover → pdf`

Each stage reads from and writes to the single SQLite `jobs` table. The DB is the conveyor belt — stages are decoupled and can be run independently or concurrently (`--stream`).

| Stage | Module | What it does |
|-------|--------|-------------|
| discover | `discovery/jobspy.py`, `discovery/workday.py`, `discovery/smartextract.py` | Scrapes job boards |
| enrich | `enrichment/detail.py` | Fetches full descriptions + apply URLs |
| score | `scoring/scorer.py` | LLM assigns fit score 1–10 |
| tailor | `scoring/tailor.py` | LLM generates job-specific resume |
| cover | `scoring/cover_letter.py` | LLM generates cover letter |
| pdf | `scoring/pdf.py` | Converts `.txt` outputs to PDF |

### Tier System (Feature Gating)

Detected automatically in `config.get_tier()`:

- **Tier 1** — Python only: `discover`, `enrich`, `status`, `dashboard`
- **Tier 2** — + LLM API key: `score`, `tailor`, `cover`, `pdf`
- **Tier 3** — + Claude Code CLI + Chrome + Node.js: `apply`

### LLM Client (`llm.py`)

Auto-detects provider from env:
- `GEMINI_API_KEY` → Google Gemini (default: `gemini-2.0-flash`)
- `OPENAI_API_KEY` → OpenAI (default: `gpt-4o-mini`)
- `LLM_URL` → OpenAI-compatible endpoint (OpenRouter, Ollama, llama.cpp)
- `LLM_MODEL` overrides the model for any provider

Falls back from Gemini's OpenAI-compat layer to native `generateContent` API automatically on 403.

### Auto-Apply (`apply/`)

`launcher.py` pulls jobs from the DB, launches a Chrome instance per worker (via CDP), builds a structured prompt with the tailored resume + job details, then spawns `claude --mcp-config` pointing at a Playwright MCP server connected to that Chrome instance. Claude fills out the application form autonomously.

### Database (`database.py`)

Single `jobs` table in `~/.applypilot/jobs.db`. Thread-local SQLite connections with WAL mode. Schema migrations are additive-only via `ensure_columns()` — adding a column to `_ALL_COLUMNS` is all that's needed.

## User Data Files

| File | Purpose |
|------|---------|
| `profile.json` | Candidate info: personal, skills, locked resume bullets, role-variant bullet instructions |
| `resume.txt` | Plain-text base resume (required for AI stages) |
| `resume.pdf` | PDF resume |
| `searches.yaml` | Job queries, locations, distance, `hours_old`, `results_per_site` |
| `.env` | API keys — `GEMINI_API_KEY`, `LLM_URL`, `LLM_API_KEY`, `LLM_MODEL`, `CAPSOLVER_API_KEY` |
| `jobs.db` | SQLite pipeline state |
| `tailored_resumes/` | `<prefix>.txt`, `<prefix>.pdf`, `<prefix>_REPORT.json` per job |
| `cover_letters/` | `<prefix>_CL.txt`, `<prefix>_CL.pdf` per job |

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Lint
ruff check .

# Tests
pytest
```

Discovery requires `python-jobspy` installed separately:
```bash
pip install --no-deps python-jobspy && pip install pydantic tls-client requests markdownify regex
```

`APPLYPILOT_DIR` env var overrides the default `~/.applypilot/` data directory (useful for testing).
