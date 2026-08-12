# Dispositions — sanity-checker review of docs/cross-project/fast-handoff-design.md

The calibration protocol's second-document run (2026-08-12), doubling as the sanity-checker's first real engagement: the settled prompt reviewed the live fast-handoff design with the built handoff skill and its draft as context. Reviewer report: `claude-sanity-check-fable.md` in this directory; the reviewed revision is snapshotted as `reviewed-fast-handoff-design.md`. Triage verified every load-bearing quote against the live documents; all seven findings survived. The user rules per finding below.

## Walk order (original)

1. Purpose: what this walk decides and how the reviewer did — processed 2026-08-12 → accepted
2. F1 — two auto-trigger mechanisms where one covers every session type (Delete)
3. F2 — the threshold hook's silence gate suppresses the self-healing path (Delete; collision flagged)
4. F3 — the queue-status line has no named reader in the detached case (route, name, or cut; #32 collision flagged)
5. F4 — the per-upgrade canary re-run is a remembered human step (Encode or delete)
6. F5 — Tests and Components predate the word-floor ruling (reconcile)
7. F6 — three disagreeing status homes (merge)
8. F7 — Known holes holds three closed holes (move rulings to their mechanisms)

## Restructure — user-ruled 2026-08-12

While weighing F1 the user ruled on the document's purpose itself: there is no utility in prose that documents what is better understood by reading the code — a design document's remaining value is only what code cannot carry (dated rulings and their whys, verified harness facts, known holes, a pointer to the scripts). That ruling resolves the four documentation findings wholesale rather than one by one:

- **F1 (document half), F5, F6, F7 — accepted as a class.** Resolution: gut `docs/cross-project/fast-handoff-design.md` to rulings, verified facts, known holes, and a component pointer; every mechanism-description paragraph — the material that drifts — goes. The gut lands after the remaining code rulings, so the surviving text reflects them.

The remaining walk is the four code-behavior decisions:

1. F1 (code half) — the statusline relay + fallback path in the threshold hook: keep or delete — processed 2026-08-12 → accepted, relay deleted. Reading the built hook overturned the keep recommendation's premise: an unknown model id never consults the relay (it takes the 200K default window, which over-fires safely), so the fallback's only trigger was a session whose first turn had not completed — a moment the threshold cannot be crossed. Execution note: the relay script was mostly the user-walked statusline renderer with the relay write fused in, so the renderer survives as `scripts/session-statusline-command.py` (tests split out alongside); only the side-file write, the hook's fallback read, and the stale side files were deleted.
2. F2 — remove the hook's supervisor-liveness silence gate — processed 2026-08-12 → accepted, gate deleted. Verified dormant anyway: the project's settings invoke the hook without `--agent`, so the gate never engaged; it existed only as a trap. The user asked when the gate could start being used — answer recorded: never; self-registration (2026-08-06) made an unwatched firing self-healing, so silence could only turn a dead supervisor into a permanent stall. What does await prerequisites is per-agent wiring of the hook (distinguishing managed agents from the user's own panes), blocked on the agent-naming convention — a different mechanism gating on "is this a named agent," not on supervisor liveness. The `--check` liveness machinery keeps its skill consumer, untouched.
3. F3 — the queue-status line: route to a reader or cut — processed 2026-08-12 → accepted as route: the ignition prompt now carries the queue-status line to every successor ("surface anything rotting to the user"), giving the #32 rot-visibility duty a reader in every supervisor mode; the console print stays for the watched-pane case. The #32 collision resolved by reading the ruling: the ruled reader is the boss ("the handoff scrub reports the store's depth ... alongside the other queues"), and with the scrub retired, the successor's reporting is the surviving channel to him.
4. F4 — mechanize the per-upgrade canary re-run — processed 2026-08-12 → revised: the user chose the finding's alternative, deleting the remembered duty rather than mechanizing the trigger. Detection now rests on the declared containment — the successor's ignition count-check (trial-proven to fire unprompted) with the queues as backstop; the first post-upgrade recycle is the detection event, and that bounded blind interval is the accepted loss. The canaries survive as diagnosis (--canary), no longer as a scheduled duty.
5. (added during item 1) `.claude/settings.json` registers the Stop hook twice under a duplicate `"hooks"` → `"Stop"` JSON key — dedupe

## Rulings on the code items
