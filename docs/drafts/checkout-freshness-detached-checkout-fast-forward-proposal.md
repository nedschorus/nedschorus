# A detached checkout with no work of its own is moved forward to main

## The problem

An agent-seat's own checkout, such as `/Users/el/agents/MD-skills`, often sits on a detached HEAD: it points at a commit, not at a branch, because the agent does its work in separate worktrees, one per branch. CLAUDE.md, the skills under `.claude/skills/` and the hooks wired in `.claude/settings.json` load from that checkout. While it falls behind main, the agent runs under older instructions than main's.

On 2026-10-08 the MD-skills checkout was 86 commits behind main. The /walk-me-through skill the user invoked loaded its old text, from before a rule change the user had approved and merged, and the agent's CLAUDE.md lacked main's rewritten naming rule. Two programs could have moved the checkout forward, and neither did:

- `sync_working_branch_with_main` in `nc-systems/handoff/handoff-supervisor.py`, run when a seat launches, leaves the checkout as it is whenever `git status --porcelain` prints anything. That includes untracked files: three untracked drafts stopped the sync. A fast-forward does not need untracked files cleared, because git refuses to overwrite an untracked file and names it.
- `scripts/checkout-freshness-catch-up.py`, run at the end of every turn, never moves a detached HEAD. It tells the agent "You are on a detached HEAD; check out your branch before working.", which an agent cannot follow in a checkout that has no branch. The agent read the note as background and went on.

## The change

Both programs move a detached HEAD forward to origin/main when, and only when, all of these hold:

- HEAD has no commits of its own: every commit it holds is already on origin/main;
- the checkout has no uncommitted change to a tracked file, staged or not; untracked files do not count;
- no rebase, merge, cherry-pick, revert or bisect is in progress.

The move is `git merge --ff-only origin/main`, which moves HEAD only forward, and refuses if a file main adds would overwrite an untracked file. A checkout already at origin/main is left alone, and nothing is said, as today. The turn-end hook's rules for a checkout on a branch, never-pushed or pushed, stay as they are; they already ignore untracked files. The machine's reference checkout, the repository's main worktree kept on the main branch, such as `/Users/el/Projects/nedschorus`, already uses the same three conditions and is unchanged.

At launch, the supervisor's branch sync stops counting untracked files for every checkout, on a branch or detached, because the reason above holds for both: it fast-forwards a checkout that is strictly behind main and has no tracked changes and no git operation in progress.

| State of a detached checkout | What happens | What the agent is told |
|---|---|---|
| No commits of its own, no tracked changes, no git operation in progress | Moved forward to origin/main | Message A |
| Commits of its own | Not moved | Message B, own-commits line |
| Uncommitted tracked changes | Not moved | Message B, tracked-changes line |
| A rebase, merge, cherry-pick, revert or bisect in progress | Not moved | Message B, in-progress line |
| Git refused the fast-forward | Not moved | Message B, refused line |

The supervisor's one-line report keeps its present forms, `branch sync: {branch} fast-forwarded to main ({commit})` and `branch sync: {branch} left as is — {reason}`, where `{branch}` reads `HEAD` for a detached checkout and `{reason}` is one of: `{count} uncommitted tracked change(s)`, `a {operation} in progress`, or git's own error when the fast-forward is refused. The reports for a checkout ahead of main, or both ahead and behind, are unchanged.

## The messages the agent is told

Each message follows the heading and the list of files changed on main that the hook prints today, both computed before any move, so that they describe what moved. For example:

```
checkout-freshness: detached HEAD is 86 behind origin/main (0 own commit(s); detached HEAD).
Changed on main since your merge base:
  your standing instructions (1): CLAUDE.md
  skills you run under (2): .claude/skills/cold-read/prompts/terminology.md, .claude/skills/walk-me-through/SKILL.md
```

Each message ends, as every note from this hook does today, with the line "Do not report this to the user: he does not need to hear that main moved, or what other agents merged, unless it changes the work you are doing with him."

**Message A**, after a move:

```
This checkout's detached HEAD was moved forward to origin/main: it held no commits of its own and no uncommitted tracked changes, so nothing was lost.
CLAUDE.md, the skills and the hooks load from this checkout, so what you read from them earlier in this session may be out of date.
If CLAUDE.md is listed above, read it again before your next action.
If a skill you are following is listed above, read that skill's SKILL.md under .claude/skills/ again before its next step.
```

**Message B**, when the checkout was not moved. The first two lines always print; after them the hook prints one line for each condition that holds, in the order below, chosen by the program, not by the agent:

```
This checkout's detached HEAD was not moved forward: {reason}.
Until it moves, CLAUDE.md, the skills and the hooks you run under are older than main's.
```

followed by those of these lines whose condition holds:

```
A {operation} is in progress: finish it or abort it; the next turn's end moves the checkout forward.
```

```
It holds commits of its own: run `git switch -c <branch name>` so they are kept on a branch; the hook then rebases that branch onto origin/main at the next turn's end.
```

```
It has uncommitted tracked changes: commit them on a branch or set them aside; the next turn's end moves the checkout forward.
```

```
Git refused the fast-forward: {error}
If git names an untracked file that main would overwrite, move that file out of the way; the next turn's end moves the checkout forward.
Otherwise, tell the user this message.
```

`{reason}` names every condition that holds, joined by "; ": "a {operation} in progress", "{count} commit(s) of its own", "{count} uncommitted tracked change(s)", or "git refused the fast-forward". `{operation}` is "rebase", "merge", "cherry-pick", "revert" or "bisect". `{error}` is git's error, first line. Git is asked to fast-forward only when no other condition holds, so the refused lines never print beside another.

Message B is told once per update of main, as the detached note is today; message A is told every time a move happens, because files changed under the agent.

## Tests

- A detached checkout behind main, holding an untracked file that main does not add, is moved forward, and message A prints.
- One case per row of the table where the checkout is not moved: the checkout stays where it was, and message B prints with the matching line and no other.
- A checkout with both commits of its own and tracked changes: message B names both reasons and prints both lines, in order.
- A checkout already at origin/main prints nothing.
- The launch-time sync: a detached checkout and a branch checkout, each behind main with an untracked file, are fast-forwarded; a tracked change still leaves either as it is, and the report names the reason.
