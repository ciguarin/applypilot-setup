# ApplyPilot Setup

A configuration layer and automation stack on top of [ApplyPilot](https://github.com/Pickle-Pixel/ApplyPilot) — an AI-powered job application pipeline that discovers listings, tailors resumes, writes cover letters, and submits applications autonomously.

This repo handles everything that's missing from the upstream package: install scripts, patches, n8n workflow for job discovery, and daemon configs for both macOS and Windows.

---

## What it does

1. **Discovers** internship listings from GitHub-curated repos (Canadian Tech Internships, Hanzili) via an n8n workflow running every 2 hours
2. **Enriches** listings with full descriptions and application URLs
3. **Scores** each job 1–10 against your profile using an LLM
4. **Tailors** your resume per job, with role-type detection and locked bullet preservation
5. **Generates** a cover letter per job
6. **Applies** autonomously using Claude Code + Playwright (fills forms, solves CAPTCHAs, handles logins)

---

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| Python 3.11+ | Yes | [python.org](https://python.org) |
| [uv](https://docs.astral.sh/uv/) | Yes | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Claude Code CLI](https://claude.ai/code) | Yes (for apply stage) | `npm install -g @anthropic-ai/claude-code` |
| Google Chrome | Yes (for apply stage) | [chrome](https://www.google.com/chrome/) |
| Node.js 18+ | Yes (for apply stage) | [nodejs.org](https://nodejs.org) |
| [n8n](https://n8n.io) | Optional | `npm install -g n8n` |
| [CapSolver](https://capsolver.com) account | Optional | Sign up — ~$2 buys hundreds of CAPTCHA solves |

**API keys needed:**
- Gemini API key (free tier works): [aistudio.google.com](https://aistudio.google.com/app/apikey)
- Anthropic API key (for Claude Code): [console.anthropic.com](https://console.anthropic.com)

---

## Installation

### macOS

```bash
git clone https://github.com/Retriever1693/applypilot-setup.git ~/.applypilot
cd ~/.applypilot
bash install.sh
```

### Windows (PowerShell 7+)

```powershell
git clone https://github.com/Retriever1693/applypilot-setup.git "$env:USERPROFILE\.applypilot"
cd "$env:USERPROFILE\.applypilot"
.\install.ps1
```

The install script:
- Installs `applypilot` via uv
- Applies patches (optimized prompt, PDF renderer, validator tweaks)
- Copies config templates to `~/.applypilot/`
- Installs a daemon (LaunchAgent on macOS, Scheduled Task on Windows) that runs the apply pipeline every 12 hours

---

## Configuration

After install, edit these three files:

### `~/.applypilot/.env`
```env
GEMINI_API_KEY=your_key_here
CAPSOLVER_API_KEY=your_key_here   # optional but recommended
AP_PASSWORD=a_unique_password      # used for ATS account creation
```

### `~/.applypilot/profile.json`
Copy from `config/profile.example.json` (already done by install script). Fill in:
- `personal` — name, email, phone, address, LinkedIn, GitHub
- `compensation` — salary floor and range
- `skills_boundary` — your actual skills (LLM never adds anything outside this list)
- `resume_facts` — locked bullet points, project descriptions, preserved company names

### `~/.applypilot/searches.yaml`
Copy from `config/searches.example.yaml`. Set your target city, role queries, and distance radius.

### Resume files
```
~/.applypilot/resume.txt   # plain text — used for AI tailoring
~/.applypilot/resume.pdf   # PDF — uploaded to application forms
```

---

## Running

```bash
# First-time setup
applypilot init

# Run the full pipeline (discover → score → tailor → cover → pdf → apply)
applypilot run

# Run specific stages only
applypilot run enrich score tailor cover pdf

# Apply to queued jobs manually
applypilot apply --limit 10 --model haiku

# Check pipeline status
applypilot status
applypilot dashboard
```

---

## n8n Automated Discovery (optional)

n8n runs the discovery + ingestion workflow on a schedule, then triggers the pipeline automatically.

1. Start n8n: `n8n` (or it runs via the LaunchAgent on macOS)
2. Open [http://localhost:5678](http://localhost:5678)
3. Import `n8n/applypilot-github-ingestion.json`
4. Activate the workflow

The workflow checks GitHub internship repos every 2 hours, prunes closed listings from your DB, inserts new ones, and calls `run_pipeline.sh`.

---

## After upgrading applypilot

Re-apply patches any time you run `uv tool upgrade applypilot`:

```bash
# macOS
bash ~/.applypilot/patches/patch_applypilot.sh

# Windows
& "$env:USERPROFILE\.applypilot\patches\patch_applypilot.ps1"
```

---

## Architecture

```
~/.applypilot/
├── install.sh / install.ps1     # One-command setup
├── apply_daemon.sh / .ps1       # Scheduled apply runner (every 12h)
├── run_pipeline.sh              # Called by n8n: pipeline + apply
├── start_n8n.sh                 # macOS nvm-aware n8n launcher
├── patches/                     # Overrides applied on top of upstream
│   ├── apply/prompt.py          # Optimized agent prompt (~50% token reduction)
│   ├── scoring/tailor.py        # Resume tailoring with profile-driven logic
│   ├── scoring/validator.py     # Banned-word detection + LLM judge
│   ├── scoring/pdf.py           # PDF generation via Playwright
│   └── cli.py                   # CLI entrypoint
├── n8n/
│   └── applypilot-github-ingestion.json   # n8n workflow
├── launchagents/                # macOS LaunchAgent templates
├── config/                      # Template configs (safe to commit)
│   ├── profile.example.json
│   └── searches.example.yaml
├── .env.example                 # API key template
└── .gitignore                   # Excludes .env, profile.json, resume, DB
```

**Pipeline stages:** `discover → enrich → score → tailor → cover → pdf → apply`

Each stage reads/writes to `~/.applypilot/applypilot.db` (SQLite). Stages are fully decoupled — you can run any subset independently.

**Apply stage:** Spawns `claude --model haiku -p` per job with a Playwright MCP pointing at a dedicated Chrome instance. Claude fills the form, solves CAPTCHAs via CapSolver, handles logins, and outputs a result code. Max 30 turns per job, 15 jobs per run.
