# Draft rule — the session task list is not durable state (awaiting the user's drain)

One rule candidate, user-stated 2026-09-11 at the close of the cold-read-research open-items walk. Destined for CLAUDE.md; queued rather than landed, because CLAUDE.md is operative prose.

**The rule, in the user's words:** "Tasks only survive as long as the worktree - these should be incorporated in GHIs or their paired design files. Or perhaps in a queue."

**What that means in practice.** An agent's task list is seat-local working state. It is invisible to other seats, invisible on the other machine, and it does not outlive the worktree — and worktrees are removed routinely, by `scripts/clean-worktrees.py` among other paths. So anything carrying pending state that must outlive this seat goes to one of three durable homes, the same three the ghi-write skill already names:

- a **GitHub issue**, for anything with its own next action and its own closure;
- its **paired document** under `docs/issues/<number>-<slug>.md`, for substantial working material riding with an issue;
- a **queue file**, for material whose fate is not yet decided — `docs/wiki/queue/` for wiki-bound doctrine, `docs/issues/queue/` for pair-bound documents.

A task list entry is then a pointer to the durable home, not the home itself.

**Why, from the occasion that produced it.** The 2026-09-11 open-items walk produced ten rulings and created seven tasks. All of the reasoning behind them sat in the task list and in the walk's minutes — and the minutes live in a gitignored directory that, as of that date, no program ships anywhere ([nedschorus#335](https://github.com/nedschorus/nedschorus/issues/335)). The user's challenge was exact: "if you just leave info in a walk it's dead info." Eight issues were then filed or edited to carry what the tasks held.

**The same reasoning applies to a walk's minutes,** which are equally invisible to everyone but the seat that wrote them. A walk's rulings reach the project through the issues, pull requests and queue files the walk produces, not through its minutes. The minutes are the recovery mechanism for an interrupted walk and the record of how a ruling was reached; they are not where the work lives.
