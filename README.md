# nedschorus

A system in which one human and a small number of AI agents build and improve the software-development system they themselves run on — a fresh minimal system succeeding the nedlern project. nedschorus is not a rebuild of nedlern: it starts from its own requirements, and cherry-picks from nedlern only the pieces that earn entry through the checkpoint. nedlern keeps running during the founding and then quiesces into a read-only legacy reference.

## Why this project exists

Its predecessor (nedlern, at `~/Projects/nedlern`) grew a working but heavy system: multi-agent messaging with delivery lifecycles, an eleven-state PR pipeline, layered enforcement hooks, a large doctrine corpus. Examined closely, most of that complexity was organizational — the cost of coordinating many agents, plus accumulated patches — not essential to the work being done. Re-derived from actual requirements with the minimal set of actors, each subsystem turned out small: messaging between agents became a pair of append-only log files; session continuity became one numbered handoff file plus its committed transcript; the path from change to production became a single writing agent and four states. Each re-derivation is specified under `docs/cross-project/`.

nedschorus keeps it that way: start from the simple system that works, cherry-pick from the legacy system only what earns entry, and let complexity be earned — never assumed.

## Founding principles

1. **Re-derive from the requirement; never inherit machinery by default.** Ask what is needed and no more; the old system's mechanisms are reference. Anything deliberately taken from them crosses the entry checkpoint (principle 6) — importing is a chosen act, never a migration habit.
2. **Complexity is earned, step by step:** manual → script the human runs → automation. Each step admitted on evidence, by the human.
3. **Behavior belongs in code wherever it can be expressed there** — testable, versionable, inert until called. Prose is for judgment only. When it is a choice between python and a prompt, python; between bash and python, python — bash only for one-liners not worth a file.
4. **Durable artifacts are written for a fresh reader** — an agent with repository access, the project instructions, and the document itself, but no conversation history — and tested by handing them to exactly such an agent.
5. **One gate to main.** The main-gatekeeper program holds the project's only push-capable credential; every check-in, by any agent, goes through it, and every mechanical check runs there from day one. Agents — all of them — edit in their own working copies, invoke the gatekeeper directly, and never push themselves.
6. **The old system is legacy:** read-only reference, freely read. Content that enters this repository from it is an import, recorded in the importing commit itself (the gatekeeper's import trailer, browsable via its `imports` query); the mechanism is defined once, in the main-gatekeeper specification ([main-gatekeeper-design.md](nc-systems/main-gatekeeper/main-gatekeeper-design.md)).
7. **Present-tense truth.** Documents state what is; git history holds what was. The built system is the source of truth — a design page carries the date on which it described that truth, and newer code and open issues may have advanced past it.

## The actors

- **The user** — the human. Reads every checked-in document, admits every rung of automation, owns every judgment only a human can make.
- **Agent-seats** — the named, long-lived agents that do the work, one subject area each; the merge-lane seat reviews and merges every pull request. Why the work is divided this way: `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`.

## The agent model

Two kinds of agent, each defined in the glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`:

- **Agent-seats** live indefinitely, as a chain of agent-sessions joined by session-handoffs: when a session's context runs low it hands off, and the handoff-supervisor starts a successor that reads the handoff, so a session's end costs minutes, not context. The machinery: `docs/nedschorus-wiki/nedschorus-handoff-system-overview.md`.
- **Fresh-agents** are spawned with minimal context for one job — a review, a fix round, a search, a single drafting call — and end with it. Their empty context is the point: they are the system's test instrument for fresh-reader readability and its guard against context contamination.

## Where things live

| Place | Holds |
|---|---|
| `docs/nedschorus-wiki/` | Standing knowledge, kept current (Obsidian vault). |
| `docs/issues/<n>-<slug>.md` | Working documents, one per GitHub issue, disposed when the issue closes. |
| `docs/cross-project/` | Artifacts both systems read, including the founding documents and specifications. |
| `handoff/` | Numbered session handoffs and their transcripts. |
| `nc-queue/` | User-requested notes awaiting their initial walk — verbatim, unreviewed, 90-day TTL; dispersed to durable homes at the walk. |
| `docs/nedschorus-wiki/queue/`, `docs/issues/queue/` | Destination-rooted queues: wiki-bound doctrine and GHI-MD-bound documents awaiting the user's drain (promote / edit / demote / drop). |
| `legacy-feature-queue/` | Undecided legacy features (consider-feature class, rewrite policy) awaiting decision; deciding is the drain. |
| `entry-manifest.md` | The ledger of everything imported from the legacy system. |
| Issues labeled `draft` | Draft issues awaiting the user's drain — same format as every issue, walkable; no work ever waits on one, and nothing requiring the user's admission takes effect without it. |

## Working in a fresh clone

A checkout carries its own git identity, and a clone arrives without one. Set it before the first commit, or git falls through to the machine's global identity — which on this project's Mac is the user's own account, so the commit is authored as him:

    git config user.name  <the agent-seat or host doing the work, never the user>
    git config user.email <that name>@nedschorus.invalid
    git config user.useConfigOnly true

`user.useConfigOnly=true` is the half that does the work: it makes git refuse to fall through to the global config at all, so a missing identity fails at commit time instead of quietly signing someone else's name. `nc-systems/main-gatekeeper/tests/main-gatekeeper-test.py` asserts all three against the enclosing checkout, which is how a fresh clone finds out — it fails one case with the setting it found and the command that fixes it.

## Status

Founding phase, retired. The current architecture and working plan: [docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md](docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md). The boot-up plan's record: `git show 615a230:docs/cross-project/nedschorus-founding-plan.md`.
