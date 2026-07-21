---
status: draft
---

# Comms Bridge Spec — two log files between the old and new systems

**The boss's design, adopted verbatim (2026-07-20):** the simplest thing that works — no daemons, no delivery lifecycle, no wake problem, fully inspectable.

**Re-derivation inputs (ruled 2026-07-21, borrowings walk item 5 — dispositions on https://github.com/nedlern/nedschorus/issues/5):** this spec is owed re-derivation before its review (founding-plan open ruling). Fixed at ruling: NO comms-substrate import — no mailbox server, no event store; two single-writer append-only files remain the protocol. Six requirements for the re-derived version: (1) when the two writers live in separate clones (companion era), the logs move to ONE shared directory outside both clones — gitignored files do not propagate between clones, so two per-clone `bridge/` directories would coordinate into the void; today's old↔new usage in the single canonical checkout is unaffected. (2) Atomic appends — a reader must never observe a half-written entry. (3) Minimal fixed entry header: entry id, UTC timestamp, author, reply-to id, base SHA whenever code is referenced. (4) Durable decisions stay OUT of the logs, linked by entry id (the persistence rule below already states this). (5) When both heads draft the same artifact, blind first passes complete before either reads the other's. (6) Open question to rule at re-derivation: whether ceremony-time snapshots of the logs join the committed record — active logs stay out of git regardless.

## Mechanism

- Two append-only files in the NEW repo: `bridge/from-old.log.md` (old system writes, new system reads) and `bridge/from-new.log.md` (new system writes, old system reads).
- **Write only your own file; read only the other's.** Append-only — never edit or delete an entry; corrections are new entries.
- Entry format: `## <UTC timestamp> <author-agent>` followed by the message body. Plain markdown, no protocol beyond that.
- Delivery is pull-only by design: each side reads the other's log when it takes a turn. There is NO wake mechanism — a message waits until the reader next runs. If something is urgent, the boss relays it by cut-and-paste, which is the always-available fallback channel.

## Persistence rules (boss directive, 2026-07-20)

- **The logs are `.gitignored`** — they are working chatter, not records. The new repo's `.gitignore` carries `bridge/*.log.md` from init.
- **Anything durable gets PROMOTED out of the log** into a committed file (a decision into the charter or a doc; state into the handoff) — the heavily-used handoff process is the backup path for anything in a log worth keeping. A log entry is presumed disposable.

## Why not import postal

The old system's postal stack (server, dispatcher, delivery lifecycle, wake mechanisms) is the single largest source of measured friction in the quarry — stranded rows, pull-only replies, delivered-but-unsurfaced messages, an unsolved idle-wake gap. The bridge defers ALL of it until the new system has more than one agent and has EARNED automation per the ladder. When that day comes, the postal code in the quarry is an import candidate — through the entry checkpoint, with its known defects listed.
