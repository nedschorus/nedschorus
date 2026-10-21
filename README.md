# nedschorus

A system in which one human and a small number of AI agents build and improve the software-development system they themselves run on.

## Founding principles

1. **Re-derive from the requirement; never inherit machinery by default.** Ask what is needed and no more.
2. **Complexity is earned, step by step:** manual → script the human runs → automation. Each step admitted on evidence, by the human.
3. **Behavior belongs in code wherever it can be expressed there** — testable, versionable, inert until called. Prose is for judgment only. When it is a choice between python and a prompt, python; between bash and python, python — bash only for one-liners not worth a file.
4. **Durable artifacts are written for a fresh reader** — an agent with repository access, the project instructions, and the document itself, but no conversation history — and tested by handing them to exactly such an agent.
5. **Present-tense truth.** Documents state what is; git history holds what was. The built system is the source of truth — a design page carries the date on which it described that truth, and newer code and open issues may have advanced past it.

## The actors

- **The user** — the human. Reads every checked-in document, admits every rung of automation, owns every judgment only a human can make.
- **Agent-seats** — the named, long-lived agents that do the work, one subject area each; the seat merge-lane-2 reviews and merges every pull request. Why the work is divided this way: `docs/nedschorus-wiki/nedschorus-agent-seat-model.md`.

## The agent model

Two kinds of agent, each defined in the glossary, `docs/nedschorus-wiki/nedschorus-glossary.md`:

- **Agent-seats** live indefinitely, as a chain of agent-sessions joined by session-handoffs: when a session's context runs low it hands off, and the handoff-supervisor starts a successor that reads the handoff, so a session's end costs minutes, not context. The machinery: `docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md`.
- **Fresh-agents** are spawned with minimal context for one job — a review, a fix round, a search, a single drafting call — and end with it. Their empty context is the point: they are the system's test instrument for fresh-reader readability and its guard against context contamination.

## Where things live

| Place | Holds |
|---|---|
| `docs/nedschorus-wiki/` | Standing knowledge, kept current (Obsidian vault). |
| `docs/issues/<n>-<slug>.md` | Working documents, one per GitHub issue, disposed when the issue closes. |
| `~/.claude/handoffs/` | Session handoffs, one file per agent-seat, on each machine only and never committed. |
| `nc-queue/` | User-requested notes awaiting their initial walk — verbatim, unreviewed, 90-day TTL; dispersed to durable homes at the walk. |
| `docs/nedschorus-wiki/queue/`, `docs/issues/queue/` | Destination-rooted queues: wiki-bound doctrine and GHI-MD-bound documents awaiting the user's drain (promote / edit / demote / drop). |
| `nc-systems/` | The project's built systems, one directory each with its program, design document and tests: `handoff/` (session reincarnation, the handoff-supervisor and the handoff writer) and `main-gatekeeper/` (the program meant to be the only way a change reaches main, dormant until activated). |
| Issues labeled `queue-drain-candidate` | Issues awaiting the user's drain — same format as every issue, walkable; no work ever waits on one, and nothing requiring the user's admission takes effect without it. |

## Working in a fresh clone

A checkout carries its own git identity, and a clone arrives without one. Set it before the first commit, or git falls through to the machine's global identity — which on this project's Mac is the user's own account, so the commit is authored as him:

    git config user.name  <the agent-seat or host doing the work, never the user>
    git config user.email <that name>@nedschorus.invalid
    git config user.useConfigOnly true

The local `user.name` and `user.email` are what stop a commit being authored as the user: being local, they override the global identity. `user.useConfigOnly=true` does not block the global config — it stops git guessing an identity from the machine when no configuration carries one, so a missing identity fails loudly instead of being invented. Set all three, then confirm with `git var GIT_AUTHOR_IDENT`, which answers the identity your commits will carry: if it names the user, the local settings are not in place. `nc-systems/main-gatekeeper/tests/main-gatekeeper-test.py` checks all three against the enclosing checkout and fails with the value it found and the commands that fix it; it reads git's merged configuration, so the `git var` line above, not a green suite, is the proof.

## Status

The project's objective: [docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md](docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md).
