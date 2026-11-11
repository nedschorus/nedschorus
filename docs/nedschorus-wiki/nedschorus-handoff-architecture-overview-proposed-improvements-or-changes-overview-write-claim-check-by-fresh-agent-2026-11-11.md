# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-11)

Assertions of the overview that the claim check against commit d4cb7c37401d2558899c9fdf923a4cc704b61e78 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4cd83f2b2e1b5d45c8aa9985785034de42e31374-2026-11-11T11-33-40-286553Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `scripts/clean-worktrees.py` keeps a worktree with no owner file, or a locked one.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/clean-worktrees.py:7 "Only a worktree holding an owner file, or a merge-lane review checkout … can be removed"; :64-71 "A worktree with no owner file directly inside ~/.cache/merge-lane-review-worktrees … is removed when that pull request was merged or closed at least 24 hours ago"
> - scripts/worktree-owner-file-read-and-write.py:38-41 "The cleaner never removes a worktree with no owner file, except a merge-lane review checkout"
> - The rest of the bullet is supported: owner and pull-request rule at :34-48, record shipping at :88-99, branches at :131-135, log at :238 and :248-249, ten-day deletion at uncommitted-work-snapshots.py:78. The locked case is also qualified at :50-62, where an ended Claude Code lock is unlocked.
> - No agent is likely to act wrongly on it, but the "no owner file … is kept" rule leaves out the merge-lane review checkouts the cleaner does remove.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The back-on-main program is run by an agent-seat when the reference-checkout will not fast-forward. It saves the leftovers to a branch it pushes, and only then puts the checkout back on main.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 "puts the local main at origin/main and checks it out, whether or not every push succeeded"; :52-55 "a failed push of a leftovers branch … still lets the checkout go back on main: the unpushed branch stays in the checkout"
> - It moves main only once a branch holds the leftovers (:61), not once the branch is pushed.
> - The handoff-supervisor also runs it itself, :7-9 "the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself"; handoff-supervisor.py:2383-2389. The bullet leaves that out.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: When the restart fails, the successor's instructions name the back-on-main program when the supervisor runs from the reference-checkout and the replacement itself did not fail, and the restart program otherwise.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-supervisor.py:2383-2395: from the reference-checkout the supervisor first runs put_reference_checkout_back_on_main itself.
> - The notice names that program only "except reference_checkout_back_on_main.StepFailed", i.e. when that run failed (:2321-2325).
> - If the run succeeds but the checkout is still not on main, :2399-2401 give the restart-program notice (:2326-2329).
> - The overview also does not say that the handoff-supervisor runs the back-on-main step itself before naming it.
State: open
