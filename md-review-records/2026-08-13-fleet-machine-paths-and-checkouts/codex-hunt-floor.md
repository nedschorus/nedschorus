<!-- provenance: runtime=codex model=gpt-5.6-luna effort=xhigh cell=defect-hunt tier=floor target=/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/docs/cross-project/fleet-machine-paths-and-checkouts.md -->

1. Line 8 — “Where every working copy, agent home, and handoff file lives on each machine”

   The tables provide patterns and one concrete Ubuntu home, not an exhaustive inventory. An independent clone or a bare agent directory created after checkout failure is a counterexample. Confidence: unsure — this may intend “every category,” but that scope is unstated.

2. Line 10 — “for every session”

   The referenced file is on Ubuntu, while the document also says Mac agents exist. A Mac session cannot read `/home/nedlern/.claude/CLAUDE.md`; the phrase therefore supports a false fleet-wide reading. Confidence: unsure — “on the box” may be intended to limit the scope.

3. Line 14 — “Agent sessions run on `ned-box`”

   This conflicts with line 16 and line 59, which say agents can run on the Mac. It also duplicates and conflicts with [CLAUDE.md](/home/nedlern/.claude/CLAUDE.md:3), which says: “Claude sessions here run on `ned-box` ... The Mac also runs its own Claude agents.” Confidence: sure.

4. Line 14 — “Nothing but git branches crosses between them ... credentials are per-machine and never travel.”

   This is broader than the actual arrangement. The supporting instructions say the Mac mounts the box’s home at `/Volumes/nedhome/...`, and an operator can also copy a handoff file or credential manually. The document gives no boundary defining “crosses.” Confidence: unsure — it may mean only automatic workflow synchronization.

5. Line 16 — “The Mac runs agents only when the work needs to be where the user is”

   “Only” makes this an absolute claim. A Mac agent can be started because the box is unavailable, because of a local failure, or simply by operator choice when no Mac-only resource is needed. Confidence: sure.

6. Line 16 — “The Mac is also the review-and-merge seat”

   This duplicates the definition in [CLAUDE.md](/home/nedlern/.claude/CLAUDE.md:5): “the review-and-merge seat for nedschorus.” The added causal statement, “branch protection admits only `NedLern`, so merges to `main` happen from the Mac,” is wrong: account-based protection does not restrict the machine from which that account operates. Confidence: sure.

7. Line 20 — “All working copies on a machine are the same repository viewed at different branches, sharing one object store”

   This excludes ordinary independent clones and detached worktrees. It also makes “all working copies” contradict the possible launcher failure that leaves an agent in a plain directory. Confidence: sure.

8. Line 20 — “Git allows a branch to be checked out in only one worktree at a time ... git refuses”

   `git worktree add --force` and equivalent checkout options can deliberately bypass this restriction, and a separate clone can check out the same branch without sharing the first clone’s worktree registry. The claimed safety mechanism therefore has a direct ordinary counterexample. Confidence: sure.

9. Line 22 — “what a session reads for the live `.claude/` machinery (hooks, settings)” and “the instruction-file guard’s worktree bug”

   “Session,” “live machinery,” and “instruction-file guard” are unexplained names. The sentence also lacks scope: a stale main worktree does not imply that an agent-home worktree has stale hooks, while line 73 says pulling main does not update those homes. Confidence: unsure — the project may have a specific guard arrangement, but this file does not identify it.

10. Line 23 — “made a checkout deliberately with `git worktree add`”

    Both launcher scripts have a reachable failure path in which `worktree add` fails and the agent starts anyway in a plain directory: [launch-claude-ubuntu](/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/scripts/launch-claude-ubuntu:121) and [launch-claude-mac](/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/scripts/launch-claude-mac:125). That case is neither a checkout nor on the named branch described here. Confidence: sure.

11. Line 24 — “created by the harness when a session isolates itself”

    “Harness” and “isolates itself” are undefined, with no executable procedure or identifiable component. A future agent cannot determine which process creates these worktrees, which sessions qualify, or how to locate that process. Confidence: sure.

12. Line 24 — “removed when the job ends ... the directory afterwards is litter”

    A directory that is removed cannot simultaneously remain as litter. The sentence also leaves push failure, interruption, job crash, and uncommitted changes unresolved; “their value leaves as pushed commits” is false when no push succeeds. Confidence: sure.

13. Line 33 — “the founding seat”

    This label is not self-documenting and has no stated behavior. The path and branch identify `choirmaster`, but “founding seat” does not tell a future agent why it is special or where to search for that concept. Confidence: sure.

14. Line 36 — “Handoff files | `/home/nedlern/.claude/handoffs/<agent>-handoff.md`”

    This defines a file store but leaves absence, staleness, partial writes, replacement, and same-name handling unspecified. A future agent cannot tell whether a missing file means “no handoff,” cleanup, or failure. Confidence: unsure — the document may intend to be location-only, but it presents the row as a complete map.

15. Lines 39–41 — “Legacy reference system” / “legacy checkout”

    This duplicates the checkout instruction’s definition: “The legacy system at `~/Projects/nedlern` is read-only reference: read anything there freely; NOT: modify anything there or execute its code.” The target uses a different label and does not carry the read-only/no-execution meaning, so the two definitions can drift. Confidence: sure.

16. Line 41 — “the git-gatekeeper’s `--import` machinery refuses `import-invalid` ... Clone it only when an import is actually needed.”

    The sentence supplies no executable gatekeeper command, no cloning source, and no criterion for “actually needed.” “Until one exists” also fails to identify what “one” must be beyond the later unexplained phrase “readable git repository.” Confidence: sure.

17. Line 45 — “The checkout path is pinned by the repository’s own tests”

    [handoff-extract-conversation-test.py](/home/nedlern/Projects/nedschorus/.claude/worktrees/gatekeeper-walk-fork-continuation/scripts/handoff-extract-conversation-test.py:232) only uses `/Users/el/Projects/nedschorus` as input to a path-mangling assertion. It does not assert that this directory exists or is the Mac checkout, so the test does not pin the checkout path. Confidence: sure.

18. Line 45 — “the remaining rows follow the same conventions and have not been inspected from the box”

    The Mac rows are presented as operational locations while explicitly being unverified. The document gives no basis for the rows beyond extrapolation, and omits Mac user-level instructions, auto-memory, and the legacy-reference status. Confidence: unsure — the sentence may intentionally mark the table as provisional.

19. Line 60 — “List agents running on a machine | either | run the matching launcher with no name”

    This is not an executable command: “matching launcher” is undefined, and the table does not give an Ubuntu-side invocation or SSH form. The launcher paths shown above are Mac paths, so the `either` instruction cannot be followed literally from both machines. Confidence: sure.

20. Line 61 — “See every checkout and its branch”

    `git worktree list` reports worktrees registered with one Git clone, not independent clones or plain directories. It also reports detached worktrees without a branch. The stated goal is therefore broader than the command’s result. Confidence: sure.

21. Line 65 — “running a name that is already up attaches to that agent”

    The referenced launchers support `--no-attach`; with that mode, an existing session is not attached to. The sentence is true only for the unqualified default invocation, but does not state that limitation. Confidence: sure.

22. Line 65 — “duplicate agents are impossible three ways”

    These protections cover the launcher/supervisor path, not arbitrary processes. A second Claude process can be started manually in the same home, in another tmux session, or from a separate clone; deriving a home path from a name is not itself an exclusion mechanism. Confidence: sure.

23. Line 65 — “the same name on both is simply two unrelated agents: no conflict ... nothing requires it” (about suffixes)

    The launchers derive the branch name from the agent name. Thus the same name on both machines produces the same branch name, which line 69 itself says can fight over one remote ref. The “no conflict” and “nothing requires” claims are incompatible with that later sentence. Confidence: sure.

24. Line 69 — “through them every committed file”

    Only objects reachable from pushed refs cross through Git. A commit on an unpushed branch, or a commit in another local clone, is an ordinary counterexample to “every committed file.” Confidence: sure.

25. Line 69 — “the one real cross-machine collision surface”

    Separate branches can later produce content conflicts when merged, and the machines can also interact through shared mounted files or remote configuration. “Collision surface” is not defined narrowly enough to justify “one.” Confidence: unsure — the phrase may intend only direct remote-ref collisions.

26. Line 71 — “anything uncommitted” under “Does not cross”

    An uncommitted change can cross through the mounted home or a manual copy, so this absolute claim is false outside an unstated Git-only protocol boundary. Confidence: sure.

27. Line 73 — “pulling the main checkout does not update agent homes or task worktrees”

    A pull updates the shared repository’s remote-tracking refs and object store, which linked worktrees can observe, even though their checked-out branch and files do not move. “Update” therefore supports incompatible meanings. Confidence: sure.

28. Line 73 — “After a merge to `main`, the main checkout needs its own pull”

    If the merge is performed in that main checkout, it already contains the merge and no pull is needed. The claim is also missing the machine scope: only other clones necessarily need to fetch the result. Confidence: sure.

29. Line 73 — “any long-lived agent branch needs `main` merged into it before that agent sees the change”

    Merging is not necessary: rebasing, cherry-picking, fast-forwarding, or starting from a commit that already contains the change also makes it visible. The sentence provides no executable update procedure or stopping condition. Confidence: sure.

clean sections: none.
