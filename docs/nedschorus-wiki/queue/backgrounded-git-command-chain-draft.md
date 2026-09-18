# Draft rule — a backgrounded git command chain acts on the branch as it is LATER (awaiting the user's drain)

One rule candidate, from the cold-read-research seat, 2026-09-10. Destined for CLAUDE.md or the git-infra wiki page; queued rather than landed, because both are operative prose.

**The rule.** Keep `git commit`, `git push` and `gh pr create` as separate foreground commands. Put a long commit message or pull-request body in a file and pass `-F` or `--body-file` rather than a heredoc. Do not chain them into one long command.

**Why, from the incident that produced it.** On 2026-09-10 a seat chained commit, push and pull-request creation into a single command. The harness backgrounded it when it exceeded its foreground timeout, and the seat concluded it had failed. It had not. It completed later, and its `push` ran against the branch **as the branch stood at that moment**, which by then included a catch-up merge the freshness hook had made in the meantime.

The result was that the head of a pull request already under review moved, which is exactly what the frozen-head rule (CLAUDE.md, ruled 2026-09-08) exists to prevent. No review round was lost, because merge-lane retargeted, but the cost was reachable.

The seat's own account to the user had been wrong in the meantime: it reported that it was holding the line by not pushing, while a command it had written off pushed for it. The reflog is what settled it.

**The hazard is narrower than "hooks move my branch", and naming it narrowly is the point.** A long chained command that gets backgrounded and finishes later acts on the repository as it is at that moment, not as it was when launched. Chaining is what makes that possible. The heredoc is what makes the command long enough to be backgrounded.

**Related but distinct:** issue [checkout-freshness catch-up merges main into a branch whose head is frozen under review](https://github.com/nedschorus/nedschorus/issues/324) is the freshness hook merging main into a frozen head, which is the other half of how that head moved.
