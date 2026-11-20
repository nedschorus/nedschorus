# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-20)

Assertions of the overview that the claim check against commit a9f87f0c602f5ae1cead8145adb6d31e184c7d9c found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/a90d58084f1bf5045f885b07773932fffb5c5bfa-2026-11-20T18-23-10-478975Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout back-on-main program "saves the checkout's leftovers, its uncommitted changes and the commits origin/main lacks, to a branch it pushes, and only then puts the checkout back on main."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> nn-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29: `then runs git switch --no-overwrite-ignore -C main origin/main, which puts the local main at origin/main and checks it out, whether or not every push succeeded`. Also handoff-supervisor.py:2464-2466: `which it can be even after a failed push, so a leftovers branch the program could not push stays only in that checkout`. The program does not wait for a successful push before putting the checkout back on main. Because the leftovers stay on a local branch and later runs push them, no work is lost and no agent would act wrongly, so this is ranked fix-later.
State: open
