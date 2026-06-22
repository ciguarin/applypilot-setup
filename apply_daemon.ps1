# ApplyPilot apply daemon — Windows scheduled task script
# Resets stuck in_progress jobs, drains the apply queue.

$DB = "$env:USERPROFILE\.applypilot\applypilot.db"

& python -c @"
import sqlite3
conn = sqlite3.connect(r'$DB')
reset = conn.execute(\"UPDATE jobs SET apply_status = NULL WHERE apply_status = 'in_progress'\").rowcount
conn.commit()
if reset:
    print(f'Reset {reset} stuck in_progress jobs')
"@

& applypilot apply --limit 15 --workers 1 --model haiku --headless --max-turns 30
