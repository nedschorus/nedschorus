# Agent-seat temp folders: one root on each machine, and a daily job that deletes what has not changed for 7 days: design

Status: pending approval of the decisions in § 11; not built. The user approved the direction on 2026-11-18 at 05:57Z, answering "A" to item 60.2 of merge-lane-2's approval-walk (walk-document `/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-pr-2760-pr-2695-and-emergency-stop-merges-approval-walk-2026-11-08.md`; walk-minutes beside it, line 810). His words on 2026-11-11: "simply marking temp things as temp and then deleting them after a week of no changes".

## 1. The problem

Five programs and rules clean up leftovers today, each with its own keep-rules (§ 6 says what each does). Even so, nothing cleans merge-lane-2's merge-helpers folder in the log-store, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers`, which held 55 GB on 2026-11-17, and the log-store is in ned-box's hourly Timeshift backup. Each new keep-rule adds code and tests for a case that may never happen, as PR 3219 did before it was closed.

This design replaces the keep-rules for temporary things with one rule: a program puts each temporary thing in its own folder under one root, and a daily job deletes any such folder in which nothing has changed for 7 days. Worktrees that hold an agent-seat's own branch are not temporary and stay where they are.

## 2. The root and its layout

The root on each machine is `~/.cache/nedsnodes-temp-folders-by-agent-seat/`, unless the user chooses `~/nedsnodes-temp-folders-by-agent-seat/` (decision 1 in § 11). It is named for the project after the nedschorus→nedsnodes rename, and the build follows the rename (§ 10).

Layout: `<root>/<agent-seat>/<temp folder>/`. The agent-seat is the one whose program makes the folder. A program that belongs to one agent-seat names it: merge-lane-2's programs name merge-lane-2, so their folders go under `<root>/merge-lane-2/` also when a cron job runs them. Any other program reads the agent-seat from the environment variable the handoff-supervisor sets for every agent-session it starts (`HANDOFF_SUPERVISOR_AGENT_NAME_ENVIRONMENT_VARIABLE` in `nc-systems/handoff/handoff-supervisor.py`), and a program started outside any agent-session uses `<root>/no-agent-seat/`.

A temp folder is one entry directly inside `<root>/<agent-seat>/`. It is the unit the daily job judges and deletes. A program that makes temporary things makes one temp folder for each piece of work, such as one review of one pull request, never one long-lived folder that collects many pieces of work, because a folder that something writes into every day is never deleted. One shared function, in `nc-systems/general-tools/agent-seat-temp-folder-create-common.py`, takes the agent-seat and a name, creates `<root>/<agent-seat>/` when it is missing, and returns the path `<root>/<agent-seat>/<name>` without creating it, so that a caller can hand the path to `git worktree add`, which refuses a path that exists, or make the folder itself.

## 3. The daily job

`nc-systems/general-tools/agent-seat-temp-folders-unchanged-seven-days-delete.py` runs once a day on ned-box at 07:30, the slot of the job it replaces (§ 6), installed from `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`. It needs no judgment. For each entry directly inside each `<root>/<agent-seat>/`, folder or file alike, it:

1. Reads the entry's newest change time: the latest of the modification time and the status-change time (mtime and ctime) of the entry and, for a folder, of every entry under it at any depth, read with lstat, never following a symbolic link. The status-change time counts because `mv` and `cp -p` keep an old modification time on a file they have just put there, while the status-change time of a folder moved into the root becomes the time of the move, as a test on ned-box's btrfs filesystem showed on 2026-11-17. So a folder moved into the root is not deleted on the next day for its contents' age.
2. Keeps the entry when that time is less than 7 days old, or in the future.
3. Otherwise deletes it. When the entry is a folder holding a `.git` file, it is a git worktree: the job runs `git worktree remove --force` on it in the repository the `.git` file names, so that git's registration goes with it. A registration left behind would make the next `git worktree add` at that path fail, as merge-lane-2's `scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py` does for a pull request reviewed again. Any other entry is deleted with its contents. A worktree nested deeper inside a deleted folder leaves a registration behind, which the cleaner's dead-registration line reports; nothing makes a worktree again at such a path.
4. Removes `<root>/<agent-seat>/` when the deletions have left it empty.

Before each deletion it prints `deleting <entry>`, flushed, and appends `<UTC time><tab>deleting<tab><entry>` to the local file `/home/nedlern/nedsnodes-logs/agent-seat-temp-folders-deleted-log/<machine>.txt` in the log-store, so the log names every entry a run stopped part way may have deleted; when the deletion then fails, it appends `<UTC time><tab>failed<tab><entry>`. `--dry-run` prints `would delete` and deletes and writes nothing. An entry whose tree cannot be read in full, or whose deletion or `git worktree remove` fails, such as a locked worktree, is kept and named on a line on stderr, and the job goes on to the others and exits 1. No user-alert is written.

What the job does not handle: a running process or a bound socket inside a temp folder in which nothing has changed for 7 days. The folder is deleted. The program that lost its folder makes a new one, or fails with an error that names the missing path, and its work is done again.

## 4. What moves into the root

| Temporary thing | Where it is today | Temp folder under `<root>/merge-lane-2/` unless named otherwise | What its program does when the folder is gone |
|---|---|---|---|
| Review worktrees `pr<n>-head`, `pr<n>-merged` | `~/.cache/merge-lane-review-worktrees/` | `pr<n>-head`, `pr<n>-merged` | `scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py` makes both again; the daily job removed git's registration with the folder. |
| The review tools worktree at main | `~/.cache/merge-lane-review-worktrees/main` | `review-tools-worktree-at-main` | Made again from the reference-checkout when missing, as `scripts/merge-lane-pull-request-helpers-common-options-paths-and-token.py` provides. It is the one temp folder that serves many reviews; every review updates it, so it is deleted only after merge-lane-2 has reviewed nothing for 7 days, and the next review makes it again. |
| Reviewer scratch folders `rv<tag>` | `~/.cache/merge-lane-pull-request-reviewer-scratch-directories/` | `rv<tag>` | `scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts.py` makes it for each review. |
| A pull request's test runs on its `pr<n>-merged` worktree | `merge-helpers/hr/pr<n>/` | `hr-pr<n>` | The next test run makes it. The merge program, finding no test record there, takes the nc-head-commit as its starting point, which selects more test suites, never fewer, and prints that it did so. |
| After-merge test logs | `merge-helpers/pr<n>-after-merge-test-run-logs-<commit>/` | the same name | Written once by the merge program and read by merge-lane-2 only while a failure is fresh. |
| Claude Code's temporary folder for each agent-session on ned-box | `~/.cache/claude-code-tmp/claude-<uid>/<project>/<session id>/` | `<root>/<agent-seat>/claude-code-<session id>`, given as `CLAUDE_CODE_TMPDIR` by the handoff-supervisor | Claude Code makes the folder when it is missing. One temp folder for each agent-session, not one for the agent-seat, because a folder an agent-seat uses every day would never be deleted, and its old agent-sessions' folders would grow as they once filled `/tmp`. A `claude --resume` of the same agent-session gets the same folder, since the session id is the same. |

merge-lane-2's programs take these paths from `scripts/merge-lane-pull-request-helpers-common-options-paths-and-token.py` and their own option defaults; the build changes those defaults and every test that names the old paths (§ 10). An open pull request whose review has been idle for 7 days loses its review worktrees and scratch, and its next review makes them again; the retired sweep kept 12 such scratch folders on 2026-11-17.

## 5. Which parts of merge-helpers are temporary

Measured with `du` on 2026-11-17: 55 GB in all.

| Part | Size | Class | Why |
|---|---|---|---|
| `hr/pr<n>/`, 1,705 folders | 18 GB, nearly all of it in `tmp/`; `stdout`, `stderr` and `log-store/` together hold about 4.9 GB | temporary | Each pull request's test runs; § 4 says what happens when one is gone. |
| `hr/store/` | 3.7 MB | state, stays | The test recordings every merge-lane test run selects by; losing it makes every test run run more suites. |
| `rv<tag>/`, 388 folders, nothing written since 2026-10-19 | 21 GB, of which 19.5 GB is `replay/` | temporary, with records at the top of each | Reviewer scratch from before scratch moved to `~/.cache`; nothing writes here now. The files directly in each `rv<tag>/`, such as `review-body.md`, `body.md` and `review.json`, are review records and stay; the review bodies were also posted on GitHub. The subfolders of each `rv<tag>/`, such as `rv<tag>/replay/`, `rv<tag>/wt/`, `rv<tag>/harness/`, `rv<tag>/runs/` and `rv<tag>/mutants/`, are temporary. |
| `pr<n>-after-merge-test-run-logs-<commit>/`, 1,046 folders | 15 GB | temporary | No GHI-MD or walk-document cites one. |
| Everything else | 416 MB | records and state, stay | Records that reviews and GHI-MDs cite: `briefs/` (79 MB), `cx/` Codex reports (33 MB), `claude-reviews/` (46 MB), and the files at the top level, such as `review-<n>.log`, `approve-<n>.md`, `brief-specs-<n>.json`, `codex-<n>.out`, `commissioned-<n>.txt` and the Codex research reports. State the programs need: `tripwire-bin/`, `loop/`, `backlog-scripts/`, the hold list of `scripts/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py`, the two worktrees in the top-level `merge-helpers/wt/`, `cc-socks/`. merge-lane-2's hand-made scratch folders, such as `fast-reads-<n>/`, `fr-<n>/` and `tmpdir-*/`, stay until merge-lane-2 judges them (§ 8). |

So about 54 GB is temporary, and about 0.4 GB stays.

**The one-off move.** A program moves the temporary parts above into `<root>/merge-lane-2/`, once merge-lane-2's programs write to the root: each `hr/pr<n>/` becomes the temp folder `hr-pr<n>`, each after-merge log folder keeps its name, and the subfolders of each `rv<tag>/` go together into one temp folder `rv<tag>-subfolders`, leaving the files directly in `rv<tag>/` where they are. It leaves in place every file that a tracked file on main or a walk-document cites by its exact path, so that citation still opens, with the folders above it: the program finds them by searching main's tracked files and the walk-documents in every agent-home and in the log-store for paths under `merge-helpers/hr/` and `merge-helpers/rv`, and on 2026-11-17 that search found 28 files, such as the test logs GHI 1233 cites under `hr/pr<n>/tmp/` and the file GHI 3096 cites under `rv1289r1-dead-reviewer-2352/`. Citations that name a pattern rather than a file, such as GHI 2569's `hr/pr*/stderr` and GHI 1374's `hr/*/log-store/...`, describe measurements already made, and stop opening anything once the folders are deleted (decision 3 in § 11). A moved folder gets a new status-change time, so the daily job deletes it 7 days after the move, not on the next day.

## 6. The jobs today, and what happens to each

| Job | What it does today | What happens to it |
|---|---|---|
| `nc-systems/general-tools/claude-code-temp-folders-of-exited-agent-sessions-delete.py`, ned-box cron 07:30 | Deletes each Claude Code agent-session folder, under `/tmp/claude-<uid>/` and `~/.cache/claude-code-tmp/claude-<uid>/`, whose agent-session's `claude` process has exited, read from `~/.claude/sessions/` and `/proc`; keeps the folder crash recovery would resume, folders changed within an hour, and anything that is not a `<project>/<session id>/` folder. With its flag, it then runs the sweep below. 314 lines, test 493 lines. | Retired into the daily job: Claude Code's folders go into one temp folder for each agent-session (§ 4). Its cron line is taken off with the installer's `--remove --job` before the pull request that deletes it from the table merges, as the installer's RETIRING A JOB says. |
| `nc-systems/general-tools/tmp-and-reviewer-scratch-folders-unchanged-a-day-and-unused-delete.py`, run by the job above | Deletes each folder directly in `/tmp` and in `~/.cache/merge-lane-pull-request-reviewer-scratch-directories/` unless another account owns it, anything in it changed in the last 24 hours, a process uses it or a socket is bound in it, or, for an `rv<n>` folder, pull request n is open; logs each deletion to the log-store. 296 lines, test 445 lines. | Retired. The reviewer scratch half moves into the root (§ 4). The `/tmp` half is left to the tmpfiles rule below: on 2026-11-17 the folders of this account in `/tmp` older than a day held 0.03 GB, against a 30 GB tmpfs that was 13% full, so `/tmp` does not need a daily sweep once Claude Code's folders are off it. |
| The `/tmp` tmpfiles rule, `config/ned-box-tmpfiles-tmp-cleanup-rule-ignoring-directory-access-time.conf`, installed on 2026-11-12 as `/etc/tmpfiles.d/tmp.conf` by `scripts/ned-box-tmpfiles-tmp-cleanup-rule-dry-run-or-install-and-clean-once.py` | systemd-tmpfiles deletes entries in `/tmp` older than 10 days, by birth and modification time, ignoring the access time that every listing of `/tmp` refreshes, while other tmpfiles.d exclusions such as tmux's still hold. | Kept, as the one rule for `/tmp`, which programs outside this project also write to. Its age changes from 10 days to 7, so one number holds for both places (decision 2 in § 11). The user reinstalls it with that script, which needs sudo. |
| `nc-systems/general-tools/guarded-file-versions-and-approvals-store-removed-checkout-copies-prune.py`, both machines, 07:00 | Prunes the guarded-file hook's store in the log-store (623 MB for ned-box, 27 MB for the Mac): deletes a copy whose version a commit on a durable ref holds, and the approved copies of checkouts that no longer exist. | Unchanged. The store holds records the hook's `--restore` reads, not temporary things, and its rule is "git already holds this version", which age cannot replace: a file in a worktree kept for months still needs its copies. |
| `scripts/clean-worktrees.py --remove`, both machines, 06:30, and at every session-handoff | § 7. | Cut down, § 7. |

## 7. clean-worktrees.py, cut down

Worktrees that hold an agent-seat's own branch stay where they are. The cleaner keeps the removal rule the user approved, a worktree whose branch's pull request has merged or closed, and, if the user chooses so in decision 4, the owner-stopped rule; it loses the rules that judge a worktree by its age and the rule for merge-lane review checkouts. Every duty that keeps a removal from losing work that cannot be done again stays.

| Duty today | Kept or cut | Why |
|---|---|---|
| Remove a worktree whose branch's pull request has merged or closed | kept | The rule the user approved. |
| Remove a worktree whose owner has stopped and that has no open pull request | decision 4 in § 11 | This rule removed 171 worktrees whose branch never had a pull request between 2026-11-04 and 2026-11-17, 143 of them Claude Code subagent worktrees under the reference-checkout's `.claude/worktrees/`, and 93 at a session-handoff. |
| Remove an idle worktree: unchanged 2 days, nothing uncommitted, every commit on origin | cut | It judges a worktree by its age, which the root now does for temporary things; a worktree with nothing to lose that this rule no longer removes is listed by the first-prompt list or by the cleaner's count line. |
| Remove a merge-lane review checkout 24 hours after its pull request finished | cut | Review checkouts move into the root (§ 4); the merge program already removes `pr<n>-head` and `pr<n>-merged` after a merge, and the daily job removes the rest. |
| Unlock a worktree Claude Code locked for a subagent that has ended | kept | Without it a merged subagent worktree stays locked and is never removed. |
| Ship walks, cold-read-records and sanity-check records before a removal, keeping the worktree when one does not ship | kept | A record not in the log-store would be lost for good. No record was ever shipped from a review checkout, so review checkouts need no shipping in the root. |
| A work-snapshot of uncommitted files, and a branch for commits on a detached HEAD, before a removal | kept | The files and commits cannot be made again; one work-snapshot has been restored, by the task it opened under `~/.claude/tasks/`. |
| Finish a removal stopped part way, from its record | kept | Otherwise a killed invocation leaves a half-removed worktree. |
| Delete branches whose commits are on main, or whose merged or closed pull request holds their tip | kept | Belongs to the merged-or-closed rule. |
| Delete leftover work-snapshots 10 days after first listing, and close restored-branch tasks | kept | Duties of the work-snapshot design, `nc-systems/handoff/handoff-uncommitted-work-snapshots-across-crashes-design.md`; moving them is a change of its own. |
| `--remove-worktree-and-force-delete-its-branch` and `--force-delete-branch` | kept | The first-prompt list prints them beside each entry it lists. |
| `--only-done` at the launchers, the count lines, the dead-registration line | kept | Report only. |

Most of the cleaner's 2,450 lines are the kept duties; the cut removal rules are about 130 lines of its functions, with their tests. Removing more would mean changing what the kept duties protect, which needs a decision of its own.

## 8. Steps that need judgment

The daily job, the one-off move and the cut-down cleaner need none. Three steps do:

1. Whether to carry on a worktree or branch that never had a pull request, or delete it. The agent-session judges each entry the first-prompt list shows it, as now (`nc-systems/handoff/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py`).
2. Whether a hand-made scratch folder now in merge-helpers holds anything merge-lane-2 still needs. merge-lane-2 judges each once, moves the rest into `<root>/merge-lane-2/`, and makes new hand-made scratch there.
3. Whether a program's folder is temporary when its author changes it to write to the root. The author judges, and the rule for the answer is § 2: a folder that one piece of work makes and nothing reads once that work is done.

## 9. Which machines

ned-box only. Everything § 4 moves runs only on ned-box: merge-lane-2 and its programs, and the handoff-supervisor sets `CLAUDE_CODE_TMPDIR` only there. The cut-down `clean-worktrees.py` still runs on both machines. When a program that runs on the Mac first writes to the root, the same job is added to the Mac in the table, as a launchd job, in that program's pull request; the job reads no `/proc`, so it runs on macOS unchanged.

## 10. Guards left out, and how the build goes

**Left out**, each because no failure has been recorded and its harm is work that can be done again: keeping a temp folder that a running process uses or a socket is bound in; keeping the temp folder of an agent-session that crash recovery would resume; keeping the scratch of an open pull request; checking that a deleted folder was really temporary; telling anyone, other than on stderr and in the deleted-folders log, about a temp folder that fails to delete day after day. The worktree removal in § 3 step 3 is not a guard: without it the next review of the same pull request fails every time.

**Build order.** The build follows the rename, so every path is written with nedsnodes names once. One pull request, since its parts cannot merge apart: the daily job and its test; the shared function; the new paths in merge-lane-2's programs and their tests; `CLAUDE_CODE_TMPDIR` in `nc-systems/handoff/handoff-supervisor.py`, and its copy in `scripts/locate-file-copies-across-machines.py`; the cut-down cleaner and its test; the deletion of the two retired programs and their tests; the table entries; the tmpfiles rule's new age in `config/ned-box-tmpfiles-tmp-cleanup-rule-ignoring-directory-access-time.conf`; the one-off move program; and a test that fails when a tracked file names one of the old places, `~/.cache/merge-lane-review-worktrees`, `merge-lane-pull-request-reviewer-scratch-directories`, `claude-code-tmp` or `merge-helpers/hr/pr`, so the build finds every caller and the old places do not come back. Before it merges, the retired job's cron line is taken off ned-box with `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py --remove --job claude-code-temp-folders-of-exited-agent-sessions-delete`.

**Tests at build time**, since this design states them without having run them: that `git worktree remove --force` run from the repository the `.git` file names removes both the folder and its registration; and that a `claude --resume` given the same `CLAUDE_CODE_TMPDIR` finds its earlier task output.

## 11. Decisions for the user

1. **Where the root is.** `~/.cache/nedsnodes-temp-folders-by-agent-seat/` is excluded from Timeshift's hourly backup of the home directory, as `~/.cache/**` already is, so no backup carries the 54 GB. `~/nedsnodes-temp-folders-by-agent-seat/` matches "a temp folder in the home directory" more literally, but the user must add its exclusion to `/etc/timeshift/timeshift.json` by hand, since agents may not edit it. Recommendation: `~/.cache/`.
2. **The `/tmp` rule's age.** Change it from 10 days to 7, so one number holds for both places, or leave it at 10. Recommendation: 7.
3. **Pattern citations into merge-helpers.** Accept that GHI 2569's and GHI 1374's pattern citations stop opening anything once the folders are deleted, or have the one-off move copy every file those patterns match into a records folder first, about 3.2 GB of `stdout`, `stderr` and `log-store/`. Recommendation: accept; the measurements are already written in the GHI-MDs.
4. **Worktrees whose branch never had a pull request.** Keep the cleaner's owner-stopped rule: once a worktree's owner has stopped and no pull request is open, the cleaner takes a work-snapshot of its uncommitted files and removes it, keeping its branch, which the first-prompt list then shows its agent-seat. Or cut the rule, and rely on the first-prompt list alone, which would show the agent-seats about 85 more worktrees a week in all to judge. Recommendation: keep the rule, since its removal loses nothing and spares that judgment.
