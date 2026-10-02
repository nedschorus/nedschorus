# The gatekeeper runs no checks at check-in, though 83 test suites now exist

Promoted from `docs/issues/queue/` on 2026-10-02 as a supporting document of issue [main-gatekeeper — the single check-in gate (design: nc-systems/main-gatekeeper/main-gatekeeper-design.md)](https://github.com/nedschorus/nedschorus/issues/3) (main-gatekeeper — the single check-in gate). Line numbers and counts below re-measured on main on 2026-10-02. Owned by the `gatekeeper` seat (`docs/agents/gatekeeper-instructions.md`).

Surfaced by the attack-split validation experiment of 2026-08-12 (`md-review-records/2026-08-12-attack-split-experiment/scorecard.md`, § Novel findings, "Checks-never-wired"), which scored a split sanity-checker prompt against two archived documents. The finding fell outside what that experiment was scored against, so it was never triaged. Verified against the repository as it stands on 2026-08-13 by the `sanity-checker` seat and written here because a triage nobody records evaporates — these sat unpresented for two days.

## 1. The specification promises checks it does not run — CONFIRMED

`nc-systems/main-gatekeeper/main-gatekeeper-design.md:98` states the growth point of the check set:

> In v1 the check set *is* construction itself, so guarantee 2 binds the checks that exist — construction — to the exact pushed bytes; it gains content as checks are added. That is the growth point, not a hole: **when a test suite exists, the tests run here**; when the user gates an artifact class, its review-evidence check runs here.

The condition is now met and the consequent is not built. 83 test suites exist (`git ls-files '*-test.py'`; seven when this note was written on 2026-08-13). `scripts/run-all-test-suites.py` runs them, and two programs call it: `scripts/daily-full-test-run-of-main.py` and `scripts/pull-request-head-test-run.py`. The gatekeeper calls neither, and no suite is wired into the check-in path.

The program says so itself. `nc-systems/main-gatekeeper/main-gatekeeper.py:868-870`, inside `integrate_and_push`, at the exact place the spec designates:

> `# Version 1 re-runs every check against the rebuilt candidate; there`
> `# are none beyond construction yet, so this is where a test suite`
> `# attaches when one exists.`

**What this is and is not.** It is not a live hole today: no host holds a main-capable credential, the gate is dormant, and nothing routes through it. It is an unimplemented promise that becomes a live hole on the day the gate activates — at which point a check-in that breaks the gatekeeper's own suite would land on main unchallenged, and the design's guarantee 2 would bind a check set that is still only construction.

**Adjacent fact, verified while checking this:** the repository has no `.github/` directory and no CI workflows. The suites now run outside the gate, by the daily full test run of main and by the run of the suites a pull request's head reaches; neither runs at check-in, so wiring the suites at the gate would be the gate's own check, not a duplicate of those two.

**Next action for the `gatekeeper` seat.** Decide with the user where this sits in the build order — it is not one of the six planned slices (`docs/issues/3-main-gatekeeper-build-slice-plan.md`), and whether it precedes activation or ships with it is a scheduling call, not an obvious one. Two questions worth settling in the same breath: which suites run at the gate (the gatekeeper's own, or all 83), and what a suite failure does to a check-in — refuse, or record and pass. The spec's deferred-optimization row (`nc-systems/main-gatekeeper/main-gatekeeper-design.md:120`) already names the trigger for narrowing re-validation "when checks become slow (a real test suite)", so the performance answer is designed and the wiring is not.

## 2. Nothing stops the gatekeeper approving a change to its own source — ALREADY RULED, no action

Recorded here so it is not raised a third time. The concern: an agent edits `nc-systems/main-gatekeeper/main-gatekeeper.py` and checks that edit in through the very program it just changed. It is real, and it is already answered by ruling rather than open.

`nc-systems/main-gatekeeper/main-gatekeeper-design.md:148` (C2, the Unix-user boundary) rules that the deployed copy keeps itself current from main automatically, and that this is safe because "the gatekeeper's source joins the instruction-file class: changes reach main only with approved-by-walk evidence, enforced by the review-evidence check (slice 6). Activating the privileged lane therefore waits on slice 6."

The gatekeeper's seat brief carried this as that seat's work until 2026-09-16 (`git show dab4d40e:docs/agents/gatekeeper-instructions.md`, line 20), including the residual it does not close: slice 6 closes the hole against agents, not against the repository's owners, who can bypass branch protection by design — "that residual is accepted, not solved."

So the remedy is scheduled (slice 6, ruled 2026-08-10 as a prerequisite of activation), owned, and already written into the responsible seat's brief. Nothing to route.

**One adjacent gap that is *not* covered by that ruling**, from the same experiment (`scorecard.md` § Fresh-eyes yield): candidate-supplied check code would execute as the credential-holding Unix user. Slice 6 gates what reaches main; it does not address what a check *executes* once the privileged lane is live. Raised here as an observation for whoever designs the check battery, not as triaged work — it has had no verification pass.
