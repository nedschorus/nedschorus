# Follow-on changes of walk item 1: the agent-home rests detached at main, every topic in its own worktree

Swept from origin/main at e2cf5ea2 on 2026-10-09 by an Explore subagent, at the user's word "we'll have to sweep the repo for cascading changes". No open pull request touched these lines at the time. Paths are repository-relative.

## Code

- `scripts/launch-claude-mac:316-327` and `scripts/launch-claude-ubuntu:373-386`: `worktree add <home> -b <seat> origin/main`, with a fallback that reuses an existing branch; becomes `worktree add --detach <home> origin/main`, the fallback and its comment go.
- `nc-systems/handoff/handoff-supervisor.py:785-846` `sync_working_branch_with_main` (callers 19, 724, 1623-1624): already handles detached; rename for what it syncs, drop the branch path, reword its `branch sync:` reports.
- `nc-systems/handoff/handoff-supervisor.py:201-210` `BRANCH_STATE_INSTRUCTION`: assumes the home is on a branch; say to start each topic in a new worktree.
- `.claude/hooks/session-location-write-guard.py:27-41`: the detached refusal tells the agent `git switch -c` in place; in an agent-home, tell it to make a topic worktree.
- `scripts/obsolete-file-edit-warning-hook.py:120, 127-130`: `git checkout -b <name> origin/main` and `git switch -c` advice; point to a topic worktree.
- `scripts/checkout-freshness-catch-up.py:6, 168, 205-209`: docstring names a seat branch; "Start your next topic with `git checkout -b`"; "run `git switch -c`" for work of its own; point to a topic worktree.
- `scripts/ghi-info-ask.py:649-651, ~683-684`: ghi-info's checkout "sits on its own `ghi-info` branch", and commits its link repairs there; both change.
- `scripts/design-to-main/design-to-main-git-record.py:101`: `git checkout -b <component> <start>` in whatever checkout runs it; check whether that can be an agent-home.

## Tests

- `.claude/hooks/session-location-write-guard-test.py:85-87, 100`
- `scripts/obsolete-file-edit-warning-hook-test.py:337, 345, 565`
- `scripts/checkout-freshness-catch-up-test.py:7-8, 367, 518`
- `nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py:563, 611, 625, 845-1007, 1186-1189, 2585`
- `nc-systems/handoff/tests/handoff-supervisor-session-end-and-resume-test.py` (the rename, ten places)
- `nc-systems/handoff/tests/uncommitted-work-snapshots-test.py:879`
- `scripts/recover-crashed-seats-test.py:396-410, 1235-1249, 1322-1337`
- `scripts/ghi-info-ask-test.py:789-801, 815`
- `nc-systems/cold-read/tests/cold-read-fast-read-test.py:899` (fixture branch name only)

## Agent instructions

- `docs/agents/seat-first-prompt.md:1, 7, 11, 14, 28`: "its own git branch"; step 2 expects the seat's branch and stops on detached; "Commit to your own branch and push it".
- `.claude/skills/start-new-agent-seat-on-ned-box/SKILL.md:10, 27`: the name names a branch, a branch-list check, "a worktree on the branch `<name>`".
- CLAUDE.md names no seat-branch; it does not state the worktree-per-topic rule, and adding it goes to the user.

## Documents

- `docs/nedschorus-wiki/nedschorus-glossary.md:19, 21, 61, 63`: agent-home, agent-seat, retire-seat, seat-branch (remove or retire the entry).
- `docs/nedschorus-wiki/nedschorus-sdlc-terms.md:8`: topic branch "Not a seat-branch".
- `docs/nedschorus-wiki/nedschorus-style-guide.md:15`: `seat-branch` in the `seat` row.
- `docs/nedschorus-wiki/nedschorus-agent-seat-model.md:18, 32, 38, 67, 69-71`
- `docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md:23, 24, 33, 49, 77`
- `docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md:64, 205-213, 350-351, 551`
- `docs/nedschorus-wiki/nedschorus-handoff-system-overview.md:53`: "often sits on a detached HEAD" becomes always.
- `docs/founding/choirmaster-founding-handoff.md:7`: historical; update or mark superseded.

## GHI-MDs

- `docs/issues/1121-one-design-of-record-for-the-project-s.md:13, 19`
- `docs/issues/236-pull-request-skill-how-a-change-reaches-main.md:38-56`: cuts topics from the seat-branch.
- `docs/issues/238-topic-branch-creation-script-design.md:35, 50, 56-61, 131`: the script makes a worktree instead.
- `docs/issues/45-remote-named-agent-launch-and-reattach.md:15`
- `docs/issues/1129-moving-an-agent-seat-to-the-other-machine.md:25`
- `docs/issues/256-four-small-skills-the-user-named-on-the.md:35`
- `docs/issues/386-project-term-sweep-rulings-and-open-work.md:111`
- `docs/issues/324-checkout-freshness-catch-up-reports-instead-of-merging.md:125` (quotes old hook text)
- `docs/issues/913-the-checkout-freshness-hook-treats-a-new-branch.md:13, 24, 44`
- `docs/issues/956-every-refusal-and-warning-a-program-hands-an.md:140-155, 370-379`: proposed rewrites still teach `switch -c`.
- `docs/issues/1036-move-mechanical-agent-chores-into-programs-and-hooks.md:30`
- `docs/issues/3-main-gatekeeper-build-slice-plan.md:31`: historical record; probably leave.

## Nothing to change

- No code makes topic worktrees outside `.claude/worktrees/`; `scripts/clean-worktrees.py` already treats agent-homes as outside its sweep.
- No code deletes or recreates a seat-branch.
- `.gitignore` already ignores `CLAUDE.local.md` and `.walk-approved`, so the new-seat skill can still write them into a detached agent-home.

## Found later in the walk

- `docs/issues/226-run-fleet-maintenance-on-a-schedule-weekly-worktree.md`: "Worktree clean-up is already built, at the handoff" says the cleaner keeps a worktree with uncommitted, untracked or ignored files; stale since PR 1042, and changes again with item 5's decision. Corrected through edit-GHI.
