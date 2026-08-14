#!/bin/sh
# Sequential md-review of the documents still unreviewed after the first runner
# was killed with its parent session (2026-08-13). Serial by design — each grid
# launches eight reviewer processes. Deleted after use.
set -u
for target in \
    docs/agents/doctrine-instructions.md \
    docs/agents/sidebar-instructions.md \
    docs/cross-project/fleet-machine-paths-and-checkouts.md \
    docs/issues/queue/45-session-seat-and-isolation-riders.md \
    docs/issues/queue/45-ubuntu-fleet-open-work-inventory.md
do
    echo "GRID-START $target"
    python3 scripts/md-review-grid.py --target "$target" 2>&1 \
        | grep -E "saved:|FAILED|Traceback" || echo "GRID-NO-OUTPUT $target"
    echo "GRID-DONE $target"
done
echo "ALL-GRIDS-COMPLETE"
