# nc-queue (the NC walk queue)

The landing directory for boss-requested notes awaiting their initial walk (boss-ruled 2026-07-22; the rule of record is [nedschorus-founding-plan.md](../docs/cross-project/nedschorus-founding-plan.md) § Project organization).

- Every requested note lands here as `<YYYY-MM-DD>-<slug>.md` — the request is complete only when the file exists in this directory.
- Queue commits are verbatim relays: never reviewed before landing. The drafting agent keeps do-not-publish material out (this repository is public).
- At the note's initial walk, the durable parts disperse to their homes — a GHI, an MD-GHI pair, a script, a revision to an existing artifact — and the dispersal commit MOVES the note to archived/, stamping frontmatter at that moment (processed date, dispositions, dropped-by). The walk itself is never memorialized. Unprocessed drops carry no frontmatter; the drop date is the filename date (filesystem timestamps are never consulted).
- An unwalked note expires 90 days after its filename date and is moved to archived/ by the handoff scrub (marked expired), which reports the queue root's count and oldest-note age each ceremony.
- The queue root empty means walks are caught up; archived/ is the browsable processed history; git history additionally holds everything.
