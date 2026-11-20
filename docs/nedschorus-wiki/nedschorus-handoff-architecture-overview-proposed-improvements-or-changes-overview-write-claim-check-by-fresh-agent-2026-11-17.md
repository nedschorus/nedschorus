# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-17)

Assertions of the overview that the claim check against commit 1009d545503c4d5284aff3bf319bfb4f255ae3d7 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c88a937f0b92541c5208190d8e883142f26c4fe5-2026-11-17T06-14-27-360390Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: Back-on-main program "saves the checkout's leftovers ... to a branch it pushes, and only then puts the checkout back on main."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The program puts the checkout back on main even when the push failed. A branch does hold the leftovers first, but the push is not a precondition.
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `which puts the local main at origin/main and checks it out, whether or not every push succeeded`
> - :51-54 `except a failed push of a leftovers branch ... which still lets the checkout go back on main: the unpushed branch stays in the checkout`
> - handoff-supervisor.py:2333-2335 `which it can be even after a failed push`
> - Suggested wording: "saves them on a branch, pushes it, and then puts the checkout back on main, even when the push failed."
State: open
