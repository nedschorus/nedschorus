#!/bin/sh
# Sequential md-review of the nine seat documents not already under review
# (user-directed 2026-08-14: review all twelve). Serial by design — each grid
# launches eight reviewer processes, so running twelve at once would put
# ninety-six on the box. Deleted after use.
set -u
for target in \
    docs/agents/sanity-checker-instructions.md \
    docs/agents/fleet-instructions.md \
    docs/agents/skill-builder-instructions.md \
    docs/agents/ghi-instructions.md \
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
