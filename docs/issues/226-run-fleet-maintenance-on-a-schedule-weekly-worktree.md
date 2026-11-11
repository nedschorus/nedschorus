---
issue: "[Before a seat is retired, report what still cites the paths the retirement removes](https://github.com/nedschorus/nedschorus/issues/226)"
kind: design
---

# Before a seat is retired, report what still cites the paths the retirement removes

Retiring a seat removes the seat's home under `~/agents/`. Nothing checks first whether main, an open issue or a live task list still cites a path that the retirement removes. This issue asks for that check.

## Narrowed 2026-09-30: the citation check only

This issue first asked for two things: worktree clean-up on a weekly schedule, and the citation check. The user ruled on the schedule in the walk open-items-this-seat-holds-2026-09-24 (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/open-items-this-seat-holds-2026-09-24-minutes.md`, the row for original item 17). His words: "I just added something (maybe a PR or GHI) to do a daily maintence thing that would trigger at noon. So let's not build anything weekly yet, let's push anything needing regular maintence into that noon maintennce step. Does that make sense?" He then approved, with "Y", narrowing this issue to the citation check.

- **Nothing is built on a weekly schedule.** Regular maintenance that needs the user's judgment goes into the noon step. The noon step is the daily memory review built by PR [From noon Pacific, a reincarnated Mac seat is asked for the day's review of both memory stores](https://github.com/nedschorus/nedschorus/pull/823): `memory_review_due_lines` in `nc-systems/handoff/handoff-supervisor.py`. The noon step carries only the memory review today. Giving the noon step a second job is a separate change, made when a second job arrives.
- **Worktree clean-up is already built, at the handoff.** Since PR [Each handoff removes the finished worktrees and merged branches](https://github.com/nedschorus/nedschorus/pull/664), every handoff runs `scripts/clean-worktrees.py --remove` through `remove_finished_worktrees_at_handoff` in `nc-systems/handoff/handoff-supervisor.py`. The cleaner removes a session worktree when the worktree has no commits beyond `origin/main` and no running process inside, and, for a worktree the Agent tool made for a subagent, when neither the worktree nor the subagent's transcript was written in the last hour. Uncommitted, untracked and ignored files do not keep a worktree: the cleaner names each one and discards it with the worktree. The one exception is a record under the worktree's `cold-read-records/` or `sanity-check-records/`, which the cleaner first ships to the log-store, keeping the worktree when a record does not ship. The cleaner also keeps a worktree whose files git cannot list. The supervisor prints one line of report on its console. This mechanical clean-up stays at the handoff and is no longer part of this issue.

## Added 2026-10-04: review worktrees outside `.claude/worktrees/`

This part brings one worktree clean-up back into this issue, at the user's request on 2026-10-04 that it join the daily maintenance; the citation check above is unchanged.

`scripts/clean-worktrees.py --remove` also runs daily at 06:30 on both machines, declared as `clean-worktrees` in `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`. It removes session worktrees under `.claude/worktrees/`, and, since PR [clean-worktrees also removes finished topic-worktrees beside the agent-homes, and keeps a worktree mid-rebase](https://github.com/nedschorus/nedschorus/pull/2237), finished topic-worktrees directly in `~/agents/` whose name is an agent-home's name, a hyphen and more, such as `cold-read-improvement-claude-md-batching-sentence` beside the agent-home `cold-read-improvement`. The cleaner counts a worktree in `~/agents/` as an agent-home when it is on a branch of the same name as its directory or holds a seat-brief (`CLAUDE.local.md`), and never removes an agent-home. It removes such a topic-worktree only when it is landed, vacant, not partway through a rebase, merge, cherry-pick or revert, free of uncommitted and untracked files, on a branch, and unwritten for 4 hours; it first ships the topic-worktree's walks and its cold-read and sanity-check records to the log-store, and keeps the topic-worktree if any of them does not ship. Among the worktrees the cleaner never judges, three kinds pile up, since no job removes them: the merge-lane's review checkouts; a worktree nested deeper in `~/agents/`, such as one under `~/agents/agent-instructions-editor-worktrees/`; and a topic-worktree beside a seat whose own home is on another branch and holds no seat-brief, since the cleaner then does not know that home as an agent-home. On ned-box on 2026-10-04, 82 of the 102 worktrees registered in `~/Projects/nedschorus` were merge-lane-2's review checkouts under `/tmp/claude-1000/-home-nedlern-agents-merge-lane-2/` (count from `git -C ~/Projects/nedschorus worktree list`); merge-lane-2 removed 71 of them by hand that day.

The job to add, on ned-box, where merge-lane-2 runs: `clean-worktrees` also removes merge-lane-2's review worktrees once their pull request is closed. It follows the rule merge-lane-2 gave in its message to fleet-restart-at-login on 2026-10-04, with one addition, that no process has its working directory inside the worktree:

- A worktree at `/tmp/claude-1000/-home-nedlern-agents-merge-lane-2/*/scratchpad/wt/pr<N>-head`, `pr<N>-merged` or `pr<N>-mut`, where `<N>` is the digits after `pr`, is removed once PR N on nedschorus/nedschorus is merged or closed (`gh pr view <N> --json state`).
- A reviewer's worktree under the same directory, at `*/scratchpad/rv*/wt/*` or with `mac-claude-pr<N>` in its path, is removed on the same condition.
- `*/scratchpad/wt/main` is never removed.
- Removal uses `git worktree remove --force`, because a merged checkout holds test byproducts, which are throwaway.
- Any other worktree under `/tmp/claude-1000/-home-nedlern-agents-merge-lane-2/`, and any whose number cannot be read, is left in place and listed in the job's output, `.claude/clean-worktrees.log`, as `clean-worktrees.py` already does for every worktree it keeps.

Next action for this part: extend `scripts/clean-worktrees.py`, which the daily job already runs, with these rules and their tests.

## Why the check is wanted

`scripts/clean-worktrees.py` never removes an agent-home under `~/agents/`, only the finished topic-worktrees beside one, which is correct — but retiring a seat is exactly where loose ends were found on 2026-08-31, and the check that found them was not "is it clean" but **"does anything still cite this?"** Sweeping main, all open issues and both live task lists for references into the paths being removed found two live citations into `doctrine-queue-drain` out of five candidate paths: the sanity-checker seat brief on main, since deleted (`git show b30aa47c:docs/agents/sanity-checker-instructions.md`), and issue [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161). The content-judgment checks run alongside that sweep produced no signal at all — the task stores were test fixtures, the unconsumed handoffs were superseded, and the one untracked design report turned out to be a specimen whose durable facts GHI [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161) had already extracted on purpose.

That citation check is mechanical and is the only part of the loose-ends sweep worth automating. It belongs with GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42)'s reference-integrity checker rather than here — same instrument, one more caller — scoped as "inbound references into a path about to be deleted." This issue depends on the reference-integrity checker and does not duplicate it.

What main has today (checked 2026-10-01): `scripts/dangling-path-citation-check.py` reports, for a change that removes a repository path, every line in the tree that still cites the removed path. That program reads only the repository's tree. It does not read open issues or task lists, and it does not know a seat's home under `~/agents/`.

## Next action

Extend the citation check under GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42) to take a set of paths about to be deleted and to read main, the open issues and the live task lists. Then add a seat-retirement report that runs the extended check on the seat's paths before anything is removed.

## Search receipt

`scripts/ghi-guide-agent-ask.py` over both mirrors, 2026-08-31: no issue covers periodic fleet maintenance, scheduling `clean-worktrees.py`, or a pre-deletion citation check. GHI [Queue drain procedure — the review process that empties wiki/queue, the pair queue, and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24) (queue drain) is deliberately on-demand and ruled that way; GHI [Build ghi-guide-agent — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)'s "maintenance sweep" is scoped to the GHI corpus only.

