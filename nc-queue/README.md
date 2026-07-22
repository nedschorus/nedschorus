# nc-queue (the NC walk queue)

The landing directory for boss-requested notes awaiting their initial walk (boss-ruled 2026-07-22; the rule of record is [nedschorus-founding-plan.md](../docs/cross-project/nedschorus-founding-plan.md) § Project organization).

- Every requested note lands here as `<YYYY-MM-DD>-<slug>.md` — the request is complete only when the file exists in this directory.
- Queue commits are verbatim relays: never reviewed before landing. The drafting agent keeps do-not-publish material out (this repository is public).
- At the note's initial walk, the durable parts disperse to their homes — a GHI, an MD-GHI pair, a script, a revision to an existing artifact — and the dispersal commit deletes the note. The walk itself is never memorialized.
- An unwalked note expires 90 days after its filename date and is deleted by the handoff scrub, which reports the queue's count and oldest-note age each ceremony.
- Deletion is working-tree only: git history holds every raw note permanently.
