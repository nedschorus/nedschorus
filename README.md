# nedschorus

A system in which one human and a small number of AI agents build and improve the software-development system they themselves run on — restarted from minimum as the successor to the nedlern project, which keeps running during the founding and then quiesces into a read-only reference.

## Why this project exists

Its predecessor (nedlern, at `~/Projects/nedlern`) grew a working but heavy system: multi-agent messaging with delivery lifecycles, an eleven-state PR pipeline, layered enforcement hooks, a large doctrine corpus. Examined closely, most of that complexity was organizational — the cost of coordinating many agents, plus accumulated patches — not essential to the work being done. Re-derived from actual requirements with the minimal set of actors, each subsystem turned out small: messaging between agents became a pair of append-only log files; session continuity became one numbered handoff file plus its committed transcript; the path from change to production became a single writing agent and four states. Each re-derivation is specified under `docs/cross-project/`.

nedschorus is the restart that keeps it that way: start from the simple system that works, and let complexity be earned — never assumed.

## Founding principles

1. **Re-derive from the requirement; never inherit machinery by default.** Ask what is needed and no more; the old system's mechanisms are reference. Anything deliberately taken from them crosses the entry checkpoint (principle 6) — importing is a chosen act, never a migration habit.
2. **Complexity is earned, step by step:** manual → script the human runs → automation. Each step admitted on evidence, by the human.
3. **Behavior belongs in code wherever it can be expressed there** — testable, versionable, inert until called. Prose is for judgment only. When it is a choice between python and a prompt, python; between bash and python, python — bash only for one-liners not worth a file.
4. **Durable artifacts are written for a zero-context reader** — an agent with repository access, the project instructions, and the document itself, but no conversation history — and tested by handing them to exactly such an agent.
5. **One writer to main.** choirmaster is the only identity that ever pushes. Every check-in — its own work or another agent's draft — lands through a single scripted gate (the throat), where every mechanical check runs from day one. All other agents draft in their own clones and never push; their work arrives via promotion through the throat.
6. **The old system is the quarry:** read-only reference, freely read. Content that enters this repository from it is an import, and every import records one line in `entry-manifest.md`, in the same commit; the line's schema is defined once, in the throat specification ([fast-pr-to-prod-design.md](docs/cross-project/fast-pr-to-prod-design.md)).
7. **Present-tense truth.** Documents state what is; git history holds what was. The built system is the source of truth — a design page carries the date on which it described that truth, and newer code and open issues may have advanced past it.

## The actors

- **The boss** — the human. Reads every document that lands, admits every rung of automation, owns every judgment only a human can make.
- **choirmaster** — the primary agent (Claude runtime). The single writer to main; operates the throat.
- **A Codex-runtime companion** (planned) — drafts and reviews in parallel from its own clone; never pushes; its work lands via promotion through the throat.

## The agent model

Three agent lifetimes, used deliberately:

- **Sustained agents** (choirmaster, the companion): live indefinitely. Choirmaster lives as a chain of sessions whose continuity is the handoff system — a numbered handoff file plus the session's committed transcript, written at each session's end and read automatically at the next session's start — so a session's end costs minutes, not context. The companion's continuity is its own runtime's persistent session: Codex auto-compaction plus resume by session id — it needs no handoff system (boss-ruled 2026-07-21).
- **Task-scoped agents**: spawned for one bounded, multi-step task (a promotion job, a dogfood run) with exactly the context that task needs; they end with the task.
- **One-shot agents** ("kleenex"): a single call, then discarded — a zero-context drafter, a review pass, a probe. Their empty context is the point: they are the system's test instrument for zero-context readability and its guard against context contamination.

## Where things live

| Place | Holds |
|---|---|
| `docs/wiki/` | Standing knowledge, kept current (Obsidian vault). |
| `docs/issues/<n>-<slug>.md` | Working documents, one per GitHub issue, disposed when the issue closes. |
| `docs/cross-project/` | Artifacts both systems read, including the founding documents and specifications. |
| `handoff/` | Numbered session handoffs and their transcripts. |
| `entry-manifest.md` | The ledger of everything imported from the quarry. |
| Issues labeled `boss-review` | Suggested updates awaiting the boss's review — same format as every issue, walkable; no work ever waits on one, and nothing requiring the boss's admission takes effect without it. |

## Status

Founding phase. The boot-up sequence and its state: [docs/cross-project/nedschorus-founding-plan.md](docs/cross-project/nedschorus-founding-plan.md).
