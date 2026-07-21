# nedschorus

A system in which one human and a small number of AI agents build and improve their own software development system — restarted from minimum, as the successor to the nedlern project.

## Why this project exists

Its predecessor (nedlern, at `~/Projects/nedlern`) grew a working but heavy system: multi-agent messaging with delivery lifecycles, an eleven-state PR pipeline, layered enforcement hooks, a large doctrine corpus. Examined closely, most of that complexity was organizational — the cost of coordinating many agents, plus accumulated patches — not essential to the problems being solved. Re-derived from actual requirements with the minimal set of actors, each subsystem turned out small: inter-system messaging became two append-only log files; session continuity became one numbered handoff file plus a script; the path from change to production became a single writer and four states.

nedschorus is the restart that keeps it that way: start from the simple system that works, and let complexity be earned — never assumed.

## Founding principles

1. **Re-derive from the requirement; never migrate machinery.** Ask what is needed and no more; the old system's mechanisms are reference, not inheritance.
2. **Complexity is earned, step by step:** manual → script the human runs → automation. Each step admitted on evidence, by the human.
3. **Behavior belongs in code wherever it can be expressed there** — testable, versionable, inert until called. Prose is for judgment only. When it is a choice between python and a prompt, python; between bash and python, python — bash only for one-liners not worth a file.
4. **Durable artifacts are written for a zero-context reader** — an agent holding only the project instructions and the document itself — and tested by handing them to one.
5. **One writer to main.** All check-ins flow through a single throat, where every mechanical check runs from day one.
6. **The old system is the quarry:** read-only reference. Every import records its source commit, purpose, and date in `entry-manifest.md`, in the same commit.
7. **Present-tense truth.** Documents state what is; git history holds what was; the production system is the source of truth, and design pages carry the date they described it.

## The actors

- **The boss** — the human. Reads everything, admits every rung of automation, owns every judgment only a human can make.
- **choirmaster** — the primary agent (Claude runtime). The single writer to main.
- **A Codex-runtime companion** (planned) — drafts and reviews in parallel from its own clone; its work lands through the throat.

## The agent model

Three agent lifetimes, used deliberately:

- **Sustained agents** (choirmaster, the companion): live indefinitely as a chain of sessions. Continuity is the handoff system — a numbered handoff file plus the session's denoised transcript, written at each session's end and read automatically at the next session's start — so succession is cheap and near-automatic, and a session's death loses minutes, not context.
- **Task-scoped agents**: spawned for one bounded task (a promotion job, a dogfood run) with exactly the context that task needs; they end with the task.
- **One-shot agents** ("kleenex"): spawned for a single job and discarded — a zero-context drafter, a review pass, a probe. Their empty context is the point: they are the system's test instrument for zero-context readability and its guard against context contamination.

## Where things live

| Place | Holds |
|---|---|
| `docs/wiki/` | Permanent knowledge (Obsidian vault). |
| `docs/issues/<n>-<slug>.md` | Working documents, one per GitHub issue, disposed when the issue closes. |
| `docs/cross-project/` | Artifacts shared with the old system, including the founding documents. |
| `handoff/` | Numbered session handoffs and their transcripts. |
| `entry-manifest.md` | The ledger of everything imported from the quarry. |
| Issues labeled `boss-review` | Suggested updates awaiting the boss's review — same format as every issue, walkable, non-blocking. |

## Status

Founding phase. The boot-up sequence and its state: [docs/cross-project/nedschorus-founding-plan.md](docs/cross-project/nedschorus-founding-plan.md).
