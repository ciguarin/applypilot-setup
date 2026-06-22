#!/usr/bin/env bash
# ApplyPilot patch script for macOS
# Run after: uv tool upgrade applypilot

set -e

SRC="$HOME/.applypilot/patches"
DST="$(python3 -c 'import applypilot, os; print(os.path.dirname(applypilot.__file__))')"

echo "Patching: $DST"

cp "$SRC/scoring/validator.py"  "$DST/scoring/validator.py"  && echo "Patched: scoring/validator.py"
cp "$SRC/scoring/tailor.py"     "$DST/scoring/tailor.py"     && echo "Patched: scoring/tailor.py"
cp "$SRC/scoring/pdf.py"        "$DST/scoring/pdf.py"         && echo "Patched: scoring/pdf.py"
cp "$SRC/cli.py"                "$DST/cli.py"                 && echo "Patched: cli.py"
cp "$SRC/apply/prompt.py"       "$DST/apply/prompt.py"        && echo "Patched: apply/prompt.py"
cp "$SRC/apply/launcher.py"    "$DST/apply/launcher.py"      && echo "Patched: apply/launcher.py"

echo ""
echo "All patches applied to $DST"
