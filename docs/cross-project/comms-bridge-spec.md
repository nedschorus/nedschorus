---
status: specification (re-derived 2026-07-21)
---

# Comms Bridge Spec — append-only log-pair channels

**The boss's design, adopted verbatim (2026-07-20), re-derived 2026-07-21 against the six ruled inputs (dispositions on https://github.com/nedschorus/nedschorus/issues/5).** The requirement: asynchronous, boss-readable coordination between two agents that survives either side's process or session death. The logs are ordinary files and outlive the processes that write them — that IS the survival boundary (boss-ruled 2026-07-21, package-review S4): machine loss is the backup layer's job (Time Machine; https://github.com/nedschorus/nedschorus/issues/7), and a lost log costs only re-emittable chatter (see the promotion-request paragraph). The simplest thing that satisfies it: two append-only files — no daemons, no delivery lifecycle, no wake problem, fully inspectable with `cat`.

## The protocol (common to every channel)

- **One channel = two append-only log files, one per writer.** Write only your own file; read only the other's. Never edit or delete an entry; corrections are new entries.
- **An append is atomic:** the writer composes the complete entry first, then appends it in a single write, so a reader never observes a half-written entry.
- **Entry header, fixed and minimal:** `## <entry-id> <UTC timestamp> <author>` on one line, where `entry-id` is the author's name plus a per-author monotonic counter (`new-vp-0041`). Optional second lines when they apply: `reply-to: <entry-id>` and `base-sha: <sha>` (required whenever the entry references repository code or a draft). Body: plain markdown. No protocol beyond that.
- **Delivery is pull-only by design:** each side reads the other's log when it takes a turn. There is NO wake mechanism — an entry waits until the reader next runs. If something is urgent, the boss relays it by cut-and-paste, which is the always-available fallback channel.
- **The logs are working chatter, not records — gitignored, never committed.** Anything durable gets PROMOTED out of the log into its governing home (a decision into a spec or issue; state into the handoff), linked back by `entry-id`. A log entry is presumed disposable.
- **Blind first passes:** when both agents draft the same artifact, each completes its first pass before reading anything the other wrote about it. Cross-reading before both passes exist collapses the value of having two heads.

## The two channels

| Channel | Writers | Files | Location |
|---|---|---|---|
| Founding bridge | the old system's agent ↔ choirmaster | `bridge/from-old.log.md`, `bridge/from-new.log.md` | `bridge/` in the canonical nedschorus checkout — both writers reach the same checkout today, so one directory serves. |
| Mini-comms (companion era) | choirmaster ↔ the companion | `mini-comms/from-choirmaster.log.md`, `mini-comms/from-companion.log.md` | **One shared directory OUTSIDE both clones** (exact path fixed at companion admission, recorded in the kernel). Gitignored files do not propagate between clones — two per-clone directories would coordinate into the void, so a clone-local location is a defect, not an option. |

The companion's **promotion requests** travel over mini-comms as ordinary entries whose body is a versioned, machine-parseable request block (boss-ruled 2026-07-21, package-review S15): a fenced block opening with its version line (`request-block v1`), one field per line — `request-id`, the path list with a content digest per path (freezing the request at send time), base commit, at most one declared quarry import with source SHA + source path + destination path — see `fast-pr-to-prod-design.md` for what the throat does with each field. Every request receives a mandatory disposition entry in the picker-upper's own log, naming the `request-id` — `landed: <commit>` or `refused: <named defect>` — so a request is never ambiguous between waiting and resolved. A stalled request is visible in the boss-readable log while the log lives. Log loss is cheap by construction: an undispositioned promotion request is re-emittable by its author, whose runtime session persists (the S3 companion-continuity ruling), so a lost log costs a re-send, not work. Accepted residual (boss-ruled 2026-07-21, package-review S4): the founding bridge's logs live inside the canonical checkout, so deleting that clone loses them — not a concern because the founding window is short and one boss-operated, backed-up machine holds both writers; reopening trigger: an actual log loss that costs real work.

## Why not import postal

The old system's postal stack (server, dispatcher, delivery lifecycle, wake mechanisms) is the single largest source of measured friction in the quarry — stranded rows, pull-only replies, delivered-but-unsurfaced messages, an unsolved idle-wake gap. The bridge defers ALL of it until the new system has more than one agent pair and has EARNED automation per the ladder. If that day comes, the postal code in the quarry is an import candidate — through the entry checkpoint, with its known defects listed.

## Open — awaiting the boss

1. Ceremony-time snapshots: whether the handoff ceremony copies the live logs into the committed record (active logs stay out of git regardless; the boss raised capture-at-handoff-creation as the candidate). Archival value only after the S4 ruling — durability no longer needs it.
2. The Monitor-armed idle-wake rider (each side arming a filesystem watch to shorten pull latency) — unruled; it is automation the ladder has not admitted.
