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
- **Agent-seats** — the named, long-lived agents that do the work, one subject area each; the seat merge-lane-2 reviews and merges every pull request. Why the work is divided this way: `docs/nedsnodes-wiki/nedsnodes-agent-seat-model.md`.

## The agent model

Two kinds of agent, each defined in the glossary, `docs/nedsnodes-wiki/nedsnodes-glossary.md`:

- **Agent-seats** live indefinitely, as a chain of agent-sessions joined by session-handoffs: when a session's context runs low it hands off, and the handoff-supervisor starts a successor that reads the handoff, so a session's end costs minutes, not context. The machinery: `docs/nedsnodes-wiki/nedsnodes-handoff-architecture-overview.md`.
- **Fresh-agents** are spawned with minimal context for one job — a review, a fix round, a search, a single drafting call — and end with it. Their minimal context is the point: they are the system's test instrument for fresh-reader readability and its guard against context contamination.

## Where things live

| Place | Holds |
|---|---|
| `docs/nedsnodes-wiki/` | Standing knowledge, kept current (Obsidian vault). |
| `docs/issues/<n>-<slug>.md` | Working documents, one per GitHub issue, disposed when the issue closes. |
| `~/.claude/handoffs/` | Session handoffs, one file per agent-seat, on each machine only and never committed. |
| `nn-queue/` | User-requested notes awaiting their initial walk — verbatim, unreviewed, 90-day TTL; dispersed to durable homes at the walk. |
| `docs/nedsnodes-wiki/queue/`, `docs/issues/queue/` | Destination-rooted queues: wiki-bound doctrine and GHI-MD-bound documents awaiting the user's drain (promote / edit / demote / drop). |
| `nn-systems/` | The project's built systems, one directory each: `cold-read/` (the programs that run a cold-read-fast-read and a cold-read-full-run), `handoff/` (session reincarnation, the handoff-supervisor and the handoff writer), `main-gatekeeper/` (the program meant to be the only way a change reaches main, dormant until activated), `nn-shared-database/` (the service of the nn-shared-database) and `skills/` (programs that some of the skills run); beside them, `general-tools/`, which is not a system, as the glossary's nc-system entry says. |
| Issues labeled `queue-drain-candidate` | Issues awaiting the user's drain — same format as every issue, walkable; no work ever waits on one, and nothing requiring the user's admission takes effect without it. |

## Working in a fresh clone

Each agent-seat's commits carry its own name: its launcher, `scripts/launch-claude-ubuntu` or `scripts/launch-claude-mac`, sets `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL`, which outrank any git config. Each clone's own config holds the identity `unconfigured-agent <unconfigured-agent@nedschorus.invalid>`, set by the user, which the pre-commit hook, `scripts/git-client-side-hooks/pre-commit`, refuses, so an agent-session started without its launcher cannot commit. Do not run `git config user.name` or `git config user.email`: every worktree of a clone shares one `.git/config`, so the change replaces that identity for every worktree, and an agent-session started without its launcher could then commit under the new one. If the pre-commit hook refuses a commit, do what its message says.

## Status

The project's objective: [docs/nedsnodes-wiki/nedsnodes-ai-native-software-development-objective.md](nedsnodes-ai-native-software-development-objective.md).
