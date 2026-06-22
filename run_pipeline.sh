#!/usr/bin/env bash
# Called by n8n after new jobs are discovered.
# Resets stuck in_progress jobs, runs pipeline, then applies headless.

set -e

APPLYPILOT="$(which applypilot 2>/dev/null || echo "$HOME/.local/bin/applypilot")"
DB="$HOME/.applypilot/applypilot.db"

# Reset any jobs stuck in_progress from a previous killed session
python3 -c "
import sqlite3
conn = sqlite3.connect('$DB')
reset = conn.execute(\"UPDATE jobs SET apply_status = NULL WHERE apply_status = 'in_progress'\").rowcount
conn.commit()
if reset: print(f'Reset {reset} stuck in_progress jobs')
"

$APPLYPILOT run enrich score tailor cover pdf --validation lenient
$APPLYPILOT apply --limit 15 --workers 2 --model haiku --headless --max-turns 30
