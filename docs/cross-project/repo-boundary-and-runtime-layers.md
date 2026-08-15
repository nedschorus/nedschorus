# Repository boundary and runtime layers

> **DRAFT — do not rely on the manifest below.** Reviewed 2026-08-14 by the eight-cell md-review grid; both defect-hunt cells returned "clean sections: none", 83 findings between them. The findings are triaged in `md-review-records/2026-08-14-repo-boundary-and-runtime-layers/dispositions.md` and are **not yet applied**. Three of them are disqualifying on their own: one citation resolves only on an unmerged branch, the component table was built from filenames rather than from reading the files, and the filing rule at the end contradicts the table it is meant to extend. Work resumes when pull request #58 lands, because two rows describe files that arrive with it. The three-layer model and the runtime analysis are believed sound; the classifications are not.

Where a new file belongs, and why. Ruled by the user 2026-08-14, in the walk that also hardened the box's backups.

Read this before creating a script, skill, hook, or lasting document, and before proposing that anything move between repositories. It answers one question — *which repository, and which machine* — and it answers it for three runtimes rather than one.

## The problem this exists to settle

`nedschorus` is one repository holding two different kinds of thing. Some of it is about nedschorus: its issues, its wiki, its seat briefs, its founding decisions. The rest is machinery that has nothing to do with this project in particular — a handoff supervisor, agent launchers, a markdown review grid, a status line, skills. A second project already exists on the same machine (`~/nedsmessenger`, with its own accumulated agent transcripts), so "shared machinery" is no longer hypothetical.

The boundary was gestured at rather than decided. `docs/cross-project/` exists, which is the gesture — but `docs/cross-project/nedschorus-founding-plan.md` sits inside it, this project's own founding document filed in the shared drawer. That single misfiling is the evidence: there was a name for the boundary but no rule, so nothing could be checked against it.

## What is not the problem

**Not disk layout.** Moving files between directories is cheap and reversible, and a wrong directory costs a `git mv`.

**Not tidiness.** A single repository holding both kinds of thing works fine for one person on two machines. If that were the whole picture, the right answer would be to leave it alone.

The problem is **delivery**: getting the machinery to a runtime that needs it. That is what makes the boundary load-bearing, and it is why the answer depends on runtimes rather than on taste.

## The three runtimes

A "runtime" here means a place a Claude Code session actually runs. There are three, and they differ in what they can reach.

| Runtime | Where it runs | Filesystem it has |
|---|---|---|
| **The box** | `ned-box`, Ubuntu, on the LAN | The box's, including `~/.claude`, seat worktrees, and `/mnt/backup` |
| **The Mac** | The user's Mac, where he sits | The Mac's, including its own `~/.claude` and Time Machine |
| **The cloud** | Anthropic's infrastructure | Neither machine's — it clones a git repository and works there |

The cloud runtime is the one that constrains everything below. It has no `~/.claude` to install into, no way to read a machine-local file, and no path to either machine. **A cloud session can reach exactly what is inside the git repository it cloned, and nothing else.**

Two further facts about cloud sessions, read from the Claude Code 2.1.232 binary rather than assumed, with the detail recorded in `docs/issues/queue/45-session-seat-and-isolation-riders.md`:

- **`claude --teleport` moves a session between the cloud and a local CLI**, in both directions. It requires a clean local working directory and requires running **from a checkout of the same repository the cloud session used**.
- **Cloud sessions sync files under hard budgets** and stop rather than degrade quietly when a repository has more files than per-turn sync can track. Repository size is therefore a functional limit on the cloud runtime, not merely a speed one.

## The three layers

Every component belongs to exactly one of these, decided by *where it must physically be at the moment it is used*.

### Layer 1 — Runtime: must be present in every session

The status line, skills, hooks, and the global `CLAUDE.md`. Claude Code reads these from `~/.claude/` and from the working directory's `.claude/` **at session start**. Nothing an agent does later can load them.

These want to be **installed to `~/.claude/` on each machine**, not vendored into every project. That is not a workaround — it is the path the harness provides, and the user already relies on it: `~/.claude/CLAUDE.md` loads into every session on the box unconditionally, with no recall step to forget.

The cost, which must be designed for rather than discovered: an installed copy can silently go stale against its source. The user has already ruled on this exact hazard in another context, requiring the git-gatekeeper to version itself and upgrade automatically, because *"AI's go in an infinite loop trying to fix problems without realizing they need to deploy those fixes."* **Any install step here carries the same obligation: a version stamp and a staleness check, from the first version.**

### Layer 2 — Tools: invoked by path when needed

The handoff supervisor, the launchers, the md-review grid, the drift lint, the git-gatekeeper, the backup health check. These are run by name at the moment they are wanted, so they need to exist on disk somewhere findable — a checkout on `PATH` — but not to be loaded at session start.

This is the layer that most wants its own repository, because it is what a second project would clone to get working.

### Layer 3 — Project content: belongs to one project

Issues, the wiki, seat briefs, drafts, design documents about this project, and the founding decisions. Cheapest test: **would a different project want this file unchanged?** If the answer needs a "well, it depends", it is project content.

## The manifest

Every component in the repository as of 2026-08-14, classified. Layer 3 entries are listed by directory rather than by file, since they are numerous and uniform.

| Component | Layer | Cloud can reach it? |
|---|---|---|
| `scripts/session-statusline-command.py` | 1 — runtime | Only if in the cloned repository |
| `.claude/hooks/instruction-file-guard.py` | 1 — runtime | Only if in the cloned repository |
| `.claude/hooks/backup-and-snapshot-write-guard.py` *(pending PR #58)* | 1 — runtime | Irrelevant: it guards machine-local paths |
| `scripts/handoff-context-threshold-hook.py` | 1 — runtime | Only if in the cloned repository |
| `.claude/skills/walk-me-through/` | 1 — runtime | Only if in the cloned repository |
| `.claude/skills/md-review/` | 1 — runtime | Only if in the cloned repository |
| `.claude/skills/handoff/` | 1 — runtime | Only if in the cloned repository |
| `.claude/skills/ghi-write/` | 1 — runtime | Only if in the cloned repository |
| `scripts/handoff-supervisor.py` | 2 — tool | No: it manages machine-local sessions |
| `scripts/handoff-write-and-check-supervisor.py` | 2 — tool | No: same |
| `scripts/handoff-extract-conversation.py` | 2 — tool | No: reads machine-local transcripts |
| `scripts/launch-claude-ubuntu`, `scripts/launch-claude-mac` | 2 — tool | No: they reach specific machines |
| `scripts/md-review-grid.py` and its two cell runners | 2 — tool | Yes, if the runtimes it shells out to exist there |
| `scripts/md-drift-lint.py` | 2 — tool | Yes |
| `scripts/git-gatekeeper.py` | 2 — tool | Yes |
| `scripts/backup-health-check.py` *(pending PR #58)* | 2 — tool | No: it reads machine-local backup state |
| `docs/cross-project/git-gatekeeper-design.md` | 2 — tool's design | Yes |
| `docs/cross-project/fast-handoff-design.md` | 2 — tool's design | Yes |
| `docs/cross-project/fleet-machine-paths-and-checkouts.md` | 2 — tool's design | Yes |
| `docs/cross-project/nc-python-toolchain-plan.md` | 2 — unverified, see below | Yes |
| `docs/cross-project/nc-python-toolchain-target-architecture.md` | 2 — unverified, see below | Yes |
| `docs/cross-project/comms-bridge-spec.md` | 2 — unverified, see below | Yes |
| `docs/cross-project/seed-claude-md-draft.md` | 2 — unverified, see below | Yes |
| `docs/cross-project/nedschorus-founding-plan.md` | **3 — misfiled**, see below | Yes |
| `docs/agents/` — seat model and briefs | 3 — project content | Yes |
| `docs/issues/`, `docs/wiki/`, `docs/drafts/`, `docs/founding/` | 3 — project content | Yes |
| `md-review-records/` | 3 — project content | Yes |

**Four entries marked unverified** were classified from their filenames and their placement in `docs/cross-project/`, not from reading them. Whoever next touches them should confirm or correct the row rather than inherit the guess.

**One entry is misfiled and has a ruled destination.** `docs/cross-project/nedschorus-founding-plan.md` moves to `docs/nedschorus-plan.md` and is retitled — its heading already reads "nedschorus Boot-Up Plan", so the file has disagreed with its own name for some time. The move was ruled 2026-08-14 and deliberately **not** executed at the time: 14 files cite it by path, one of them `.claude/skills/ghi-write/SKILL.md`, which is instruction-class and needs its own walked approval, and two more are being rewritten in an unmerged branch. It waits for that branch to land.

## The boundary: what was decided, and what is still open

**Decided: the three-layer model above, and that the manifest is its operative half.** A layer table with no per-file classification decides nothing, and a classification with no reasoning cannot be extended. They stay in one document for that reason.

**Decided: do not split the repository yet.** The case for splitting is real and got stronger during the walk that produced this document — a second project exists, and cloud sessions can only receive what a repository carries. But the case against is concrete and unresolved:

1. **A split needs an install mechanism with a version check, built first.** Without it, the split reproduces exactly the failure the user predicted for the gatekeeper: fixes that are made but never deployed, chased in a loop.
2. **A cloud session is bound to one repository.** If the machinery leaves this repository, a cloud session that cloned `nedschorus` can no longer see it, and a `--teleport` lands in the project checkout. The cloud runtime is an argument *for* a shared repository and simultaneously a constraint *against* splitting the one a cloud session uses. Whichever repository a cloud session clones is the one it gets.
3. **Two repositories mean two review-and-merge lanes**, and the project's whole change-control design is one door to main. Splitting doubles the credential work that is already the blocking item for the git-gatekeeper.

The manifest is what makes the split cheap when it happens: the boundary is drawn and every file is classified, so the split becomes a mechanical operation against a list rather than an archaeology exercise. Deciding the classification while it is free is the point.

**Open, and the user's to answer: which account owns which repository.** He works under two identities — `ned@lerner1.com` for the non-profit and `junk@lerner1.com` for personal — and a cloud session authenticated as one may not be able to read a repository owned by the other. `nedschorus` currently lives under the `nedschorus` GitHub organisation and merges run as `NedLern`. Until this is answered, any split risks producing a repository that some of his own sessions cannot clone. **Answer it before splitting, not during.**

## Filing rule

For a new file, in order:

1. **Would a different project want this unchanged?** No → layer 3, this repository, under `docs/` or wherever its kind lives.
2. **Must it be loaded at session start to work?** Yes → layer 1. It lives in the repository today; when the split happens it becomes an installed artifact, and it needs the version stamp described above.
3. **Otherwise it is layer 2** — a tool, in `scripts/`, with its design document in `docs/cross-project/`.

When a file's layer is genuinely unclear, record the ambiguity in the manifest row rather than picking silently. A wrong row that says it is uncertain is worth more than a confident one nobody can check.
