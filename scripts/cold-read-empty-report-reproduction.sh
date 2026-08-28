#!/bin/sh
# Reproduce: a cold-read grid can report eight saved reviews having
# reviewed nothing.
#
# WHY THIS EXISTS. `cold-read-grid.py` decides a cell succeeded from its
# exit code alone -- `wait_for_cells` prints "saved: <path>" for any cell
# that exits 0 and never checks the report has content. A review cell
# whose model run exits 0 with empty stdout writes only its provenance
# stamp and exits 0. The grid then prints its ordinary closing
# instructions, which tell the reviewing agent to read all eight reports,
# triage them, and walk the findings with the user. An agent that follows
# those instructions against eight empty reports has no way to tell
# "eight reviewers found nothing" from "eight reviewers never ran".
#
# This is the family recorded at nedschorus PR #111 and collected across
# seven unrelated tools on 2026-08-23: a step whose success signal cannot
# express the failure. It was found by reading the code; this script is
# the measurement, because the family has bitten hardest where people
# reasoned about exit codes instead of running them.
#
# WHAT IT DOES. Puts stub `claude` and `codex` executables -- each exits 0
# having printed nothing -- ahead of the real ones on PATH, runs the grid
# against a throwaway target, and reports the grid's exit code alongside
# the content length of every report it saved. No network calls, no model
# calls, nothing outside a temporary directory and the gitignored
# cold-read-records/ tree.
#
# EXPECTED TODAY (the defect): grid exit 0, and every report body empty.
# EXPECTED AFTER A FIX: the grid reports those cells as failures, and its
# closing instructions do not invite triage of reports that do not exist.
#
# Usage: sh scripts/cold-read-empty-report-reproduction.sh

set -eu

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/stub-bin"
for tool in claude codex; do
    cat > "$WORK/stub-bin/$tool" <<'STUB'
#!/bin/sh
# Succeeds having produced nothing: models an interrupted stream or an
# empty completion, both of which exit 0 in the real CLIs.
exit 0
STUB
    chmod +x "$WORK/stub-bin/$tool"
done

TARGET_NAME="cold-read-empty-report-reproduction-target.md"
TARGET="$REPO_ROOT/$TARGET_NAME"
printf '# Reproduction target\n\nOne real line, so the cells have something to point at.\n' > "$TARGET"
trap 'rm -rf "$WORK"; rm -f "$TARGET"' EXIT

echo "running the grid with stub runtimes that exit 0 and print nothing"
set +e
PATH="$WORK/stub-bin:$PATH" python3 "$REPO_ROOT/scripts/cold-read-grid.py" \
    --target "$TARGET_NAME" > "$WORK/grid.out" 2>&1
GRID_EXIT=$?
set -e

echo
echo "grid exit code: $GRID_EXIT"
echo "cells the grid called saved: $(grep -c '^saved:' "$WORK/grid.out" || true)"
echo "cells the grid called FAILED: $(grep -c '^FAILED' "$WORK/grid.out" || true)"
echo
echo "content of each report, provenance stamp excluded:"
RECORD_DIR=$(grep -o '/[^ ]*cold-read-records/[^ ]*' "$WORK/grid.out" | head -1)
for report in "$RECORD_DIR"/*.md; do
    [ -f "$report" ] || continue
    body=$(grep -v '^<!-- provenance' "$report" | tr -d '[:space:]' | wc -c | tr -d ' ')
    printf '  %-28s body-chars=%s\n' "$(basename "$report")" "$body"
done
echo
echo "the grid's closing instructions to the reviewing agent:"
tail -6 "$WORK/grid.out" | sed 's/^/  /'
echo
echo "record directory left for inspection: $RECORD_DIR"
