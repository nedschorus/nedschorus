# Proposed improvements or changes: nedsnodes-handoff-architecture-overview.md (overview claim check, 2026-11-20)

Assertions of the overview that the claim check against commit b514ec8e38942e3ac569f16e463c20b8f3f58325 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedsnodes-logs/overview-write-architecture-overview-claim-check-reports/nedsnodes-handoff-architecture-overview/5fa922f2469933a9d9ddf29d20ac8c77d366d8d7-2026-11-20T05-09-06-423719Z.md. A follow-up pull request fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `nn-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py` saves the checkout's leftovers, its uncommitted changes and the commits origin/main lacks, to a branch it pushes, and only then puts the checkout back on main.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The program puts the checkout back on main even when the push failed. "Only then" says the leftovers are on origin whenever the checkout is back on main, which is not always so.
> - `nn-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29`: "runs `git switch --no-overwrite-ignore -C main origin/main`, which puts the local main at origin/main and checks it out, whether or not every push succeeded".
> - Same file, lines 52-54: "a failed push of a leftovers branch ... still lets the checkout go back on main: the unpushed branch stays in the checkout".
> - `nn-systems/handoff/handoff-supervisor.py:2443-2445`: "which it can be even after a failed push, so a leftovers branch the program could not push stays only in that checkout".
> - Ranked fix-later: the program's own failure message names any unpushed branch, so no agent would open the wrong file or lose work by relying on the overview's wording.
State: open
