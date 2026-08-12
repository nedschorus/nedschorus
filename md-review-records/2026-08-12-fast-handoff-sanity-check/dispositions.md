# Dispositions — sanity-checker review of docs/cross-project/fast-handoff-design.md

The calibration protocol's second-document run (2026-08-12), doubling as the sanity-checker's first real engagement: the settled prompt reviewed the live fast-handoff design with the built handoff skill and its draft as context. Reviewer report: `claude-sanity-check-fable.md` in this directory; the reviewed revision is snapshotted as `reviewed-fast-handoff-design.md`. Triage verified every load-bearing quote against the live documents; all seven findings survived. The user rules per finding below.

## Walk order

1. Purpose: what this walk decides and how the reviewer did — processed 2026-08-12 → accepted
2. F1 — two auto-trigger mechanisms where one covers every session type (Delete)
3. F2 — the threshold hook's silence gate suppresses the self-healing path (Delete; collision flagged)
4. F3 — the queue-status line has no named reader in the detached case (route, name, or cut; #32 collision flagged)
5. F4 — the per-upgrade canary re-run is a remembered human step (Encode or delete)
6. F5 — Tests and Components predate the word-floor ruling (reconcile)
7. F6 — three disagreeing status homes (merge)
8. F7 — Known holes holds three closed holes (move rulings to their mechanisms)
