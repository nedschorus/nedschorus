# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-20)

Assertions of the overview that the claim check against commit 47b7f0bb3e3416391f4f8a5b8145fe577bf12443 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/2f0219bf69a7d6aa36f34ae8b162971021b35cfb-2026-11-20T16-40-42-343880Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py` removal rules, including "a worktree locked by Claude Code for a subagent whose process has ended is unlocked by `--remove` and then judged like any other".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The process in Claude Code's lock is the dispatching agent-session's `claude`, not a process of the subagent.
> - worktree-owner-file-read-and-write.py:32-34 "locks it while the subagent runs with the reason "claude agent agent-<id> (pid N start M)", N being the dispatching agent-session's `claude` process"
> - clean-worktrees.py:80-87 "once no process N that started at T runs ... --remove unlocks the worktree, first writing it an owner file ... naming that ended agent-session"
> - The other rules in the sentence hold: clean-worktrees.py:60-67 and :397 for idle worktrees, :94-101 and :395 for merge-lane review checkouts, and :44-58 for the owner rules.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: Shared state `worktree-owner.json`, including "or by `clean-worktrees.py` once that subagent's `claude` process has ended".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The process is the dispatching agent-session's `claude`, not the subagent's.
> - worktree-owner-file-read-and-write.py:32-34 "N being the dispatching agent-session's `claude` process"
> - clean-worktrees.py:80-86 "once no process N that started at T runs ... writing it an owner file ... naming that ended agent-session"
> - The rest of the bullet holds:
>   - agent-seat-worktree-create-with-owner-file.py:197 `core.hooksPath={NO_HOOKS_DIRECTORY}`;
>   - the WorktreeCreate hook, line 39, runs that creator;
>   - the post-checkout program writes owner files (git-client-side-hooks-post-checkout-new-worktree-owner-file-write.py:125);
>   - the first-prompt list reads them through cleaner.owner_file (first-prompt list:220).
State: open
