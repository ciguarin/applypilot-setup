#!/usr/bin/env bash
# ApplyPilot setup script — macOS / Linux
set -e

APPLYPILOT_DIR="$HOME/.applypilot"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

echo "=== ApplyPilot Setup ==="

# ── 1. uv ────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "✓ uv $(uv --version)"

# ── 2. applypilot ────────────────────────────────────────────────────────────
echo "Installing applypilot..."
uv tool install applypilot
export PATH="$HOME/.local/bin:$PATH"
echo "✓ applypilot $(applypilot --version 2>/dev/null || echo installed)"

# ── 3. patches ───────────────────────────────────────────────────────────────
echo "Applying patches..."
DST="$(python3 -c 'import applypilot, os; print(os.path.dirname(applypilot.__file__))')"
SRC="$APPLYPILOT_DIR/patches"
cp "$SRC/scoring/validator.py" "$DST/scoring/validator.py"
cp "$SRC/scoring/tailor.py"    "$DST/scoring/tailor.py"
cp "$SRC/scoring/pdf.py"       "$DST/scoring/pdf.py"
cp "$SRC/cli.py"               "$DST/cli.py"
cp "$SRC/apply/prompt.py"      "$DST/apply/prompt.py"
echo "✓ Patches applied to $DST"

# ── 4. config templates (only if not already present) ────────────────────────
[[ ! -f "$APPLYPILOT_DIR/.env" ]]         && cp "$APPLYPILOT_DIR/.env.example"                    "$APPLYPILOT_DIR/.env"
[[ ! -f "$APPLYPILOT_DIR/profile.json" ]] && cp "$APPLYPILOT_DIR/config/profile.example.json"     "$APPLYPILOT_DIR/profile.json"
[[ ! -f "$APPLYPILOT_DIR/searches.yaml" ]]&& cp "$APPLYPILOT_DIR/config/searches.example.yaml"    "$APPLYPILOT_DIR/searches.yaml"
echo "✓ Config templates ready"

# ── 5. LaunchAgents (macOS only) ─────────────────────────────────────────────
if [[ "$(uname)" == "Darwin" ]]; then
    mkdir -p "$LAUNCH_AGENTS" "$APPLYPILOT_DIR/logs"

    sed "s|__HOME__|$HOME|g" "$APPLYPILOT_DIR/launchagents/com.applypilot.apply.plist.template" \
        > "$LAUNCH_AGENTS/com.applypilot.apply.plist"
    launchctl unload "$LAUNCH_AGENTS/com.applypilot.apply.plist" 2>/dev/null || true
    launchctl load   "$LAUNCH_AGENTS/com.applypilot.apply.plist"
    echo "✓ Apply daemon installed (runs every 12h)"

    if command -v n8n &>/dev/null; then
        sed "s|__HOME__|$HOME|g" "$APPLYPILOT_DIR/launchagents/com.applypilot.n8n.plist.template" \
            > "$LAUNCH_AGENTS/com.applypilot.n8n.plist"
        launchctl unload "$LAUNCH_AGENTS/com.applypilot.n8n.plist" 2>/dev/null || true
        launchctl load   "$LAUNCH_AGENTS/com.applypilot.n8n.plist"
        echo "✓ n8n daemon installed"
    else
        echo "  n8n not found — skipping. Install: npm install -g n8n"
    fi
fi

echo ""
echo "=== Done! Next steps ==================================="
echo ""
echo "  1. Edit ~/.applypilot/.env          — add API keys"
echo "  2. Edit ~/.applypilot/profile.json  — fill in personal info"
echo "  3. Add resume: ~/.applypilot/resume.txt  (plain text)"
echo "                 ~/.applypilot/resume.pdf  (PDF)"
echo "  4. Edit ~/.applypilot/searches.yaml — set job queries"
echo "  5. applypilot init                  — first-time setup"
echo "  6. applypilot run                   — run the pipeline"
echo ""
echo "  Optional: import n8n/applypilot-github-ingestion.json"
echo "            into n8n for automated discovery."
echo ""
