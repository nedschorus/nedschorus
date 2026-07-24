---
status: draft
---

# Seed CLAUDE.md — draft for the boss's line-by-line admission

**This is a DRAFT of the successor project's kernel.** Every line below must be individually admitted by the boss before it ships; cut freely. The distillation rule: only lines that change behavior and cannot be a mechanism yet. Everything else lives in the charter, the legacy system, or code.

---

# <project-name>

## Who and where
- One human (the boss) + one agent. The boss reads every document that lands; there is no automated review, publishing, or merge process — and none gets added without his explicit admission, following the ladder: manual → script-you-run → automation, each step earned by evidence.
- Your repo is `~/Projects/<project-name>`. The old system at `~/Projects/nedlern` is LEGACY: read-only reference. NOT: write, commit, or run anything there. DO: read anything there freely.

## The entry checkpoint (the one sacred rule)
- Everything imported from the legacy system crosses one gate: record in `entry-manifest.md` the legacy system SHA it came from, a one-line purpose, and the date — in the same commit as the import. The manifest is the system map; it must never lag the system.

## How to work
- Behavior belongs in code whenever it can be expressed there (testable, versionable, inert until called); prose is only for judgment and semantics. English is not a programming language.
- Pin the revision: any claim about code or a document states the SHA or artifact it was verified against. Evidence has a lifetime — state it. An absence claim carries its query and scope.
- Optimize for correctness and clarity over speed. Small increments: one file, one decision at a time, walkable with the boss.
- Write clearly and completely for a reader with no context. No figurative phrasing; plain engineering register.
- Session end: write the handoff (current state, decisions, next steps), commit it. It is the only continuity that survives you.

## Comms
- With the boss: this terminal. With the old system: the bridge logs per `comms-bridge-spec.md` (write yours, read theirs); logs are .gitignored — promote anything durable to a committed file.
