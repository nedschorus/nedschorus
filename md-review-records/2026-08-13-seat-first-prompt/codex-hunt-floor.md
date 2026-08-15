<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/agents/seat-first-prompt.md -->

1. “everything you need is reachable from here.” This is contradicted by line 21, which requires asking the user when no brief exists. That reachable case requires information outside this file. Confidence: sure.

2. “Your seat name is the name of your working directory. Run `pwd`: if it is `/home/nedlern/agents/<name>`, then `<name>` is your seat.” The procedure handles only that exact path. A nested checkout, symlink, or other valid working directory leaves the agent unable to determine its seat or brief. Confidence: sure.

3. “The launcher makes your home a checkout … before your session starts.” The referenced seat model says the launcher creates an “empty directory, not a checkout,” and the first-prompt file makes it a worktree on the first run. This prompt therefore treats the normal launch state as a launch failure. Confidence: sure.

4. “`git rev-parse --show-toplevel` should answer with your own directory and `git branch --show-current` with your seat name.” No outcome is defined for a valid checkout with a detached HEAD, an unexpected branch, or a top-level path that differs from the working-directory name. The agent can pass the checkout test while operating on the wrong branch, with no stated action. Confidence: sure.

5. “If it is *not* a checkout, something went wrong at launch.” The referenced seat model explicitly describes a normal launch into an empty non-checkout directory. This instruction would make the intended first-run state appear erroneous and tell the agent to relaunch instead of following the normal setup path. Confidence: sure.

6. “`origin/main`” in the repair command is an unstated precondition. A checkout with no `origin` remote, no fetched `origin/main`, or a differently named remote makes the command fail, and the prompt gives no handling for that failure. Confidence: unsure — the launcher may guarantee this remote, but that guarantee is not stated here.

7. “drop `-b` and pass the branch name last if the branch already exists” supports incompatible command constructions. It does not say whether the existing `origin/main` positional argument remains; retaining it while moving `<name>` to the end produces a different and potentially invalid argument list. This is specifically triggered in the branch-exists case. Confidence: unsure — the intended Git transformation can be inferred, but the wording does not uniquely specify it.

8. “if the branch already exists” leaves an occupied-branch case unresolved. An existing branch may already be checked out in another worktree, in which case the ordinary `worktree add` operation refuses it. The prompt provides no result or stopping rule for that case. Confidence: sure.

9. “git permits a branch in only one worktree at a time” is false as an absolute claim. Git’s `--force` option permits a branch to be checked out in another worktree, so branch exclusivity is a default guard, not an unconditional property. Confidence: sure.

10. “If no file in `docs/agents/` matches your seat name” does not define what “matches” means. Exact filename, prefix, substring, and case-sensitive interpretations can disagree, so the agent cannot reliably know whether it has found its brief. Confidence: unsure — the preceding `<name>-instructions.md` pattern suggests exact matching, but does not state it.

11. “Every brief's first action is to read, verify, and report to the user” is contradicted by an existing brief: `sidebar-instructions.md` says, “Greet the user briefly and ask what he needs. No status report, no inventory, no plan.” Following this sentence would make an agent disregard its actual brief. Confidence: sure.

12. “read, verify, and report to the user” does not identify what must be read, what must be verified, what evidence satisfies verification, or what the report must contain. The agent cannot determine when this mandated first action is complete. Confidence: sure.

13. “Changes reach `main` only through the user's Mac-side review seat” conflicts with `CLAUDE.md`, which says: “the git-gatekeeper … is the permanent path,” while the Mac-side review seat is only the interim lane “until its credential work lands.” The target sentence is false once the gate is active and omits the condition under which the interim route applies. Confidence: sure.

14. “anything under `.claude/`” is broader than the actual guard’s protected set. The hook explicitly carves out `.claude/worktrees/` and `.claude/jobs/` as ordinary working and scratch space. The blanket definition therefore misclassifies reachable files and gives the agent a false approval requirement. Confidence: sure.

15. “a hook enforces this and will tell you the sanctioned path if you forget.” The configured hook runs only for `Edit`, `Write`, and `NotebookEdit`, is explicitly a soft block, and does not mediate shell or other direct file changes. It supplies guidance only when a matching hook invocation occurs, not for every unauthorized change. Confidence: sure.

clean sections: none.
